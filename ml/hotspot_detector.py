import math

from ml.config import HEAT_THRESHOLDS, HeatThresholds


def classify_lst(value, thresholds=HEAT_THRESHOLDS):
    """Classify LST with configurable exploratory bands, not official alerts."""
    thresholds.validate()
    if value is None:
        return "Unavailable"
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return "Unavailable"
    if not math.isfinite(temperature):
        return "Unavailable"
    if temperature <= thresholds.low_max_c:
        return "Low"
    if temperature <= thresholds.moderate_max_c:
        return "Moderate"
    if temperature <= thresholds.high_max_c:
        return "High"
    return "Very high"
