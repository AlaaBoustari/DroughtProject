# Marrakech–Safi: shared rainfall model

22 NASA meteorological grid cells overlap the geoBoundaries Marrakech–Safi boundary. Edge cells may have centres outside the administrative boundary. Latitude, longitude and NASA source elevation are included in the daily, monthly and feature CSVs. Source elevation is not farm altitude.

Same rolling weather features and fixed Random Forest settings. Forecast issued on day 25, using data through day 20, for the next calendar month. All locations share chronological splits. This is one snapshot configuration, not the previous average over multiple issue dates/delays.

| Split | Approach | MAE mm/month | RMSE mm/month |
|---|---|---:|---:|
| known_benchmark | shared_no_location | 16.424 | 26.336 |
| known_benchmark | shared_coordinates | 16.423 | 26.336 |
| known_benchmark | shared_coordinates_elevation | 16.424 | 26.336 |
| known_benchmark | seasonal_mean | 19.967 | 28.925 |
| known_benchmark | seasonal_median | 16.782 | 26.961 |
| validation | shared_no_location | 18.543 | 29.335 |
| validation | shared_coordinates | 18.606 | 29.390 |
| validation | shared_coordinates_elevation | 18.569 | 29.358 |
| validation | seasonal_mean | 19.050 | 28.984 |
| validation | seasonal_median | 17.676 | 28.901 |

Coordinates/elevation do not improve this fixed shallow forest. The regional seasonal median is stronger on validation; the forest wins on the already-known 2024–2025 benchmark. Do not select a winner solely from that benchmark. Regional MAE averages cell-month errors, not rainfall averaged across the whole region. Neighboring cells and months are correlated. There is no held-out-location evaluation.

Only rainfall was extended in this experiment. The existing single-point SPI artifacts were not relabelled as regional.

Files: coordinates.csv, daily.csv, monthly.csv, feature_table.csv (date, cell, target, inputs and train/benchmark flag), predictions.csv, per_cell_scores.csv, scores.csv, protocol.json, and three shared forest artifacts. Each artifact stores per-cell training normals.

Run: `uv run python -m droughtproject.regional`

Boundary: geoBoundaries / OpenStreetMap, ODbL. Source URL and protocol are in protocol.json. NASA meteorology: 0.5° latitude × 0.625° longitude; adding farm altitude cannot create mountain detail absent from the source grid.
