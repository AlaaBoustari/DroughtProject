# Archived professional forecast inputs and local calibration

Actual archived NOAA CFSv2 monthly forecasts were downloaded and added to local
rainfall predictions. They did not establish a decisive improvement. The
forecast-enhanced ML candidate selected on validation scored 15.679 mm MAE on
the known benchmark, but performed worse than the local historical-feature
control on rolling validation and had substantially worse benchmark RMSE.

## Forecast archive and extraction

- Source: NOAA operational CFSv2 forecasts in the public noaa-cfs-pds S3 bucket,
  https://registry.opendata.aws/noaa-cfs/ . These are operational forecast model
  outputs, not observations or a stitched near-analysis historical API.
- 83 target months: February 2019–December 2025. Every target has four archived
  forecasts: member 01 at 00,06,12,18 UTC on day 1 of its preceding month.
  Total: 332 forecast GRIB messages. This is a small four-run combination, not
  the full CFS ensemble, and its spread is not a calibrated confidence interval.
- Target issue date is day 10 of the preceding month. Reference dates are
  strictly before issue date and issue date is before target month. The nine-day
  allowance avoids assuming instantaneous publication. Actual historical
  dissemination logs were not independently reconstructed; object timestamps
  are saved as provenance and may reflect archive handling.
- Only the PRATE surface message is downloaded using its GRIB inventory byte
  offsets; metadata checks reference date/time, mean statistic, monthly unit,
  one-month interval length, forecast month offset, variable and units.
- CFS calendar-month forecastTime is used to match target month. Generic
  ecCodes start/endStep converts months to fixed 30-day intervals and is not
  suitable for deriving calendar-month boundaries here. The supplied end-of-
  overall-interval metadata also retains the initialization date in inspected
  messages, so it is not used as a valid-date shortcut.
- Precipitation rate kg m^-2 s^-1 is converted to monthly mm by multiplying by
  86400 and the number of days in the target month. Nearest forecast grid point
  is approximately latitude 31.6534, longitude 351.5620, about 43 km from the
  requested point. This differs from NASA's source grid and a farm rain gauge.
- Raw messages, inventory/message hashes, URLs, GRIB metadata and nearest-point
  information are retained in data/raw/cfsv2 and source_manifest.json.
- ecCodes Python bindings and native library were added to pyproject.toml and
  uv.lock to decode the GRIB format. No external service credentials required.

## Comparison protocol

Archive coverage does not extend through all thirty years. Local rainfall,
weather and seasonal-normal context retain the original long history. Forecast
calibrators use only months that have actual archived forecast inputs.

Rolling validation uses 2021, 2022 and 2023 as separate one-year windows. The
calibration fit has 22,34,46 rows respectively. The 2024–2025 known benchmark
uses 58 fitted calibration rows. All target labels are purged to be available
by the first target's input cutoff; no random split or contemporaneous target
observations are passed as forecast inputs.

Candidates are the raw four-run mean, global median-bias correction, Ridge,
median quantile regression, MAE forest/boosting with original engineered
features plus forecast mean/spread. Comparators include seasonal means/medians
from the same short label history and from all available long history, plus the
long-history engineered MAE forest. Every approach is scored on identical
target months. The extra forecast information is tested against an independently
available professional forecast; no promise was made that it improves MAE.

## Results

| Approach | Rolling-validation MAE | Known-benchmark MAE | Known-benchmark RMSE |
| --- | ---: | ---: | ---: |
| Raw CFSv2 four-run mean | 25.932 | 17.838 | 31.327 |
| Forecast + engineered MAE boosting, selected forecast ML | 17.961 | 15.679 | 31.811 |
| Long-history engineered control, selected overall | 17.093 | 16.163 | 27.683 |
| Long-history seasonal median | 17.353 | 16.249 | 27.919 |
| Short-history seasonal median | 20.046 | 14.589 | 27.683 |

All values are mm/month. A forecast-enhanced forest happened to score 15.490 mm
on the known benchmark, but its worse rolling-validation score did not select
it. Likewise the short-history median's favourable benchmark score must not be
used to claim retrospective selection success. All candidate results are saved.

The selected forecast-enhanced model reduced benchmark MAE by about 3.0%
relative to the historical engineered control, but increased RMSE by about
14.9% and did not beat the control in rolling validation. It has not reached
8 mm/month and has not demonstrated that it should replace the existing model.

This is a limited single-point/model/run-selection pilot. It does not establish
the accuracy of professional forecasting generally. 2024–2025 has already been
examined repeatedly, and recent historical rainfall targets are gridded NASA
estimates rather than independent local measurements. Proper fresh evaluation
and appropriate forecast ensembles are needed before stronger skill claims.

## Reproduction

```sh
uv run python -m droughtproject.fetch_cfsv2
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 uv run python -m droughtproject.calibrate_forecasts
uv run python -m unittest discover -s tests -v
```

Each downloader reuses cached messages. Raw requests use bounded concurrency
and download only the needed rainfall field, rather than full global products.
The API and its existing deployed artifact were not replaced. A selected
forecast-ML candidate, predictions, scores and selection metadata are saved
separately in this directory.
