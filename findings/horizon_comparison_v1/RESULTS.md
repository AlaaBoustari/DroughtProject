# Marrakech rainfall horizon comparison

Thirty years of local rainfall history produced modest improvements with the
fixed Random Forest setup. Weekly aggregation provided more training rows but
did not demonstrate a large improvement over seasonal averages. This is one
location and one previously examined benchmark period, not evidence of reliable
farm-level forecasting.

## Results

Models were selected by validation MAE on 2022–2023 before scoring the known
2024–2025 benchmark. Positive skill means lower MAE than the reference selected
on validation for that experiment.

| History and target | Selected ML model | Benchmark MAE mm | Reference MAE mm | MAE improvement | Benchmark RMSE mm |
| --- | --- | ---: | ---: | ---: | ---: |
| 10 years monthly | Ridge | 18.858 | 16.377 | -15.15% | 29.019 |
| 30 years monthly | Random Forest | 16.339 | 17.831 | 8.37% | 27.657 |
| 10 years weekly | Random Forest | 6.196 | 6.181 | -0.24% | 9.996 |
| 30 years weekly | Random Forest | 6.070 | 6.294 | 3.56% | 9.776 |

The 30-year monthly forest is almost tied with the stronger 10-year monthly
seasonal reference: 16.339 versus 16.377 mm MAE, a difference of only 0.038 mm.
Thus the 8.37% gain over its own baseline should not be interpreted as a major
gain over the existing best simple method. The 30-year weekly forest improves
on the 10-year weekly seasonal reference by about 1.80%.

Monthly and weekly MAE values describe different target durations and must not
be directly ranked. Differences here are point estimates; no statistical
significance or calibrated prediction interval is claimed.

## Fixed protocol

- Location: the original point, latitude 31.6295, longitude -7.9811.
- NASA POWER PRECTOTCORR, daily UTC. All 10,958 days from 1996–2025 passed the
  existing date, unit, missing-value and nonnegative-value checks. No imputation.
- Existing 2016–2025 raw files were reused; 1996–2015 was downloaded. Raw-response
  hashes and declared NASA sources are recorded in source_manifest.json.
- Ten-year controls use 2016–2025; 30-year runs use 1996–2025. Initial history
  needed by features is not itself a usable supervised example.
- Monthly input features exactly reproduce the original prototype: rainfall
  lags 2/3/4, three-month sum ending at lag 2, lag 12, calendar sine and cosine.
- Weeks are non-overlapping Monday–Sunday. Incomplete boundary weeks are
  excluded. Weekly features use lags 2/3/4, three-week sum ending at lag 2,
  lag 52, and annual sine/cosine. Lag 52 means 364 days rather than an exact
  calendar-year match. This is a period-based analogue, not identical physical
  lookback duration to the monthly experiment.
- Weekly forecasts are issued on the target Monday, using observations through
  the Sunday eight days earlier. This assumes a seven-day publication allowance.
  A live pipeline must still verify actual availability; current historical
  responses do not establish what data revisions existed at each past issue date.
- Monthly seasonal baseline: mean training target rainfall for each calendar
  month. Weekly references considered: mean weekly rainfall by calendar month,
  and a seasonal mean smoothed over +/- 2.5/52 of the annual cycle. Both also
  compare lag-two persistence. The reference is chosen by validation MAE only.
- Fixed models: scaled Ridge alpha 10; Random Forest 200 trees, depth 3,
  minimum leaf size 5, seed 42. Negative model predictions floored at zero.
- Fit labels are purged to be available at the first forecast's input cutoff.
  No random temporal splitting and no benchmark-based tuning or model selection.
- Validation: 24 monthly targets or 104 weekly targets in 2022–2023. Known
  benchmark: 24 monthly targets or 104 complete weekly targets in 2024–2025.
- Monthly train/development examples: 59/83 for ten years, 299/323 for thirty.
  Weekly train/development examples: 260/364 for ten years, 1304/1408 for thirty.
- Models remain fixed within each evaluation period while available historical
  input features advance. Targets are NASA estimates, not farm rain-gauge truth.
- Previously inspected 2024–2025 scores remain an exploratory benchmark, not a
  fresh blind test. Results are not evidence of safe irrigation recommendations.

## Outputs and rerunning

Run from the project root:

```sh
uv run python -m droughtproject.compare_horizons
```

The downloader resumes using cached annual responses. The command rewrites this
experiment's generated scores/artifacts; it does not change the original API,
feature CSVs, or rainfall_ridge_v1 artifact.

- protocol.json: predetermined experiment definitions.
- source_manifest.json: raw file provenance and hashes.
- daily_1996_2025.csv: merged validated archive.
- scores.csv: validation and benchmark metrics for all approaches.
- run.json: sample counts, dates and library versions.
- Each case directory contains its features, per-target validation/benchmark
  predictions, model metadata, and validation-selected model artifact.

Check the calendar and leakage invariants with:

```sh
uv run python -m unittest discover -s tests -p 'test_horizon_comparison.py' -v
```

Additional verification: the rebuilt 10-year monthly features matched the
original feature CSV, and the original validation and Ridge benchmark scores
were reproduced. The original deployed artifact has not been replaced.
