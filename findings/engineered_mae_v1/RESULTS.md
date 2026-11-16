# Rainfall feature engineering and MAE-aligned training

The requested engineered features were implemented and evaluated alongside
MAE-aligned training. Monthly improvements were small. Weekly MAE fell
substantially, but forecasts became systematically too dry and RMSE increased.
None of these experiments achieved 8 mm monthly MAE.

## Evaluation

Data and delayed-input timing match the previous 1996–2025 experiments at the
single Marrakech point. Candidate choice now uses pooled, chronological
validation windows 2016–2017, 2018–2019, 2020–2021, 2022–2023. Each fold refits
models and all seasonal normals using only that fold's fitted history. Training
target periods end by the first validation target's observation cutoff. No
random split. The existing 2024–2025 period is an already examined exploratory
benchmark, not an independent final test. No hyperparameters were adjusted after
viewing this experiment's benchmark results.

## Requested engineered features

- Recent rainfall minus the fitted historical normal for its source calendar
  month. Normals use observed periods ending by the fold cutoff.
- Recent temperature minus its similarly fitted calendar-month normal.
- Pressure and humidity changes between lag-two and lag-three periods.
- Number of >=1 mm rainy days in the lag-two source period.
- Longest consecutive run of <1 mm days within that source period; runs do not
  cross the period boundary. This threshold is an explicit experiment choice.
- Available NAO index multiplied by the target season's sine and cosine.
- Original rainfall features retained for controlled comparison.

Monthly versus weekly periods preserve their original definitions. NOAA monthly
indices retain the earlier assumed month-end +15-day publication rule and are
never backward-interpolated. This is a retrospective experiment using revised
observations and climate-index climatologies, not a vintage operational replay.

## Models

Original squared-error forest; absolute-error forest; absolute-error histogram
gradient boosting; scaled Ridge; an absolute-error boosting residual forecast
that adds back a training-only seasonal mean. Original-feature MAE models are
included to separate the effect of changing the loss from engineering features.
Baselines include calendar-month means, medians, lag-two persistence, and the
previous smoothed weekly seasonal mean. Configuration is in protocol.json.

## Main results

| Approach | Rolling-validation MAE | Known-benchmark MAE | Known-benchmark RMSE |
| --- | ---: | ---: | ---: |
| Monthly original forest | 18.124 | 16.339 | 27.657 |
| Monthly engineered MAE forest, validation-selected ML | 17.426 | 16.163 | 27.683 |
| Monthly seasonal median, validation-selected overall | 17.355 | 16.249 | 27.919 |
| Weekly original forest | 6.453 | 6.070 | 9.776 |
| Weekly original-feature MAE boosting, validation-selected ML | 5.321 | 4.708 | 10.610 |
| Weekly seasonal median, validation-selected overall | 5.223 | 4.707 | 10.940 |

Values are mm per corresponding target period. Do not directly rank weekly and
monthly errors. The selected monthly ML candidate improves benchmark MAE by
about 1.1% versus the previous forest. The selected weekly ML candidate improves
MAE by about 22.4%, while RMSE worsens by about 8.5%. Its mean prediction bias
is -3.504 mm/week versus +0.313 for the original forest. It therefore should not
be promoted as a generally more accurate water-budget forecast merely because
its MAE is lower. The median baseline is still competitive or better.

The original-feature monthly MAE forest happened to score 15.669 mm on the known
benchmark, but it was not the validation-selected model. It must not be reported
as an independently validated winner. All candidate scores remain in scores.csv.

## Outputs

The existing API and rainfall_ridge_v1 artifact were not modified. Each frequency
directory contains raw features, index availability audit, rolling and benchmark
predictions, selection metadata, and selected_ml.joblib. The artifact contains
the fitted model and training normals; reproducing serving requires applying
the same feature builder and any residual seasonal adjustment, not simply
passing the original seven input columns.

Reproduce from the project root:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 uv run python -m droughtproject.improve_features
uv run python -m unittest discover -s tests -v
```
