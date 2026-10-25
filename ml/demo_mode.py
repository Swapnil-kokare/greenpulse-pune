import json
from datetime import datetime, timezone

import pandas as pd
from joblib import load

from ml.config import (
    DEMO_ARTIFACT_DIR,
    DEMO_ARTIFACT_METADATA_PATH,
    DEMO_PREDICTIONS_PATH,
    DEMO_TRAINING_REPORT_PATH,
    FEATURE_COLUMNS,
    HEAT_THRESHOLDS,
    LOCAL_DATASET_PATH,
    ReadinessRequirements,
)
from ml.data_validation import validate_observations
from ml.features import build_next_observation_features
from ml.recommendation_engine import generate_recommendations
from ml.trainer import _write_json, train_candidate

DEMO_REQUIREMENTS = ReadinessRequirements(
    minimum_observations=50,
    minimum_dates=8,
    minimum_zones=5,
    minimum_test_observations=20,
    minimum_test_dates=2,
)


def load_demo_observations():
    if not LOCAL_DATASET_PATH.is_file():
        raise FileNotFoundError(
            f"Bundled demo CSV was not found: {LOCAL_DATASET_PATH}"
        )
    frame = pd.read_csv(LOCAL_DATASET_PATH)
    normalized, _, report = validate_observations(frame)
    if normalized.empty:
        raise ValueError("The bundled demonstration CSV has no valid observations.")
    report["eligible_non_demo_rows"] = 0
    report["eligible_sources"] = []
    report["demo_training_rows"] = int(len(normalized))
    return normalized, report


def train_demo_model():
    observations, validation = load_demo_observations()
    report = train_candidate(
        observations,
        validation,
        requirements=DEMO_REQUIREMENTS,
        demo_mode=True,
    )
    if report["status"] != "demo_only":
        _write_json(DEMO_TRAINING_REPORT_PATH, report)
    return report


def predict_demo(thresholds=HEAT_THRESHOLDS):
    if not DEMO_ARTIFACT_METADATA_PATH.is_file():
        raise FileNotFoundError(
            "No demo-only model exists. Run `python -m ml.train_model --demo` first."
        )
    metadata = json.loads(
        DEMO_ARTIFACT_METADATA_PATH.read_text(encoding="utf-8")
    )
    if not metadata.get("demo_only"):
        raise ValueError("Refusing to load an artifact not marked demo_only.")
    artifact_path = DEMO_ARTIFACT_DIR / metadata["artifact_file"]
    if not artifact_path.is_file():
        raise FileNotFoundError(
            f"Demo model artifact is missing: {artifact_path}"
        )
    observations, _ = load_demo_observations()
    features = build_next_observation_features(observations)
    if features.empty:
        raise ValueError("The demo CSV has insufficient history for predictions.")
    model = load(artifact_path)
    values = model.predict(features[list(FEATURE_COLUMNS)])
    error_band = metadata["uncertainty"]["absolute_error_quantile_c"]
    predictions = []
    for (_, row), value in zip(features.iterrows(), values):
        value = float(value)
        predictions.append(
            {
                "zone_id": str(row["zone_id"]),
                "zone_name": str(row["zone_name"]),
                "input_observation_date": row[
                    "input_observation_date"
                ].date().isoformat(),
                "target_observation_date": row[
                    "target_observation_date"
                ].date().isoformat(),
                "forecast_horizon_days": int(row["forecast_horizon_days"]),
                "predicted_lst_c": value,
                "predicted_lst_lower_c": value - error_band,
                "predicted_lst_upper_c": value + error_band,
                "model_version": metadata["model_version"],
                "data_source_status": "SYNTHETIC DEMO ONLY - NOT REAL DATA",
                "coordinates_verified": False,
            }
        )
    latest_observations = (
        observations.sort_values("observation_date")
        .drop_duplicates("zone_id", keep="last")
        .copy()
    )
    recommendations = generate_recommendations(
        latest_observations,
        pd.DataFrame(predictions),
        thresholds=thresholds,
        generated_at=datetime.now(timezone.utc),
        allow_demo=True,
    )
    result = {
        "status": "demo_only",
        "data_label": "SYNTHETIC DEMO ONLY - NOT REAL DATA",
        "model_version": metadata["model_version"],
        "metrics_note": (
            "Metrics and predictions are produced from synthetic demo values "
            "and are not real-world validation or forecasts."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "predictions": predictions,
        "recommendations": recommendations,
    }
    _write_json(DEMO_PREDICTIONS_PATH, result)
    return result
