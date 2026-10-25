import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import dump
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.config import (
    ARTIFACT_DIR,
    ARTIFACT_METADATA_PATH,
    CATEGORICAL_FEATURES,
    DEMO_ARTIFACT_DIR,
    DEMO_ARTIFACT_METADATA_PATH,
    DEMO_TRAINING_REPORT_PATH,
    FEATURE_COLUMNS,
    MODEL_VERSION_PREFIX,
    NUMERIC_FEATURES,
    READINESS_REQUIREMENTS,
    TARGET_COLUMN,
    TRAINING_REPORT_PATH,
)
from ml.features import make_supervised_dataset
from ml.model_evaluation import regression_metrics


def chronological_split(supervised, requirements=READINESS_REQUIREMENTS):
    dates = sorted(pd.to_datetime(supervised["observation_date"]).unique())
    if len(dates) < requirements.minimum_test_dates + 1:
        raise ValueError(
            f"At least {requirements.minimum_test_dates + 1} distinct dates are "
            "required for a chronological train/test split."
        )
    split_index = max(1, int(len(dates) * 0.8))
    split_index = min(split_index, len(dates) - 1)
    cutoff = dates[split_index]
    train = supervised[pd.to_datetime(supervised["observation_date"]) < cutoff]
    test = supervised[pd.to_datetime(supervised["observation_date"]) >= cutoff]
    return train.copy(), test.copy(), pd.Timestamp(cutoff)


