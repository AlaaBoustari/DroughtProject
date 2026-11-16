# ////////////////////////////////////////////////////////////////////////////
# // 1. Loads a trusted local fitted artifact and prepared monthly observations.
# // 2. Rebuilds exactly the training features for one requested target month.
# // 3. Rejects missing, unavailable, or in-sample inputs instead of inventing them.
# // 4. Returns a dated rainfall or direct SPI forecast with seasonal comparison.
# ////////////////////////////////////////////////////////////////////////////
import json

import joblib
import numpy as np
import pandas as pd

from droughtproject.settings import ARTIFACTS, PROCESSED, SCHEMA_VERSION
from droughtproject.prepare import load_monthly
from droughtproject.features import build_features, cutoff_for
from droughtproject.spi import calculate_spi, category


def predict(target, month):
    date = pd.Timestamp(f"{month}-01")
    bundle = joblib.load(ARTIFACTS / target / "model.joblib")
    metadata = bundle["metadata"]
    if metadata["schema_version"] != SCHEMA_VERSION or metadata["target"] != target:
        raise ValueError("Artifact schema/target mismatch.")
    cutoff = cutoff_for(date)
    trained = pd.Timestamp(bundle["trained_targets_through"]) + pd.offsets.MonthEnd(0)
    if trained > cutoff:
        raise ValueError(
            "Requested forecast precedes this model's available training-label cutoff."
        )
    monthly = load_monthly()
    if cutoff > monthly["period_end"].max():
        raise ValueError(
            f"Need complete observations through {cutoff:%Y-%m}; current archive ends {monthly.index.max():%Y-%m}."
        )
    monthly = monthly.loc[monthly["period_end"] <= cutoff]
    index = pd.date_range(monthly.index.min(), date, freq="MS")
    monthly = monthly.reindex(index)
    nao = pd.read_csv(PROCESSED / "nao.csv", parse_dates=["month"]).set_index("month")
    spi = calculate_spi(monthly, bundle["spi_reference"])
    features = build_features(monthly, spi, nao, target, bundle["normals"])
    if features.columns.tolist() != bundle["feature_columns"]:
        raise ValueError("Feature schema differs from the trained model.")
    row = features.loc[[date], bundle["feature_columns"]]
    if not np.isfinite(row.to_numpy()).all():
        raise ValueError("Missing required forecast inputs.")
    value = float(bundle["pipeline"].predict(row)[0])
    if target == "rainfall":
        value = max(0, value)
    result = {
        "target": target,
        "target_month": month,
        "prediction": round(value, 4),
        "units": metadata["units"],
        "observations_through": cutoff.strftime("%Y-%m-%d"),
        "mode": "archived_inputs",
        "location": metadata["location"],
        "trained_targets_through": metadata["trained_targets_through"],
        "model": metadata["model"],
        "seasonal_median": round(float(bundle["seasonal_median"].loc[date.month]), 4),
    }
    if target == "spi":
        result["estimated_category"] = category(value)
    return result


if __name__ == "__main__":
    for target in ["rainfall", "spi"]:
        print(json.dumps(predict(target, "2025-12"), indent=2))
