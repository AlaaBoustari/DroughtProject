# Dynamic rolling-window rainfall and SPI

The requested moving-cutoff design is implemented in src/droughtproject/dynamic.py.
The model predicts the next calendar month, while its input windows move backward
from the latest available complete daily record. The original static artifacts
remain unchanged. No new algorithm or tuning search was added.

## Features and data

The existing NASA daily archive is used with the strongest previously justified
data sources: rainfall, temperature, humidity, pressure and NOAA NAO. Wind,
solar and ocean-temperature indices are not reintroduced after their weak earlier
results. Inputs include rainfall over 7/30/90 days, previous non-overlapping
30-day blocks, a 30-day total 365 days earlier, rainy-day counts, longest dry
run within 30 days, recent weather averages/changes, seasonal anomalies, NAO
seasonal interactions, target-month sine/cosine, lead time and data age. The
365-day feature is not an exact calendar-year match in leap years.

Seasonal normals are fitted only on available training history. Expected
30-day rainfall sums training daily month-of-year normals across the actual
window, including month boundaries. NAO retains the assumed month-end +15-day
availability rule. SPI adds the latest three completed calendar-month SPI
values; the fixed 1982–2011 reference remains unchanged. Monthly SPI is not
relabelled as an observed rolling 90-day SPI.

## Evaluation

- Fixed existing absolute-error Random Forest settings.
- Issue days 5/10/15/20/25 of the preceding month; simulated delays 3/5/7 days.
- Validation windows 2016–2017, 2018–2019, 2020–2021, 2022–2023.
- Known benchmark 2024–2025. This is still not a fresh blind test.
- All snapshots predicting the same monthly answer stay in the same split.
- Training labels end by the earliest cutoff of that evaluation window. A
  partially complete November therefore cannot become a training answer.
- Normals and models remain fixed within a window; inputs advance over time.
- The calendar model is refitted on the same permitted training-label months,
  so its result differs slightly from the original 16.16 mm result. Its nominal
  issue date is the 10th; it is not scored as an available baseline on day 5.
- Seasonal baselines use unique training months, not repeated snapshot labels.
- Each issue/delay cell has 96 validation target months or 24 benchmark target
  months. Repeated snapshots are correlated, not independent new answers.

## Overall matched comparison

These averages cover issue days 10/15/20/25 and all three delay assumptions,
giving equal weight to each requested forecast snapshot. They do not average
several predictions into a new forecast. There are still only 24 distinct
benchmark months.

| Target and split | Calendar model MAE | Dynamic model MAE |
| --- | ---: | ---: |
| Rainfall, rolling validation | 17.496 mm | 17.326 mm |
| Rainfall, known benchmark | 16.244 mm | 15.631 mm |
| SPI, rolling validation | 0.863 | 0.809 |
| SPI, known benchmark | 0.736 | 0.739 |

Rainfall improves about 1.0% in validation and 3.8% on the known benchmark.
SPI improves about 6.2% in validation but is approximately tied/slightly worse
overall on the known benchmark. There is no universal improvement at every
issue date, nor a result near 8 mm/month.

## Five-day delay example on known benchmark

| Issue day | Rainfall dynamic MAE mm | Calendar MAE mm | SPI dynamic MAE | Calendar SPI MAE |
| --- | ---: | ---: | ---: | ---: |
| 10 | 18.632 | 16.244 | 0.772 | 0.736 |
| 15 | 15.241 | 16.244 | 0.775 | 0.736 |
| 20 | 15.250 | 16.244 | 0.723 | 0.736 |
| 25 | 15.500 | 16.244 | 0.695 | 0.736 |

For the 25th/five-day-delay example, rainfall validation MAE was 17.846 versus
17.496 for the calendar control: its benchmark gain did not persist across
all validation periods. Do not select a favourable issue date from this table
and describe it as independently proven optimal. All cells, RMSE and bias are
saved in scores.csv. No statistical significance is claimed.

## Inference

predict_dynamic accepts available daily history (including enough past rainfall
for the year-earlier window), NAO data, an as-of date, and a target name. It finds
the latest common usable weather date at/before as-of, derives the next calendar
month and rebuilds the same training features. It does not subtract a fixed
delay from real supplied data. The demo truncates the archived input explicitly
to simulate publication delay. A live caller must provide cached history plus
fresh API records; this experiment does not download live 2026 data.

The replay as of November 25, 2025 with data ending November 20 uses the latest
30-day window October 22–November 20. December forecasts are 35.3582 mm rainfall
and -0.3915 SPI, both labelled archived-data demo outputs.

Reproduce:

```sh
uv run python -m droughtproject.dynamic
```

This rebuilds candidates and per-snapshot evaluations without modifying the
original rainfall/SPI artifacts or adding tests, CLI wrappers or frameworks.
