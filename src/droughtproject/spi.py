# ////////////////////////////////////////////////////////////////////////////
# // 1. Reads complete monthly rainfall and the fixed 1982–2011 reference period.
# // 2. Fits one zero-adjusted gamma distribution per ending calendar month.
# // 3. Converts three-month rainfall totals into finite historical SPI-3 values.
# // 4. Supplies statistical reference parameters to training and prediction.
# ////////////////////////////////////////////////////////////////////////////
import numpy as np
import pandas as pd
from scipy.stats import gamma, norm

from droughtproject.settings import SPI_REFERENCE


def fit_reference(monthly):
    accumulated = monthly["rainfall_mm"].rolling(3, min_periods=3).sum()
    reference = accumulated.loc[SPI_REFERENCE[0] : SPI_REFERENCE[1]]
    parameters = {}
    for month in range(1, 13):
        values = reference.loc[reference.index.month == month].dropna()
        positive = values[values > 0]
        if len(values) != 30 or len(positive) < 10 or positive.nunique() < 2:
            raise ValueError(
                f"SPI month {month}: need 30 complete reference years and enough variable nonzero totals."
            )
        shape, _, scale = gamma.fit(positive.to_numpy(), floc=0)
        if not np.isfinite([shape, scale]).all() or shape <= 0 or scale <= 0:
            raise ValueError(f"SPI month {month}: invalid gamma fit.")
        parameters[month] = {
            "shape": float(shape),
            "scale": float(scale),
            "zero_probability": float((values == 0).mean()),
        }
    return parameters


def calculate_spi(monthly, parameters):
    accumulated = monthly["rainfall_mm"].rolling(3, min_periods=3).sum()
    result = pd.Series(np.nan, index=monthly.index, name="spi3")
    for month, fitted in parameters.items():
        mask = (accumulated.index.month == int(month)) & accumulated.notna()
        probability = gamma.cdf(
            accumulated.loc[mask], a=fitted["shape"], scale=fitted["scale"]
        )
        probability = (
            fitted["zero_probability"] + (1 - fitted["zero_probability"]) * probability
        )
        result.loc[mask] = norm.ppf(np.clip(probability, 1e-8, 1 - 1e-8))
    return result


def category(value):
    if value <= -2:
        return "extremely_dry"
    if value <= -1.5:
        return "severely_dry"
    if value <= -1:
        return "moderately_dry"
    if value >= 1:
        return "wet"
    return "near_normal"
