import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from joblib import dump
from sklearn.dummy import DummyRegressor

from ml.config import FEATURE_COLUMNS, HeatThresholds
from ml.data_validation import validate_observations
from ml.features import (
    build_next_observation_features,
    make_supervised_dataset,
)
from ml.hotspot_detector import classify_lst
from ml.model_evaluation import regression_metrics
from ml.recommendation_engine import generate_recommendations
from ml.trainer import chronological_split
from ml.predict import run_inference


def observations_for_tests():
    rows = []
    dates = pd.date_range("2025-01-01", periods=5, freq="7D")
    for zone_id, offset in (("zone-a", 0.0), ("zone-b", 2.0)):
        for index, observation_date in enumerate(dates):
            rows.append(
                {
                    "zone_id": zone_id,
                    "zone_name": zone_id.upper(),
                    "observation_date": observation_date,
                    "lst_celsius": 25.0 + offset + index,
                    "ndvi": 0.4 - index * 0.01,
                    "data_source": "LANDSAT_TEST_FIXTURE",
                }
            )
    return pd.DataFrame(rows)


class DataValidationTests(unittest.TestCase):
    def test_excludes_demo_and_conflicting_sources(self):
        frame = pd.DataFrame(
            [
                {
                    "zone_id": "a",
                    "zone_name": "A",
                    "observation_date": "2025-01-01",
                    "lst_celsius": 32.0,
                    "ndvi": 0.3,
                    "data_source": "LANDSAT",
                },
                {
                    "zone_id": "a",
                    "zone_name": "A",
                    "observation_date": "2025-01-02",
                    "lst_celsius": 33.0,
                    "ndvi": 0.2,
                    "data_source": "SYNTHETIC_DEMO_NOT_REAL",
                },
                {
                    "zone_id": "b",
                    "zone_name": "B",
                    "observation_date": "2025-01-01",
                    "lst_celsius": 35.0,
                    "ndvi": 0.1,
                    "data_source": "SOURCE_A",
                },
                {
                    "zone_id": "b",
                    "zone_name": "B",
                    "observation_date": "2025-01-01",
                    "lst_celsius": 36.0,
                    "ndvi": 0.2,
                    "data_source": "SOURCE_B",
                },
            ]
        )
        normalized, eligible, report = validate_observations(frame)
        self.assertEqual(len(normalized), 2)
        self.assertEqual(len(eligible), 1)
        self.assertEqual(report["demonstration_rows_excluded"], 1)
        self.assertEqual(report["conflicting_source_rows_excluded"], 2)

        unknown = frame.iloc[[0]].copy()
        unknown.loc[:, "data_source"] = "unknown"
        _, unknown_eligible, _ = validate_observations(unknown)
        self.assertTrue(unknown_eligible.empty)


class FeatureTests(unittest.TestCase):
    def test_lags_use_prior_rows_and_inference_has_one_zone_id_column(self):
        data = observations_for_tests()
        supervised = make_supervised_dataset(data)
        self.assertEqual(len(supervised), 6)
        self.assertEqual(supervised.iloc[0]["lst_lag_1"], 26.0)
        self.assertEqual(supervised.iloc[0]["lst_lag_2"], 25.0)

        future = build_next_observation_features(data)
        self.assertEqual(len(future), 2)
        self.assertEqual(future.columns.tolist().count("zone_id"), 1)
        self.assertEqual(set(future["forecast_horizon_days"]), {7})
        self.assertEqual(
            future.iloc[0]["target_observation_date"],
            pd.Timestamp("2025-02-05"),
        )

    def test_chronological_split_holds_out_later_dates(self):
        data = make_supervised_dataset(observations_for_tests())
        train, test, cutoff = chronological_split(
            data,
            type(
                "Requirements",
                (),
                {
                    "minimum_test_dates": 2,
                },
            )(),
        )
        self.assertLess(train["observation_date"].max(), cutoff)
        self.assertGreaterEqual(test["observation_date"].min(), cutoff)


