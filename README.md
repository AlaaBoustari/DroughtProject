# Marrakech rainfall and SPI

Monthly rainfall and direct SPI-3 prediction for one Marrakech point.
Both use the existing MAE Random Forest. 

## Run

```sh
uv sync --locked
uv run python -m droughtproject.download
uv run python -m droughtproject.prepare
uv run python -m droughtproject.train
uv run python -m droughtproject.predict
```

Downloads reuse saved files. Training builds both models. Prediction currently
prints both results for December 2025; change that month at the bottom of
`src/droughtproject/predict.py`.

## Code

| File | Job |
| --- | --- |
| `settings.py` | Location, dates, paths and NASA variables |
| `download.py` | Fetch yearly NASA data and the NOAA NAO index |
| `prepare.py` | Validate daily records and produce monthly tables |
| `features.py` | Build lagged rainfall/weather/SPI inputs and seasonal features |
| `spi.py` | Calculate historical SPI-3 using the fixed 1982–2011 reference |
| `train.py` | Train, evaluate against baselines and save models/results |
| `predict.py` | Load models and predict a chosen month |

## Folders

- `data/`: original downloads and prepared CSVs.
- `artifacts/rainfall/`, `artifacts/spi/`: fitted models, metadata and predictions.
- `findings/`: experiment reports and metrics.
- `archive/`: previous prototype, including the old API and research scripts.

Model history is 1996–2025; older rainfall supports the SPI reference. A December
forecast uses completed observations through October. Seasonal normals are
fitted on training history only. Validation uses chronological windows from
2016–2023; 2024–2025 is our already-examined benchmark, not a fresh blind test.
Predictions use archived data and remain experimental.

## Dynamic input windows

```sh
uv run python -m droughtproject.dynamic
```

This trains rolling-window rainfall/SPI candidates and compares them with the
calendar models at several issue dates and data delays. Results go to
`findings/dynamic_windows/`; artifacts go to `artifacts/rainfall_dynamic/` and
`artifacts/spi_dynamic/`. Original artifacts are retained.

`predict_dynamic(available_daily, nao, as_of, target)` in `dynamic.py` uses the
latest common usable date in the supplied daily history. Pass cached history
combined with newly fetched records; the same model supports changing cutoffs.
The included demo supplies records through November 20 on November 25, 2025.
Publication delays in historical evaluation are simulated, not measured releases.

## Marrakech–Safi regional rainfall

`uv run python -m droughtproject.regional` downloads 22 overlapping NASA cells and compares one shared rainfall forest with/without coordinates and source elevation. Tables and scores: `findings/regional/`. Uses next-month forecasts issued on day 25 with a simulated five-day data delay. SPI remains the single-point prototype.
