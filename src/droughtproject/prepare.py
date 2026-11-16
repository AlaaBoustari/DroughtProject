# ////////////////////////////////////////////////////////////////////////////
# // 1. Reads annual NASA JSON files from data/raw/nasa and data/raw/nao.txt.
# // 2. Checks dates, units, missing values, finite numbers, and physical bounds.
# // 3. Aggregates complete months; calculates rainy days and within-month dry runs.
# // 4. Writes daily.csv, monthly.csv, nao.csv, and quality.json under data/processed.
# ////////////////////////////////////////////////////////////////////////////
import json

import numpy as np
import pandas as pd

from droughtproject.settings import (
    RAW,
    DATA,
    PROCESSED,
    PARAMETERS,
    ARCHIVE_START,
    ARCHIVE_END,
    MODEL_HISTORY_START,
)


def longest_dry(values):
    longest = run = 0
    for value in values:
        run = run + 1 if value < 1.0 else 0
        longest = max(longest, run)
    return longest


def parse_year(payload, year):
    if payload["header"]["time_standard"] != "UTC":
        raise ValueError(f"{year}: UTC is required.")
    codes = list(PARAMETERS) if year >= MODEL_HISTORY_START else ["PRECTOTCORR"]
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    expected = set(dates.strftime("%Y%m%d"))
    columns = {}
    for code in codes:
        name, units = PARAMETERS[code]
        if payload["parameters"][code]["units"] != units:
            raise ValueError(f"{year}/{code}: unexpected units.")
        values = payload["properties"]["parameter"][code]
        if set(values) != expected:
            raise ValueError(f"{year}/{code}: missing or unexpected dates.")
        if any(
            isinstance(v, bool) or not isinstance(v, (float, int))
            for v in values.values()
        ):
            raise ValueError(f"{year}/{code}: nonnumeric measurement.")
        series = pd.Series(values).reindex(dates.strftime("%Y%m%d"))
        numbers = series.to_numpy(dtype=float)
        if (
            not np.isfinite(numbers).all()
            or (numbers == payload["header"]["fill_value"]).any()
        ):
            raise ValueError(
                f"{year}/{code}: missing or nonfinite measurement; no automatic imputation."
            )
        if code in ["PRECTOTCORR", "WS2M", "ALLSKY_SFC_SW_DWN"] and (numbers < 0).any():
            raise ValueError(f"{year}/{code}: negative measurement.")
        if code == "RH2M" and ((numbers < 0) | (numbers > 100)).any():
            raise ValueError(f"{year}: humidity outside 0–100%.")
        if code == "PS" and (numbers <= 0).any():
            raise ValueError(f"{year}: invalid pressure.")
        columns[name] = numbers
    return pd.DataFrame(columns, index=dates)


def parse_nao(text):
    records = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 13 or not fields[0].isdigit():
            continue
        year = int(fields[0])
        if not 1900 <= year <= 2100:
            continue
        for month, raw in enumerate(fields[1:], 1):
            key = pd.Timestamp(year=year, month=month, day=1)
            if key in records:
                raise ValueError("Duplicate NAO month.")
            value = float(raw)
            records[key] = value if value > -90 and np.isfinite(value) else np.nan
    result = pd.Series(records, name="nao").sort_index()
    expected = pd.date_range("1995-01-01", f"{ARCHIVE_END}-12-01", freq="MS")
    if result.reindex(expected).isna().any():
        raise ValueError("Missing NAO observations in the required period.")
    return result.rename_axis("month").to_frame()


def prepare():
    frames = []
    for year in range(ARCHIVE_START, ARCHIVE_END + 1):
        path = RAW / f"{year}.json"
        frames.append(parse_year(json.loads(path.read_text()), year))
    daily = pd.concat(frames).rename_axis("date")
    expected = pd.date_range(f"{ARCHIVE_START}-01-01", f"{ARCHIVE_END}-12-31")
    if not daily.index.equals(expected):
        raise ValueError("Daily calendar is not unique and complete.")
    groups = daily.resample("MS")
    monthly = groups.mean()
    monthly["rainfall_mm"] = groups["rainfall_mm"].sum(min_count=1)
    monthly["days_recorded"] = groups["rainfall_mm"].count()
    if not monthly["days_recorded"].eq(monthly.index.days_in_month).all():
        raise ValueError("Incomplete month; aggregation stopped.")
    monthly["rainy_days"] = groups["rainfall_mm"].apply(
        lambda values: int((values >= 1).sum())
    )
    monthly["longest_dry_spell"] = groups["rainfall_mm"].apply(longest_dry)
    monthly["period_end"] = monthly.index + pd.offsets.MonthEnd(0)
    nao_path = DATA / "raw" / "nao.txt"
    nao = parse_nao(nao_path.read_text())
    PROCESSED.mkdir(parents=True, exist_ok=True)
    daily.to_csv(PROCESSED / "daily.csv", index_label="date", date_format="%Y-%m-%d")
    monthly.to_csv(
        PROCESSED / "monthly.csv", index_label="month", date_format="%Y-%m-%d"
    )
    nao.to_csv(PROCESSED / "nao.csv", index_label="month", date_format="%Y-%m-%d")
    quality = {
        "daily_rows": len(daily),
        "monthly_rows": len(monthly),
        "missing_required_values": 0,
        "imputation": "none",
        "rainy_day_threshold_mm": 1,
        "pre_1996_weather": "intentionally not downloaded; older rainfall supports SPI reference only",
        "units": {name: units for name, units in PARAMETERS.values()},
    }
    (PROCESSED / "quality.json").write_text(
        json.dumps(quality, indent=2), encoding="utf-8"
    )
    print(
        f"Prepared {len(daily)} daily rows and {len(monthly)} complete months.",
        flush=True,
    )


def load_monthly():
    frame = pd.read_csv(
        PROCESSED / "monthly.csv", parse_dates=["month", "period_end"]
    ).set_index("month")
    expected = pd.date_range(frame.index.min(), frame.index.max(), freq="MS")
    if frame.empty or not frame.index.equals(expected):
        raise ValueError("Prepared monthly calendar is invalid.")
    return frame


if __name__ == "__main__":
    prepare()
