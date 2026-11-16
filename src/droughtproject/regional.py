# ////////////////////////////////////////////////////////////////////////////
# // 1. Selects NASA meteorological cells overlapping Marrakech–Safi.
# // 2. Downloads daily history and adds cell coordinates/source elevation.
# // 3. Reuses rolling rainfall features; compares one shared regional forest
# //    with no location, coordinates, and coordinates plus elevation.
# // 4. Saves tables, chronological scores, predictions and the fitted model.
# ////////////////////////////////////////////////////////////////////////////
import json, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
sys.path.insert(0, '/Users/mac/Desktop/DroughtProject/src')
from droughtproject.dynamic import rolling_daily, snapshots, daily_normals, dynamic_features
from droughtproject.prepare import longest_dry
from droughtproject.train import new_model
from droughtproject.settings import VALIDATION_WINDOWS, BENCHMARK

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'findings'/'regional'
CODES={'PRECTOTCORR':('rainfall_mm','mm/day'),'T2M':('temperature_c','C'),'RH2M':('humidity_pct','%'),'PS':('pressure_kpa','kPa')}
BOUNDARY_URL='https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/9469f09/releaseData/gbOpen/MAR/ADM1/geoBoundaries-MAR-ADM1.geojson'

def clip(poly, axis, bound, lower):
    if not poly: return []
    out=[]
    prev=poly[-1]
    for cur in poly:
        a=(prev[axis]>=bound) if lower else (prev[axis]<=bound)
        b=(cur[axis]>=bound) if lower else (cur[axis]<=bound)
        if a!=b:
            t=(bound-prev[axis])/(cur[axis]-prev[axis])
            out.append([prev[0]+t*(cur[0]-prev[0]),prev[1]+t*(cur[1]-prev[1])])
        if b: out.append(cur)
        prev=cur
    return out

def overlap(ring,x,y):
    p=ring
    for axis,bound,lower in [(0,x-.3125,True),(0,x+.3125,False),(1,y-.25,True),(1,y+.25,False)]: p=clip(p,axis,bound,lower)
    return len(p)>2 and abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1])))>1e-10

def cells():
    boundary=OUT/'boundary.geojson'
    if not boundary.exists():
        with httpx.Client(timeout=120,follow_redirects=True) as c:
            r=c.get(BOUNDARY_URL);r.raise_for_status();j=r.json()
        feature=next(f for f in j['features'] if f['properties']['shapeISO']=='MA-07')
        boundary.write_text(json.dumps(feature))
    feature=json.loads(boundary.read_text())
    g=feature['geometry'];polys=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
    rings=[p[0] for p in polys]
    coords=[v for r in rings for v in r]
    rows=[]
    for y in np.arange(29.5,34.01,.5):
        for x in np.arange(-11.25,-4.99,.625):
            if any(overlap(r,float(x),float(y)) for r in rings):
                rows.append({'cell_id':f'{y:.3f}_{x:.3f}','latitude':float(y),'longitude':float(x)})
    return rows

def download(cell):
    dest=OUT/'raw'/f"{cell['cell_id']}.json"
    if dest.exists(): return cell,json.loads(dest.read_text())
    for attempt in range(4):
        try:
            with httpx.Client(timeout=240,follow_redirects=True) as c:
                r=c.get('https://power.larc.nasa.gov/api/temporal/daily/point',params={'parameters':','.join(CODES),'community':'AG','latitude':cell['latitude'],'longitude':cell['longitude'],'start':'19950101','end':'20251231','format':'JSON','time-standard':'UTC'})
                r.raise_for_status();j=r.json()
            if 'parameter' not in j.get('properties',{}): raise ValueError(str(j)[:300])
            dest.write_text(json.dumps(j));print('Downloaded',cell['cell_id'],flush=True)
            return cell,j
        except (httpx.HTTPError,ValueError):
            if attempt==3: raise
            time.sleep(5*(attempt+1))

