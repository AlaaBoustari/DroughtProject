# ////////////////////////////////////////////////////////////////////////////
# // 1. Reads prepared monthly weather, NAO, and historical SPI-3 values.
# // 2. Builds monthly lagged inputs using observations ending two months earlier.
# // 3. Fits seasonal normals on training history only and creates rainfall anomalies.
# // 4. Returns the same ordered input columns for training and later inference.
# ////////////////////////////////////////////////////////////////////////////
import numpy as np
import pandas as pd

from droughtproject.settings import MODEL_HISTORY_START, MODEL_TARGET_START

RAINFALL_COLUMNS = [
    "rainfall_latest_mm",
    "rainfall_previous_mm",
    "rainfall_older_mm",
    "rainfall_three_month_total_mm",
    "rainfall_same_month_last_year_mm",
    "month_sin",
    "month_cos",
    "recent_rainy_days",
    "recent_dry_spell",
    "pressure_change",
    "humidity_change",
    "nao_season_sin",
    "nao_season_cos",
    "climate_nao",
    "rainfall_anomaly",
    "temperature_anomaly",
]
SPI_COLUMNS = [
    "spi_latest",
    "spi_previous",
    "spi_older",
    "rainfall_latest_mm",
    "rainfall_three_month_total_mm",
    "month_sin",
    "month_cos",
]


def cutoff_for(month):
    return pd.Timestamp(month) - pd.offsets.MonthBegin(1) - pd.Timedelta(days=1)


def fit_normals(monthly, cutoff):
    available = monthly.loc[
        (monthly.index.year >= MODEL_HISTORY_START) & (monthly["period_end"] <= cutoff)
    ]
    result = available.groupby(available.index.month)[
        ["rainfall_mm", "temperature_c"]
    ].mean()
    if len(result) != 12 or result.isna().any().any():
        raise ValueError("Training history lacks complete seasonal normals.")
    return result


def climate_inputs(index, nao):
    source = nao.copy()
    source["source_end"] = source.index + pd.offsets.MonthEnd(0)
    source["available_at"] = source["source_end"] + pd.Timedelta(days=15)
    requests = pd.DataFrame(
        {
            "target_month": index,
            "issue_date": index - pd.offsets.MonthBegin(1) + pd.Timedelta(days=9),
        }
    )
    matched = (
        pd.merge_asof(
            requests.sort_values("issue_date"),
            source.reset_index(drop=True).sort_values("available_at"),
            left_on="issue_date",
            right_on="available_at",
            direction="backward",
        )
        .set_index("target_month")
        .reindex(index)
    )
    relevant = matched.index >= pd.Timestamp(MODEL_TARGET_START)
    if (
        matched.loc[relevant, "nao"].isna().any()
        or not (
            matched.loc[relevant, "source_end"] <= cutoff_for_index(index[relevant])
        ).all()
    ):
        raise ValueError(
            "NAO feature has missing data or extends beyond the observation cutoff."
        )
    return matched["nao"]


def cutoff_for_index(index):
    return index - pd.offsets.MonthBegin(1) - pd.Timedelta(days=1)


def build_features(monthly, spi, nao, target, normals=None):
    rainfall = monthly["rainfall_mm"]
    table = pd.DataFrame(index=monthly.index)
    table["rainfall_latest_mm"] = rainfall.shift(2)
    table["rainfall_previous_mm"] = rainfall.shift(3)
    table["rainfall_older_mm"] = rainfall.shift(4)
    table["rainfall_three_month_total_mm"] = (
        rainfall.rolling(3, min_periods=3).sum().shift(2)
    )
    angle = 2 * np.pi * (table.index.month - 1) / 12
    table["month_sin"], table["month_cos"] = np.sin(angle), np.cos(angle)
    if target == "spi":
        table["spi_latest"], table["spi_previous"], table["spi_older"] = (
            spi.shift(2),
            spi.shift(3),
            spi.shift(4),
        )
        return table[SPI_COLUMNS]
    if target != "rainfall" or normals is None:
        raise ValueError(
            "Rainfall requires fitted normals; supported targets are rainfall and spi."
        )
    table["rainfall_same_month_last_year_mm"] = rainfall.shift(12)
    table["recent_rainy_days"] = monthly["rainy_days"].shift(2)
    table["recent_dry_spell"] = monthly["longest_dry_spell"].shift(2)
    table["pressure_change"] = monthly["pressure_kpa"].shift(2) - monthly[
        "pressure_kpa"
    ].shift(3)
    table["humidity_change"] = monthly["humidity_pct"].shift(2) - monthly[
        "humidity_pct"
    ].shift(3)
    table["climate_nao"] = climate_inputs(table.index, nao)
    table["nao_season_sin"] = table["climate_nao"] * table["month_sin"]
    table["nao_season_cos"] = table["climate_nao"] * table["month_cos"]
    source_month = (table.index - pd.offsets.MonthBegin(2)).month
    table["rainfall_anomaly"] = (
        table["rainfall_latest_mm"]
        - source_month.map(normals["rainfall_mm"]).to_numpy()
    )
    table["temperature_anomaly"] = (
        monthly["temperature_c"].shift(2)
        - source_month.map(normals["temperature_c"]).to_numpy()
    )
    return table[RAINFALL_COLUMNS]