class HotspotAndRecommendationTests(unittest.TestCase):
    def test_heat_thresholds_and_invalid_values(self):
        thresholds = HeatThresholds(30, 35, 40, 0.25)
        self.assertEqual(classify_lst(30, thresholds), "Low")
        self.assertEqual(classify_lst(35, thresholds), "Moderate")
        self.assertEqual(classify_lst(40, thresholds), "High")
        self.assertEqual(classify_lst(41, thresholds), "Very high")
        self.assertEqual(classify_lst(float("nan"), thresholds), "Unavailable")
        with self.assertRaises(ValueError):
            HeatThresholds(35, 30, 40, 0.25).validate()

    def test_recommendations_ignore_demo_and_include_supporting_evidence(self):
        thresholds = HeatThresholds(30, 35, 40, 0.25)
        zones = pd.DataFrame(
            [
                {
                    "zone_id": "real-zone",
                    "zone_name": "Real zone",
                    "observation_date": "2025-01-01",
                    "lst_celsius": 42.0,
                    "ndvi": 0.2,
                    "data_source": "LANDSAT_C2",
                },
                {
                    "zone_id": "demo-zone",
                    "zone_name": "Demo zone",
                    "observation_date": "2025-01-01",
                    "lst_celsius": 45.0,
                    "ndvi": 0.1,
                    "data_source": "SYNTHETIC_DEMO_NOT_REAL",
                },
            ]
        )
        recommendations = generate_recommendations(
            zones, pd.DataFrame(), thresholds=thresholds
        )
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["zone_id"], "real-zone")
        self.assertIn("data_source", recommendations[0]["supporting_evidence"])
        self.assertIn("not a causal", recommendations[0]["reason"])


class EvaluationTests(unittest.TestCase):
    def test_metrics_report_temperature_units_and_single_value_r2(self):
        result = regression_metrics([30], [32])
        self.assertEqual(result["mae_c"], 2.0)
        self.assertEqual(result["rmse_c"], 2.0)
        self.assertIsNone(result["r2"])

    def test_validation_metrics_reject_empty_or_mismatched_inputs(self):
        with self.assertRaises(ValueError):
            regression_metrics([], [])
        with self.assertRaises(ValueError):
            regression_metrics([1, 2], [1])


class InferenceTests(unittest.TestCase):
    def test_inference_persists_idempotent_rows_with_uncertainty_and_unverified_coords(self):
        observations = observations_for_tests()
        validation = {"eligible_non_demo_rows": len(observations)}
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            artifact_directory = root / "artifacts"
            artifact_directory.mkdir()
            artifact_path = artifact_directory / "fixture.joblib"
            model_input = pd.DataFrame(
                [{column: 1 for column in FEATURE_COLUMNS}]
            )
            model = DummyRegressor(strategy="constant", constant=32.0)
            model.fit(model_input, [32.0])
            dump(model, artifact_path)

            metadata_path = artifact_directory / "latest.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "artifact_file": artifact_path.name,
                        "model_version": "test-only-model",
                        "training_data_end": "2025-01-29",
                        "uncertainty": {"absolute_error_quantile_c": 1.5},
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch("ml.predict.ARTIFACT_DIR", artifact_directory),
                patch("ml.predict.ARTIFACT_METADATA_PATH", metadata_path),
                patch(
                    "ml.predict.read_training_observations",
                    return_value=(observations, validation),
                ),
                patch("ml.predict.persist_predictions_and_recommendations") as persist,
            ):
                result = run_inference()

        saved_predictions = persist.call_args.args[0]
        self.assertEqual(result["predictions_saved"], 2)
        self.assertEqual(len(saved_predictions), 2)
        self.assertTrue(all(len(row) == 14 for row in saved_predictions))
        self.assertEqual(saved_predictions[0][7:9], (30.5, 33.5))
        self.assertFalse(saved_predictions[0][13])


if __name__ == "__main__":
    unittest.main()
