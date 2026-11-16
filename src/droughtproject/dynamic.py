# ////////////////////////////////////////////////////////////////////////////
# // 1. Reads existing daily weather, monthly rainfall/SPI labels, and NOAA NAO.
# // 2. Builds recent 7/30/90-day inputs backward from each available-data cutoff.
# // 3. Evaluates dated monthly forecasts against the existing calendar model.
# // 4. Saves dynamic rainfall/SPI models, scores, and a November 25 demo forecast.
# ////////////////////////////////////////////////////////////////////////////
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from droughtproject.settings import ROOT, PROCESSED, ARTIFACTS, VALIDATION_WINDOWS, BENCHMARK, MODEL_TARGET_START
from droughtproject.prepare import load_monthly, longest_dry
from droughtproject.spi import fit_reference, calculate_spi, category
from droughtproject.features import build_features, fit_normals
from droughtproject.train import new_model

DAYS = [5, 10, 15, 20, 25]
DELAYS = [3, 5, 7]
REQUIRED = ["rainfall_mm", "temperature_c", "humidity_pct", "pressure_kpa"]
OUT = ROOT / "findings" / "dynamic_windows"
PROTOCOL = {
    "issue_days": DAYS, "simulated_publication_delays_days": DELAYS,
    "target": "Next calendar month total rainfall or ending-month SPI-3",
    "selection": "Fixed existing MAE Random Forest; no hyperparameter/benchmark tuning",
    "validation": VALIDATION_WINDOWS, "known_benchmark": BENCHMARK,
    "training": "Every snapshot for a target month stays in the same chronological split. Training labels end by earliest evaluation cutoff.",
    "counts": "Snapshots share monthly answers; report unique target months, not independent sample claims.",
    "normals": "Training-only daily month-of-year averages; rolling-window expected rainfall sums daily normals across the actual window",
    "nao": "Latest monthly value assumed available 15 days after month end; no future interpolation",
    "comparison": "Calendar model refitted using same allowed target-label months; intended for issue day 10 onwards, not a valid available baseline for day 5",
    "caveats": "Historical publication delays simulated, not vintage releases. Revised observations. Existing known 2024–2025 benchmark, not blind. One point only.",
}


def rolling_daily(daily):
    expected = pd.date_range(daily.index.min(), daily.index.max())
    daily = daily.reindex(expected)
    rain = daily["rainfall_mm"]
    table = pd.DataFrame(index=daily.index)
    table["rain_7"] = rain.rolling(7).sum()
    table["rain_30"] = rain.rolling(30).sum()
    table["rain_previous_30"] = rain.rolling(30).sum().shift(30)
    table["rain_older_30"] = rain.rolling(30).sum().shift(60)
    table["rain_90"] = rain.rolling(90).sum()
    table["rain_30_year_earlier"] = rain.rolling(30).sum().shift(365)
    table["rainy_days_30"] = rain.ge(1).where(rain.notna()).rolling(30).sum()
    table["dry_spell_30"] = rain.rolling(30).apply(longest_dry, raw=True)
    for column in ["temperature_c", "humidity_pct", "pressure_kpa"]:
        mean = daily[column].rolling(30).mean()
        table[f"{column}_30"] = mean
        if column != "temperature_c":
            table[f"{column}_change"] = mean - mean.shift(30)
    return table


def snapshots(monthly):
    rows = []
    for target in monthly.loc[MODEL_TARGET_START:].index:
        previous = target - pd.DateOffset(months=1)
        for day in DAYS:
            issue = previous + pd.Timedelta(days=day-1)
            for delay in DELAYS:
                rows.append({"target_month": target, "issue_date": issue,
                    "cutoff": issue-pd.Timedelta(days=delay), "issue_day": day, "delay_days": delay})
    return pd.DataFrame(rows)


def daily_normals(daily, cutoff):
    history = daily.loc["1996":].loc[:cutoff]
    return history.groupby(history.index.month)[["rainfall_mm", "temperature_c"]].mean()