def prepare(cell,j):
    if j['header']['time_standard']!='UTC': raise ValueError('Expected UTC')
    dates=pd.date_range('1995-01-01','2025-12-31')
    d=pd.DataFrame(index=dates)
    for code,(name,unit) in CODES.items():
        if j['parameters'][code]['units']!=unit: raise ValueError('Unexpected unit')
        v=pd.Series(j['properties']['parameter'][code]);v.index=pd.to_datetime(v.index,format='%Y%m%d')
        if not v.index.equals(dates): raise ValueError('Incomplete daily coverage')
        d[name]=v
    if not np.isfinite(d.to_numpy()).all() or d.eq(j['header']['fill_value']).any().any(): raise ValueError('Missing values; no automatic imputation')
    if d.rainfall_mm.lt(0).any() or not d.humidity_pct.between(0,100).all() or d.pressure_kpa.le(0).any(): raise ValueError('Invalid physical values')
    cell=dict(cell,source_elevation_m=float(j['geometry']['coordinates'][2]))
    if not np.isfinite(cell['source_elevation_m']) or cell['source_elevation_m']==j['header']['fill_value']: raise ValueError('Missing source elevation')
    m=d.resample('MS').mean();m['rainfall_mm']=d.rainfall_mm.resample('MS').sum();m['period_end']=m.index+pd.offsets.MonthEnd(0)
    m['rainy_days']=d.rainfall_mm.ge(1).resample('MS').sum();m['longest_dry_spell']=d.rainfall_mm.resample('MS').apply(longest_dry)
    rows=snapshots(m);rows=rows[(rows.issue_day==25)&(rows.delay_days==5)].reset_index(drop=True)
    return cell,d,m,rolling_daily(d),rows

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'raw').mkdir(exist_ok=True)
    locations=cells();print('Overlapping NASA cells:',len(locations),flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool: series=[prepare(c,j) for c,j in pool.map(download,locations)]
    pd.DataFrame([s[0] for s in series]).to_csv(OUT/'coordinates.csv',index=False)
    for kind,idx in [('daily',1),('monthly',2)]:
        pd.concat([s[idx].assign(**s[0]).rename_axis('date' if idx==1 else 'month').reset_index() for s in series],ignore_index=True).to_csv(OUT/f'{kind}.csv',index=False)
    nao=pd.read_csv(ROOT/'data/processed/marrakech/nao.csv',parse_dates=['month']).set_index('month')
    predictions=[];scores=[]
    for first,last in VALIDATION_WINDOWS+[BENCHMARK]:
        trainx=[];evalx=[];trainy=[];info=[]
        for cell,d,m,rolling,rows in series:
            ev=rows[rows.target_month.dt.year.between(first,last)].reset_index(drop=True);cutoff=ev.cutoff.min()
            allowed=m.index[(m.index>=pd.Timestamp('1997-01-01'))&(m.period_end<=cutoff)]
            tr=rows[rows.target_month.isin(allowed)].reset_index(drop=True)
            normal=daily_normals(d,cutoff)
            tx=dynamic_features(d,rolling,m,None,nao,tr,normal,'rainfall');ex=dynamic_features(d,rolling,m,None,nao,ev,normal,'rainfall')
            for key in ['latitude','longitude','source_elevation_m']:tx[key]=cell[key];ex[key]=cell[key]
            trainx.append(tx);evalx.append(ex);trainy.extend(m.rainfall_mm.reindex(tr.target_month))
            median=m.rainfall_mm.loc[allowed].groupby(allowed.month).median()
            mean=m.rainfall_mm.loc[allowed].groupby(allowed.month).mean()
            r=ev.assign(**cell);r['actual']=m.rainfall_mm.reindex(ev.target_month).to_numpy();r['seasonal_median']=ev.target_month.dt.month.map(median);r['seasonal_mean']=ev.target_month.dt.month.map(mean);info.append(r)
        X=pd.concat(trainx,ignore_index=True);E=pd.concat(evalx,ignore_index=True);result=pd.concat(info,ignore_index=True)
        for name,excluded in [('shared_no_location',['latitude','longitude','source_elevation_m']),('shared_coordinates',['source_elevation_m']),('shared_coordinates_elevation',[])]:
            cols=[c for c in X if c not in excluded];model=new_model();model.fit(X[cols],trainy);result[name]=model.predict(E[cols]).clip(min=0)
            if (first,last)==BENCHMARK:joblib.dump({'pipeline':model,'feature_columns':cols,'coordinates':series and [s[0] for s in series],'issue_day':25,'delay_days':5,'training_cutoff':str(cutoff.date()),'normals_by_cell':{s[0]['cell_id']:daily_normals(s[1],cutoff) for s in series}},OUT/f'{name}.joblib')
        result['split']='known_benchmark' if (first,last)==BENCHMARK else 'validation';predictions.append(result)
        print(f'Evaluated {first}–{last}',flush=True)
        if (first,last)==BENCHMARK:
            training_meta=pd.DataFrame({'target_month':np.tile(tr.target_month.to_numpy(),len(series)),'cell_id':np.repeat([s[0]['cell_id'] for s in series],len(tr)),'rainfall_target_mm':trainy})
            evaluation_meta=result[['target_month','cell_id','actual']].rename(columns={'actual':'rainfall_target_mm'}).reset_index(drop=True)
            pd.concat([pd.concat([training_meta,X],axis=1).assign(table_split='train'),pd.concat([evaluation_meta,E],axis=1).assign(table_split='benchmark')],ignore_index=True).to_csv(OUT/'feature_table.csv',index=False)
    pred=pd.concat(predictions,ignore_index=True);pred.to_csv(OUT/'predictions.csv',index=False)
    methods=['shared_no_location','shared_coordinates','shared_coordinates_elevation','seasonal_mean','seasonal_median']
    for split,g in pred.groupby('split'):
        for name in methods:
            scores.append({'split':split,'approach':name,'cell_months':len(g),'distinct_months':g.target_month.nunique(),'mae_mm':mean_absolute_error(g.actual,g[name]),'rmse_mm':root_mean_squared_error(g.actual,g[name])})
    scores=pd.DataFrame(scores);scores.to_csv(OUT/'scores.csv',index=False)
    per=[]
    for cell,g in pred[pred.split=='known_benchmark'].groupby('cell_id'):
        for name in methods:per.append({'cell_id':cell,'approach':name,'mae_mm':mean_absolute_error(g.actual,g[name])})
    pd.DataFrame(per).to_csv(OUT/'per_cell_scores.csv',index=False)
    protocol={'boundary':BOUNDARY_URL,'license':'geoBoundaries / OpenStreetMap ODbL attribution required','selection':'MERRA-2 0.5 latitude x 0.625 longitude grid rectangles intersecting Marrakech–Safi; boundary cells can have centres outside region','history':'1995 supplies lag context; target months 1997–2025; training weather normals start 1996','scope':'rainfall only; existing point rainfall/SPI artifacts unchanged','model':'same 200-tree absolute-error RF, depth 3, leaf 5, seed 42; no tuning','forecast':'next calendar month, issued preceding month day 25, simulated 5-day delay','validation':VALIDATION_WINDOWS,'benchmark':BENCHMARK,'warning':'known benchmark, not blind; dates shared across cells; correlated cells are not independent weather events; no spatial holdout; cell-mean MAE is not error of region-average rainfall','elevation':'NASA source elevation, not precise farm elevation','variants':'controlled ablation of coordinates and elevation using same cells, years and weather inputs'}
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
    print(scores.round(3).to_string(index=False),flush=True)
    print(f'Tables and results: {OUT}',flush=True)
if __name__=='__main__':main()
