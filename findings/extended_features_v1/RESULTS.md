# Ocean and atmospheric feature experiments

These particular lagged climate indices and local weather summaries did not
materially improve the original 30-year rainfall models. The weekly NAO addition
gave a negligible MAE change; the monthly local-weather addition was essentially
tied with the rainfall-only forest. This does not show that all ocean or
atmospheric predictors are useless, nor that fresh professional forecasts lack
value. We tested delayed historical summaries, not global forecast fields.

## Results on the known 2024–2025 benchmark

All rows below use the original fixed Random Forest settings. The added-feature
configuration selected on validation was local weather for monthly targets and
NAO for weekly targets. No selection or tuning used benchmark scores.

| Added features | Monthly MAE mm | Weekly MAE mm |
| --- | ---: | ---: |
| None, original rainfall features | 16.339 | 6.070 |
| NAO circulation index | 16.427 | 6.064 |
| Nino3.4 and tropical North Atlantic SST anomalies | 16.928 | 6.286 |
| All three climate indices | 16.776 | 6.313 |
| Local temperature, humidity, wind, pressure and solar history | 16.355 | 6.200 |
| All additions | 16.555 | 6.347 |

The validation-selected monthly forest has RMSE 27.314 mm, versus 27.657 mm for
the rainfall-only forest, but slightly worse MAE. The weekly NAO forest's RMSE
is 9.777 versus 9.776 mm: also effectively unchanged. Monthly and weekly errors
cannot be directly ranked because the target periods differ.

The reference MAEs remain 17.831 mm monthly and 6.294 mm weekly. The selected
models improve on those respective references by 8.28% and 3.66%, but the
original ten-year monthly seasonal reference scored 16.377 mm, almost tied with
the expanded monthly model. No statistical significance is claimed.

## Data and availability

- Rainfall: existing validated 1996–2025 NASA archive, same demonstration point.
- Local NASA covariates: T2M, RH2M, WS2M, PS, ALLSKY_SFC_SW_DWN, daily UTC.
  10,958 daily rows passed calendar, missing/nonfinite and basic physical-range
  checks. Source responses and metadata are cached; no imputation.
- NOAA PSL NAO: https://psl.noaa.gov/data/correlation/nao.data
- NOAA PSL Nino3.4: https://psl.noaa.gov/data/correlation/nina34.anom.data
- NOAA PSL tropical North Atlantic: https://psl.noaa.gov/data/correlation/tna.data
- Each index contributes its latest assumed-available monthly value and a
  trailing three-month mean. No centered ONI, future interpolation, backward
  filling or daily fake ocean observations. Monthly indices can repeat across
  weekly inputs without becoming independent new ocean observations.
- Local weather contributes means at lags two and three target periods.
- Index availability is ASSUMED to be 15 days after month end. Monthly forecasts
  issue on the 10th of the preceding month; weekly forecasts issue on the target
  Monday. Source periods must also end by the original rainfall input cutoff.
  October indices are therefore not used for a December outlook issued November
  10 under this assumption. The per-target availability_audit.csv records this.
- This publication allowance is a conservative experiment rule, not verified
  historical release dates. Current revised indices and their climatological
  anomaly reference periods were used. These results are not an operational
  as-issued hindcast; historical revisions/reference climatologies can introduce
  retrospective information. An operational skill claim needs vintage data.

## Evaluation and artifacts

Six predeclared feature sets, two original fixed models, and two frequencies
were evaluated. Validation is 2022–2023; the repeatedly inspected 2024–2025 years
are a known exploratory benchmark, not a new blind test. Training labels use
the same purged availability cutoffs as the previous experiment. All variants
retain the same evaluation targets. No post-result tuning was performed.

The existing API and deployed Ridge artifact were not changed. New selected
artifacts, features, source hashes, timing audits, per-target predictions and
all scores are under this experiment directory.

To reproduce from the project root:

```sh
uv run python -m droughtproject.fetch_extended
uv run python -m droughtproject.compare_extended
uv run python -m unittest discover -s tests -v
```

The first command caches sources. Delete/refresh source files deliberately if
you want a new snapshot; repeating the experiment uses the saved responses.

## Recommended demo design

Use a current external forecast for the live seven-day farm report, and keep
the trained local model as a separately labelled experimental comparison.
Current forecasts, historical observations, local-model outputs, historical
averages and simulated demo scenarios should be distinguishable in the UI and
API. Include source, retrieval time, valid period, observation cutoff, model
version where applicable, and any fallback reason.

If a forecast source fails, use only a cached forecast still covering the
requested period, with its age visible. Otherwise return an explicitly labelled
seasonal planning estimate or show that a current forecast is unavailable.
Do not re-label an expired prediction as current or assign invented confidence
percentages. Blending estimates requires a documented rule and evaluation.

Provider forecasts may be used directly for a farm report. Using them as inputs
to our trained model instead of the historical observation features would change
the input distribution and require corresponding archived-forecast training and
evaluation. Integration does not establish that we trained the provider's model.