def dynamic_features(daily, rolling, monthly, spi, nao, rows, normals, target):
    X = rolling.reindex(pd.DatetimeIndex(rows["cutoff"])).reset_index(drop=True)
    angle = 2*np.pi*(rows["target_month"].dt.month-1)/12
    X["month_sin"], X["month_cos"] = np.sin(angle), np.cos(angle)
    X["days_until_target"] = (rows["target_month"]-rows["cutoff"]).dt.days
    X["data_age_days"] = (rows["issue_date"]-rows["cutoff"]).dt.days
    seasonal = pd.DataFrame(index=daily.index)
    seasonal["expected_rain"] = daily.index.month.map(normals["rainfall_mm"])
    seasonal["expected_temperature"] = daily.index.month.map(normals["temperature_c"])
    rain_normal = seasonal["expected_rain"].rolling(30).sum()
    temp_normal = seasonal["expected_temperature"].rolling(30).mean()
    X["rainfall_anomaly_30"] = X["rain_30"]-rain_normal.reindex(rows["cutoff"]).to_numpy()
    X["temperature_anomaly_30"] = X["temperature_c_30"]-temp_normal.reindex(rows["cutoff"]).to_numpy()
    source = nao.copy()
    source["available_at"] = source.index + pd.offsets.MonthEnd(0) + pd.Timedelta(days=15)
    ordered = rows[["issue_date"]].copy()
    ordered["row_number"] = np.arange(len(rows))
    matched = pd.merge_asof(ordered.sort_values("issue_date"), source.reset_index(drop=True).sort_values("available_at"),
        left_on="issue_date", right_on="available_at", direction="backward").sort_values("row_number")
    X["nao"] = matched["nao"].to_numpy()
    X["nao_season_sin"] = X["nao"]*X["month_sin"]
    X["nao_season_cos"] = X["nao"]*X["month_cos"]
    if target == "spi":
        completed = (rows["cutoff"] + pd.Timedelta(days=1)).dt.to_period("M").dt.to_timestamp() - pd.offsets.MonthBegin(1)
        for lag in range(3):
            dates = pd.DatetimeIndex(completed) - pd.DateOffset(months=lag)
            X[f"completed_spi_lag{lag}"] = spi.reindex(dates).to_numpy()
    if not np.isfinite(X.to_numpy()).all():
        raise ValueError("Incomplete rolling inputs: need complete daily windows and the latest available climate index.")
    return X


def run_fold(daily, rolling, monthly, spi, nao, rows, target, first, last):
    evaluation = rows.loc[rows["target_month"].dt.year.between(first,last)].reset_index(drop=True)
    cutoff = evaluation["cutoff"].min()
    allowed_months = monthly.index[(monthly.index >= pd.Timestamp(MODEL_TARGET_START)) & (monthly["period_end"] <= cutoff)]
    training = rows.loc[rows["target_month"].isin(allowed_months)].reset_index(drop=True)
    normals = daily_normals(daily, cutoff)
    X_train = dynamic_features(daily, rolling, monthly, spi, nao, training, normals, target)
    X_eval = dynamic_features(daily, rolling, monthly, spi, nao, evaluation, normals, target)
    labels = monthly["rainfall_mm"] if target == "rainfall" else spi
    model = new_model()
    model.fit(X_train, labels.reindex(training["target_month"]).to_numpy())
    dynamic = model.predict(X_eval)
    monthly_features = build_features(monthly,spi,nao,target,fit_normals(monthly,cutoff))
    control = new_model()
    control.fit(monthly_features.loc[allowed_months], labels.loc[allowed_months])
    unique_evaluation = pd.DatetimeIndex(evaluation["target_month"].unique())
    fixed = pd.Series(control.predict(monthly_features.loc[unique_evaluation]), index=unique_evaluation)
    means = labels.loc[allowed_months].groupby(allowed_months.month).mean()
    medians = labels.loc[allowed_months].groupby(allowed_months.month).median()
    if target == "rainfall":
        dynamic = np.maximum(0,dynamic)
        fixed = fixed.clip(lower=0)
    result = evaluation.copy()
    result["actual"] = labels.reindex(evaluation["target_month"]).to_numpy()
    result["dynamic_model"] = dynamic
    result["calendar_model"] = fixed.reindex(evaluation["target_month"]).to_numpy()
    result["seasonal_mean"] = evaluation["target_month"].dt.month.map(means)
    result["seasonal_median"] = evaluation["target_month"].dt.month.map(medians)
    bundle = {"pipeline":model,"normals":normals,"feature_columns":X_train.columns.tolist(),"target":target,
        "spi_reference":fit_reference(monthly),"trained_targets_through":str(allowed_months.max().date()),
        "seasonal_median":medians,"protocol":PROTOCOL}
    return result,bundle


