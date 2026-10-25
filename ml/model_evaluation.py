import math

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def regression_metrics(actual, predicted):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if len(actual) != len(predicted) or len(actual) == 0:
        raise ValueError("Metric inputs must have equal, non-zero lengths.")
    metrics = {
        "mae_c": float(mean_absolute_error(actual, predicted)),
        "rmse_c": float(math.sqrt(mean_squared_error(actual, predicted))),
        "r2": (
            float(r2_score(actual, predicted))
            if len(actual) >= 2
            else None
        ),
    }
    return metrics