def _candidate_pipeline(random_state=42):
    preprocessor = ColumnTransformer(
        [
            (
                "zone",
                OneHotEncoder(handle_unknown="ignore"),
                list(CATEGORICAL_FEATURES),
            ),
            ("numeric", "passthrough", list(NUMERIC_FEATURES)),
        ],
        remainder="drop",
    )
    return Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=300,
                    min_samples_leaf=2,
                    max_features=0.8,
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, default=_json_default),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def train_candidate(
    observations,
    validation_report,
    requirements=READINESS_REQUIREMENTS,
    minimum_mae_improvement=0.05,
    demo_mode=False,
):
    """Train only on eligible rows and deploy only after temporal holdout acceptance."""
    now = datetime.now(timezone.utc)
    supervised = make_supervised_dataset(observations)
    zones = int(observations["zone_id"].nunique())
    dates = int(observations["observation_date"].nunique())
    readiness = {
        "eligible_observations": int(len(observations)),
        "supervised_observations": int(len(supervised)),
        "distinct_dates": dates,
        "distinct_zones": zones,
        "minimums": {
            "observations": requirements.minimum_observations,
            "dates": requirements.minimum_dates,
            "zones": requirements.minimum_zones,
            "test_observations": requirements.minimum_test_observations,
            "test_dates": requirements.minimum_test_dates,
        },
    }
    report = {
        "status": "insufficient_data",
        "generated_at": now,
        "validation": validation_report,
        "readiness": readiness,
        "target": "Next observed LST (°C), using each zone's observed median cadence",
        "feature_columns": list(FEATURE_COLUMNS),
        "metric_note": (
            "Synthetic demonstration data only. These metrics illustrate the "
            "workflow and are not evidence of real-world performance."
            if demo_mode
            else (
                "Metrics use a chronological holdout and are reported only for "
                "eligible non-demonstration observations."
            )
        ),
        "demo_only": demo_mode,
    }
    if demo_mode:
        report["data_quality_note"] = (
            "Trained explicitly in demo mode using synthetic demonstration "
            "observations. Never present this model, predictions, or metrics as "
            "real Pune measurements or validated forecasts."
        )
    elif (
        validation_report.get("demonstration_rows_excluded", 0)
        or validation_report.get("eligible_non_demo_rows", len(observations))
        != validation_report.get("valid_rows", len(observations))
    ):
        report["data_quality_note"] = (
            "Demonstration and/or ambiguous-source records were excluded before "
            "training."
        )

    missing = []
    if len(observations) < requirements.minimum_observations:
        missing.append("eligible observations")
    if dates < requirements.minimum_dates:
        missing.append("distinct observation dates")
    if zones < requirements.minimum_zones:
        missing.append("distinct zones")
    if missing:
        report["reason"] = (
            "Insufficient eligible non-demonstration data: minimum requirements "
            "not met for "
            + ", ".join(missing)
            + "."
        )
        _write_json(
            DEMO_TRAINING_REPORT_PATH if demo_mode else TRAINING_REPORT_PATH,
            report,
        )
        return report

    if len(supervised) == 0:
        report["reason"] = (
            "No supervised rows can be formed; each zone needs at least three "
            "valid, source-consistent observations."
        )
        _write_json(
            DEMO_TRAINING_REPORT_PATH if demo_mode else TRAINING_REPORT_PATH,
            report,
        )
        return report

    supervised_dates = int(supervised["observation_date"].nunique())
    if supervised_dates < requirements.minimum_test_dates + 1:
        report["reason"] = (
            "Insufficient supervised observation dates for the configured "
            "chronological holdout."
        )
        _write_json(
            DEMO_TRAINING_REPORT_PATH if demo_mode else TRAINING_REPORT_PATH,
            report,
        )
        return report
    train, test, cutoff = chronological_split(supervised, requirements)
    readiness["training_rows"] = int(len(train))
    readiness["test_rows"] = int(len(test))
    readiness["test_dates"] = int(test["observation_date"].nunique())
    readiness["split_date"] = cutoff
    if (
        len(train) < requirements.minimum_observations
        or len(test) < requirements.minimum_test_observations
        or readiness["test_dates"] < requirements.minimum_test_dates
    ):
        report["reason"] = (
            "Insufficient supervised rows for the configured chronological "
            "training and holdout minimums."
        )
        _write_json(
            DEMO_TRAINING_REPORT_PATH if demo_mode else TRAINING_REPORT_PATH,
            report,
        )
        return report

    x_train = train[list(FEATURE_COLUMNS)]
    y_train = train[TARGET_COLUMN]
    x_test = test[list(FEATURE_COLUMNS)]
    y_test = test[TARGET_COLUMN]
    baseline = DummyRegressor(strategy="mean")
    baseline.fit(x_train, y_train)
    baseline_prediction = baseline.predict(x_test)
    baseline_metrics = regression_metrics(y_test, baseline_prediction)

    candidate = _candidate_pipeline()
    candidate.fit(x_train, y_train)
    candidate_prediction = candidate.predict(x_test)
    candidate_metrics = regression_metrics(y_test, candidate_prediction)
    report["metrics"] = {
        "baseline": baseline_metrics,
        "candidate_random_forest": candidate_metrics,
    }
    required_mae = baseline_metrics["mae_c"] * (
        1.0 - minimum_mae_improvement
    )
    accepted = (
        baseline_metrics["mae_c"] > 0
        and candidate_metrics["mae_c"] <= required_mae
        and candidate_metrics["rmse_c"] <= baseline_metrics["rmse_c"]
    )
    report["acceptance_criteria"] = {
        "minimum_mae_improvement_fraction": minimum_mae_improvement,
        "candidate_mae_must_be_at_most_c": required_mae,
        "candidate_rmse_must_not_exceed_baseline": True,
        "accepted": accepted,
    }
    report["holdout"] = [
        {
            "observation_date": row["observation_date"],
            "zone_id": row["zone_id"],
            "actual_lst_c": float(actual),
            "predicted_lst_c": float(predicted),
        }
        for (_, row), actual, predicted in zip(
            test.iterrows(), y_test, candidate_prediction
        )
    ]
    absolute_residuals = np.abs(np.asarray(y_test) - candidate_prediction)
    interval_error = float(np.quantile(absolute_residuals, 0.9))
    report["uncertainty"] = {
        "method": "90th percentile absolute error from chronological holdout",
        "absolute_error_quantile_c": interval_error,
        "holdout_coverage": float(
            np.mean(absolute_residuals <= interval_error)
        ),
        "caveat": (
            "Empirical error band only; it is not a calibrated probability "
            "interval or a guarantee of future coverage."
        ),
    }
    report["status"] = (
        "demo_only" if demo_mode else ("accepted" if accepted else "rejected")
    )
    if not accepted and not demo_mode:
        report["reason"] = (
            "Candidate did not meet both the "
            f"{minimum_mae_improvement:.0%} MAE improvement and non-worse "
            "RMSE acceptance criteria. Any previously accepted artifact is retained."
        )
        _write_json(TRAINING_REPORT_PATH, report)
        return report

    model = _candidate_pipeline()
    model.fit(supervised[list(FEATURE_COLUMNS)], supervised[TARGET_COLUMN])
    artifact_dir = DEMO_ARTIFACT_DIR if demo_mode else ARTIFACT_DIR
    metadata_path = (
        DEMO_ARTIFACT_METADATA_PATH if demo_mode else ARTIFACT_METADATA_PATH
    )
    training_report_path = (
        DEMO_TRAINING_REPORT_PATH if demo_mode else TRAINING_REPORT_PATH
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{MODEL_VERSION_PREFIX}-demo" if demo_mode else MODEL_VERSION_PREFIX
    model_version = f"{prefix}-{now.strftime('%Y%m%dT%H%M%SZ')}"
    artifact_name = f"{model_version}.joblib"
    artifact_path = artifact_dir / artifact_name
    temporary_artifact = artifact_path.with_suffix(".joblib.tmp")
    dump(model, temporary_artifact)
    os.replace(temporary_artifact, artifact_path)
    feature_names = model.named_steps["preprocessor"].get_feature_names_out()
    importances = model.named_steps["regressor"].feature_importances_
    top_features = sorted(
        (
            {"feature": str(name), "importance": float(importance)}
            for name, importance in zip(feature_names, importances)
        ),
        key=lambda item: item["importance"],
        reverse=True,
    )[:10]
    metadata = {
        "model_version": model_version,
        "artifact_file": artifact_name,
        "trained_at": now,
        "training_data_start": observations["observation_date"].min(),
        "training_data_end": observations["observation_date"].max(),
        "training_observations": int(len(supervised)),
        "training_zones": zones,
        "training_dates": dates,
        "feature_columns": list(FEATURE_COLUMNS),
        "target": "lst_celsius",
        "forecast_horizon": (
            "Next observation based on each zone's median historical cadence; "
            "this is not a daily forecast."
        ),
        "validation_metrics": report["metrics"],
        "uncertainty": report["uncertainty"],
        "holdout": report["holdout"],
        "acceptance_criteria": report["acceptance_criteria"],
        "top_feature_importances": top_features,
        "source_summary": validation_report.get("eligible_sources", []),
        "demo_only": demo_mode,
        "data_label": (
            "SYNTHETIC DEMO ONLY - NOT REAL DATA"
            if demo_mode
            else "Source-tagged non-demonstration input"
        ),
    }
    _write_json(metadata_path, metadata)
    report["model_version"] = model_version
    report["artifact_file"] = artifact_name
    _write_json(training_report_path, report)
    return report