def summarize(frame,target,split):
    rows=[]
    for (day,delay), group in frame.groupby(["issue_day","delay_days"]):
        for method in ["dynamic_model","calendar_model","seasonal_mean","seasonal_median"]:
            if day<10 and method=="calendar_model":
                continue
            rows.append({"target":target,"split":split,"issue_day":int(day),"delay_days":int(delay),"approach":method,
                "target_months":group["target_month"].nunique(),
                "mae":mean_absolute_error(group["actual"],group[method]),
                "rmse":root_mean_squared_error(group["actual"],group[method]),
                "bias":float((group[method]-group["actual"]).mean())})
    return pd.DataFrame(rows)


def predict_dynamic(available_daily,nao,as_of,target="rainfall"):
    issue=pd.Timestamp(as_of).normalize()
    available=available_daily.loc[:issue]
    cutoff=available.dropna(subset=REQUIRED).index.max()
    month=issue.to_period("M").to_timestamp()+pd.offsets.MonthBegin(1)
    bundle=joblib.load(ARTIFACTS/f"{target}_dynamic"/"model.joblib")
    if pd.Timestamp(bundle["trained_targets_through"])+pd.offsets.MonthEnd(0)>cutoff:
        raise ValueError("This artifact was trained after the requested historical cutoff.")
    monthly=load_monthly()
    complete=monthly.loc[monthly["period_end"]<=cutoff]
    spi=calculate_spi(complete,bundle["spi_reference"])
    row=pd.DataFrame([{"target_month":month,"issue_date":issue,"cutoff":cutoff,"issue_day":issue.day,"delay_days":(issue-cutoff).days}])
    X=dynamic_features(available,rolling_daily(available),complete,spi,nao,row,bundle["normals"],target)
    value=float(bundle["pipeline"].predict(X[bundle["feature_columns"]])[0])
    if target=="rainfall":
        value=max(0,value)
    result={"target":target,"target_month":month.strftime("%Y-%m"),"as_of":str(issue.date()),"data_cutoff":str(cutoff.date()),
        "last_30_days_start":str((cutoff-pd.Timedelta(days=29)).date()),"prediction":round(value,4),
        "units":"mm/month" if target=="rainfall" else "SPI units","mode":"archived_data_demo"}
    if target=="spi":
        result["estimated_category"]=category(value)
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"protocol.json").write_text(json.dumps(PROTOCOL,indent=2),encoding="utf-8")
    daily=pd.read_csv(PROCESSED/"daily.csv",parse_dates=["date"]).set_index("date")
    monthly=load_monthly()
    nao=pd.read_csv(PROCESSED/"nao.csv",parse_dates=["month"]).set_index("month")
    spi=calculate_spi(monthly,fit_reference(monthly))
    rolling=rolling_daily(daily)
    rows=snapshots(monthly)
    all_scores=[]
    for target in ["rainfall","spi"]:
        validation=[]
        for first,last in VALIDATION_WINDOWS:
            result,_=run_fold(daily,rolling,monthly,spi,nao,rows,target,first,last)
            validation.append(result)
            print(f"{target}: {first}–{last} evaluated",flush=True)
        validation=pd.concat(validation,ignore_index=True)
        benchmark,bundle=run_fold(daily,rolling,monthly,spi,nao,rows,target,*BENCHMARK)
        scores=pd.concat([summarize(validation,target,"rolling_validation"),summarize(benchmark,target,"known_benchmark")])
        all_scores.append(scores)
        folder=OUT/target
        folder.mkdir(exist_ok=True)
        validation.to_csv(folder/"validation_predictions.csv",index=False)
        benchmark.to_csv(folder/"benchmark_predictions.csv",index=False)
        scores.to_csv(folder/"scores.csv",index=False)
        artifact=ARTIFACTS/f"{target}_dynamic"
        artifact.mkdir(parents=True,exist_ok=True)
        joblib.dump(bundle,artifact/"model.joblib")
        print(scores[(scores["split"]=="known_benchmark") & (scores["delay_days"]==5)].round(3).to_string(index=False),flush=True)
    pd.concat(all_scores).to_csv(OUT/"scores.csv",index=False)
    for target in ["rainfall","spi"]:
        demo=predict_dynamic(daily.loc[:"2025-11-20"],nao,"2025-11-25",target)
        (OUT/f"{target}_demo.json").write_text(json.dumps(demo,indent=2),encoding="utf-8")
        print(json.dumps(demo,indent=2),flush=True)


if __name__=="__main__":
    main()
