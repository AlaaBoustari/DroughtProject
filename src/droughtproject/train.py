# ////////////////////////////////////////////////////////////////////////////
# // 1. Reads prepared monthly CSV files and the fixed historical SPI reference.
# // 2. Fits the existing MAE Random Forest on chronological training windows.
# // 3. Compares forecasts with seasonal and persistence baselines, without tuning.
# // 4. Saves fitted models, reference parameters, metrics, predictions.
# ////////////////////////////////////////////////////////////////////////////
import json
import platform
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from droughtproject.settings import (
    ROOT,
    ARTIFACTS,
    PROCESSED,
    VALIDATION_WINDOWS,
    BENCHMARK,
    MODEL_TARGET_START,
    SPI_REFERENCE,
    LOCATION,
    SCHEMA_VERSION,
)
from droughtproject.prepare import load_monthly
from droughtproject.spi import fit_reference, calculate_spi
from droughtproject.features import cutoff_for, fit_normals, build_features


def new_model():
    return RandomForestRegressor(
        n_estimators=200,
        criterion="absolute_error",
        max_depth=3,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=2,
    )


def ensure_finite(frame):
    if frame.empty or not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError(
            "Required model features/targets are empty or nonfinite; regenerate prepared data."
        )


def fit_window(monthly, spi, nao, target, first, last):
    evaluation_dates = monthly.index[
        (monthly.index.year >= first) & (monthly.index.year <= last)
    ]
    if len(evaluation_dates) != 12 * (last - first + 1):
        raise ValueError("Evaluation period does not contain every requested month.")
    cutoff = cutoff_for(evaluation_dates[0])
    training_dates = monthly.index[
        (monthly.index >= pd.Timestamp(MODEL_TARGET_START))
        & (monthly["period_end"] <= cutoff)
    ]
    if SPI_REFERENCE[1] >= str(cutoff.date()):
        raise ValueError("SPI calibration reference extends into an evaluation window.")
    normals = fit_normals(monthly, cutoff)
    features = build_features(monthly, spi, nao, target, normals)
    labels = monthly["rainfall_mm"] if target == "rainfall" else spi
    X_train, X_eval = features.loc[training_dates], features.loc[evaluation_dates]
    y_train, y_eval = labels.loc[training_dates], labels.loc[evaluation_dates]
    ensure_finite(X_train)
    ensure_finite(X_eval)
    ensure_finite(y_train.to_frame())
    ensure_finite(y_eval.to_frame())
    model = new_model()
    model.fit(X_train, y_train)
    predicted = model.predict(X_eval)
    if target == "rainfall":
        predicted = np.maximum(0, predicted)
    seasonal_mean = y_train.groupby(y_train.index.month).mean()
    seasonal_median = y_train.groupby(y_train.index.month).median()
    persistence_column = "rainfall_latest_mm" if target == "rainfall" else "spi_latest"
    results = pd.DataFrame(
        {
            "actual": y_eval,
            "model": predicted,
            "seasonal_mean": evaluation_dates.month.map(seasonal_mean).to_numpy(),
            "seasonal_median": evaluation_dates.month.map(seasonal_median).to_numpy(),
            "persistence": X_eval[persistence_column],
        },
        index=evaluation_dates,
    )
    bundle = {
        "pipeline": model,
        "normals": normals,
        "feature_columns": X_train.columns.tolist(),
        "seasonal_mean": seasonal_mean,
        "seasonal_median": seasonal_median,
        "trained_targets_through": str(training_dates.max().date()),
    }
    return results, bundle


def metrics(predictions, split, target):
    rows = []
    for approach in ["model", "seasonal_mean", "seasonal_median", "persistence"]:
        rows.append(
            {
                "target": target,
                "split": split,
                "approach": approach,
                "n": len(predictions),
                "mae": mean_absolute_error(
                    predictions["actual"], predictions[approach]
                ),
                "rmse": root_mean_squared_error(
                    predictions["actual"], predictions[approach]
                ),
                "bias": float((predictions[approach] - predictions["actual"]).mean()),
            }
        )
    return rows


def train(target="all"):
    monthly = load_monthly()
    nao = pd.read_csv(PROCESSED / "nao.csv", parse_dates=["month"]).set_index("month")
    reference = fit_reference(monthly)
    spi = calculate_spi(monthly, reference)
    spi.to_csv(PROCESSED / "spi.csv", index_label="month", date_format="%Y-%m-%d")
    (PROCESSED / "spi_reference.json").write_text(
        json.dumps(
            {
                "period": SPI_REFERENCE,
                "method": "zero-adjusted gamma MLE, standard normal transform",
                "parameters": reference,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    targets = ["rainfall", "spi"] if target == "all" else [target]
    for name in targets:
        directory = ARTIFACTS / name
        directory.mkdir(parents=True, exist_ok=True)
        validation_parts = []
        for first, last in VALIDATION_WINDOWS:
            result, _ = fit_window(monthly, spi, nao, name, first, last)
            validation_parts.append(result)
        validation = pd.concat(validation_parts)
        benchmark, bundle = fit_window(monthly, spi, nao, name, *BENCHMARK)
        scores = metrics(validation, "rolling_validation", name) + metrics(
            benchmark, "known_benchmark", name
        )
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "target": name,
            "units": "mm/month" if name == "rainfall" else "SPI units",
            "model": "random_forest_absolute_error",
            "model_parameters": {
                "trees": 200,
                "max_depth": 3,
                "min_samples_leaf": 5,
                "seed": 42,
            },
            "location": LOCATION,
            "status": "experimental",
            "feature_columns": bundle["feature_columns"],
            "trained_targets_through": bundle["trained_targets_through"],
            "validation_windows": VALIDATION_WINDOWS,
            "known_benchmark": BENCHMARK,
            "benchmark_warning": "Previously inspected years; not a new blind test.",
            "spi_reference_period": SPI_REFERENCE,
            "forecast_rule": "Target next calendar month on preceding month's 10th; observations through target minus two months.",
            "nao_availability": "Assumed month-end +15 days; rainfall feature only; revised historical index, no release-vintage replay.",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "versions": {
                "python": platform.python_version(),
                "scikit_learn": sklearn.__version__,
                "pandas": pd.__version__,
                "scipy": scipy.__version__,
                "joblib": joblib.__version__,
            },
            "metrics": scores,
        }
        bundle["metadata"] = metadata
        bundle["spi_reference"] = reference
        validation.to_csv(
            directory / "validation_predictions.csv",
            index_label="target_month",
            date_format="%Y-%m-%d",
        )
        benchmark.to_csv(
            directory / "benchmark_predictions.csv",
            index_label="target_month",
            date_format="%Y-%m-%d",
        )
        (directory / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        pd.DataFrame(scores).to_csv(directory / "metrics.csv", index=False)
        joblib.dump(bundle, directory / "model.joblib")
        findings = ROOT / "findings" / "current_pipeline" / name
        findings.mkdir(parents=True, exist_ok=True)
        (findings / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        pd.DataFrame(scores).to_csv(findings / "metrics.csv", index=False)
        print(f"\n{name.upper()}: fixed existing model, no tuning", flush=True)
        print(pd.DataFrame(scores).round(3).to_string(index=False), flush=True)


if __name__ == "__main__":
    train()
