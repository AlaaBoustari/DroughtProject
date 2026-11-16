# ////////////////////////////////////////////////////////////////////////////
# // 1. Defines the demonstration location and NASA parameter names.
# // 2. Defines fixed history, SPI reference, and chronological evaluation dates.
# // 3. Supplies shared paths and settings to every pipeline stage.
# ////////////////////////////////////////////////////////////////////////////
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw" / "nasa"
PROCESSED = DATA / "processed" / "marrakech"
ARTIFACTS = ROOT / "artifacts"
LOCATION = {
    "name": "Marrakech demonstration point",
    "latitude": 31.6295,
    "longitude": -7.9811,
}
ENDPOINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
NAO_URL = "https://psl.noaa.gov/data/correlation/nao.data"
PARAMETERS = {
    "PRECTOTCORR": ("rainfall_mm", "mm/day"),
    "T2M": ("temperature_c", "C"),
    "RH2M": ("humidity_pct", "%"),
    "WS2M": ("wind_ms", "m/s"),
    "PS": ("pressure_kpa", "kPa"),
    "ALLSKY_SFC_SW_DWN": ("solar_mj_m2_day", "MJ/m^2/day"),
}
ARCHIVE_START = 1981
MODEL_HISTORY_START = 1996
MODEL_TARGET_START = "1997-01-01"
ARCHIVE_END = 2025
SPI_REFERENCE = ("1982-01-01", "2011-12-01")
VALIDATION_WINDOWS = [(2016, 2017), (2018, 2019), (2020, 2021), (2022, 2023)]
BENCHMARK = (2024, 2025)
SCHEMA_VERSION = 1
