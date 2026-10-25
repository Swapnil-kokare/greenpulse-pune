import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from joblib import load

from ml.config import ARTIFACT_DIR, ARTIFACT_METADATA_PATH, FEATURE_COLUMNS
from ml.database import (
    persist_predictions_and_recommendations,
    read_training_observations,
)
from ml.features import build_next_observation_features
from ml.config import HEAT_THRESHOLDS
from ml.recommendation_engine import generate_recommendations

PREDICTION_NAMESPACE = uuid.UUID("426c6e12-36da-46ba-b87d-5f6a32656847")


def _verified_coordinates(observations, zone_id):
    zone_data = observations[observations["zone_id"].astype(str) == str(zone_id)]
    if zone_data.empty:
        return None, None, False
    latest_date = zone_data["observation_date"].max()
    latest = zone_data[zone_data["observation_date"] == latest_date].iloc[-1]
    latitude = latest.get("latitude")
    longitude = latest.get("longitude")
    verified_value = latest.get("coordinates_verified", False)
    verified = not pd.isna(verified_value) and bool(verified_value)
    if (
        not verified
        or pd.isna(latitude)
        or pd.isna(longitude)
        or not -90 <= float(latitude) <= 90
        or not -180 <= float(longitude) <= 180
    ):
        return None, None, False
    return float(latitude), float(longitude), True


def run_inference(thresholds=HEAT_THRESHOLDS):
    if not ARTIFACT_METADATA_PATH.is_file():
        raise FileNotFoundError(
            "No accepted model artifact is available. Run `python -m ml.train_model` "
            "after sufficient source-tagged non-demonstration history has "
            "accumulated and its provenance has been reviewed."
        )
    metadata = json.loads(ARTIFACT_METADATA_PATH.read_text(encoding="utf-8"))
    artifact_path = ARTIFACT_DIR / Path(metadata["artifact_file"]).name
    if not artifact_path.is_file():
        raise FileNotFoundError(
            "The accepted model artifact listed in latest.json is missing."
        )

    observations, validation = read_training_observations()
    latest_date = pd.to_datetime(observations["observation_date"]).max()
    trained_through = pd.to_datetime(metadata.get("training_data_end"), errors="coerce")
    if pd.notna(trained_through) and latest_date > trained_through:
        raise ValueError(
            "The accepted model is stale because newer observations are available. "
            "Run `python -m ml.train_model` before generating new predictions."
        )
    features = build_next_observation_features(observations)
    if features.empty:
        raise ValueError(
            "At least two dated observations per zone are required to build "
            "next-observation inputs."
        )
    model = load(artifact_path)
    predicted = model.predict(features[list(FEATURE_COLUMNS)])
    uncertainty = metadata.get("uncertainty", {})
    absolute_error = uncertainty.get("absolute_error_quantile_c")
    if absolute_error is None:
        raise ValueError(
            "The accepted model has no stored chronological uncertainty estimate. "
            "Retrain with the current pipeline before running inference."
        )
    generated_at = datetime.now(timezone.utc)
    rows = []
    predictions = []
    for (_, row), value in zip(features.iterrows(), predicted):
        value = float(value)
        if not -50 <= value <= 80:
            raise ValueError(
                f"Model output for zone {row['zone_id']} is outside the validated "
                "land-surface-temperature range (-50 to 80 °C); no outputs were saved."
            )
        prediction_id = str(
            uuid.uuid5(
                PREDICTION_NAMESPACE,
                "|".join(
                    (
                        str(row["zone_id"]),
                        str(row["input_observation_date"].date()),
                        str(row["target_observation_date"].date()),
                        metadata["model_version"],
                    )
                ),
            )
        )
        latitude, longitude, coordinates_verified = _verified_coordinates(
            observations, row["zone_id"]
        )
        source_rows = observations[
            observations["zone_id"].astype(str) == str(row["zone_id"])
        ].sort_values("observation_date")
        source = str(source_rows.iloc[-1]["data_source"])
        prediction = {
            "prediction_id": prediction_id,
            "zone_id": str(row["zone_id"]),
            "zone_name": str(row["zone_name"]),
            "input_observation_date": row["input_observation_date"].date(),
            "target_observation_date": row["target_observation_date"].date(),
            "forecast_horizon_days": int(row["forecast_horizon_days"]),
            "predicted_lst_c": value,
            "predicted_lst_lower_c": max(-50.0, value - absolute_error),
            "predicted_lst_upper_c": min(80.0, value + absolute_error),
            "model_version": metadata["model_version"],
            "data_source_status": (
                f"Source-tagged non-demonstration input: {source}"
            ),
            "latitude": latitude,
            "longitude": longitude,
            "coordinates_verified": coordinates_verified,
        }
        predictions.append(prediction)
        rows.append(
            (
                prediction_id,
                prediction["zone_id"],
                prediction["zone_name"],
                prediction["input_observation_date"],
                prediction["target_observation_date"],
                prediction["forecast_horizon_days"],
                prediction["predicted_lst_c"],
                prediction["predicted_lst_lower_c"],
                prediction["predicted_lst_upper_c"],
                prediction["model_version"],
                prediction["data_source_status"],
                latitude,
                longitude,
                coordinates_verified,
            )
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
        generated_at=generated_at,
    )
    recommendation_rows = [
        (
            str(
                uuid.uuid5(
                    PREDICTION_NAMESPACE,
                    recommendation["deduplication_key"],
                )
            ),
            recommendation["zone_id"],
            recommendation["zone_name"],
            recommendation["environmental_issue"],
            recommendation["issue_type"],
            json.dumps(recommendation["supporting_evidence"], sort_keys=True),
            recommendation["recommended_intervention"],
            recommendation["reason"],
            recommendation["priority"],
            recommendation["confidence"],
            recommendation["recommendation_timestamp"].replace(tzinfo=None),
            recommendation["follow_up_measurement"],
            recommendation["related_prediction_id"],
            recommendation["deduplication_key"],
            recommendation["source_status"],
        )
        for recommendation in recommendations
    ]
    persist_predictions_and_recommendations(rows, recommendation_rows)
    return {
        "status": "complete",
        "model_version": metadata["model_version"],
        "observations": validation["eligible_non_demo_rows"],
        "predictions_saved": len(rows),
        "recommendations_saved": len(recommendation_rows),
        "verified_coordinate_predictions": sum(
            prediction["coordinates_verified"] for prediction in predictions
        ),
        "generated_at": generated_at.isoformat(),
    }


def main():
    import json
    import argparse

    import mysql.connector

    parser = argparse.ArgumentParser(
        description="Generate predictions using the accepted real-data or demo-only model."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use only the isolated synthetic demo model and save local demo outputs.",
    )
    args = parser.parse_args()
    if args.demo:
        from ml.demo_mode import predict_demo

        try:
            result = predict_demo()
        except (FileNotFoundError, RuntimeError, ValueError) as error:
            print(json.dumps({"status": "failed", "reason": str(error)}, indent=2))
            return 2
        print(json.dumps(result, indent=2, default=str))
        return 0

    try:
        result = run_inference()
    except (FileNotFoundError, RuntimeError, ValueError, mysql.connector.Error) as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
