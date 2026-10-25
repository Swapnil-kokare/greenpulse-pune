import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "ml"
ARTIFACT_DIR = OUTPUT_DIR / "artifacts"
ARTIFACT_METADATA_PATH = ARTIFACT_DIR / "latest.json"
READINESS_REPORT_PATH = OUTPUT_DIR / "data_readiness.json"
TRAINING_REPORT_PATH = OUTPUT_DIR / "latest_training_report.json"
DEMO_ARTIFACT_DIR = OUTPUT_DIR / "demo_artifacts"
DEMO_ARTIFACT_METADATA_PATH = DEMO_ARTIFACT_DIR / "latest.json"
DEMO_TRAINING_REPORT_PATH = DEMO_ARTIFACT_DIR / "training_report.json"
DEMO_PREDICTIONS_PATH = DEMO_ARTIFACT_DIR / "predictions.json"
LOCAL_DATASET_PATH = ROOT / "data" / "pune_demo_observations.csv"

FEATURE_COLUMNS = (
    "zone_id",
    "lst_lag_1",
    "lst_lag_2",
    "ndvi_lag_1",
    "ndvi_lag_2",
    "days_since_previous",
    "target_month",
    "target_day_of_year",
)
CATEGORICAL_FEATURES = ("zone_id",)
NUMERIC_FEATURES = tuple(
    column for column in FEATURE_COLUMNS if column not in CATEGORICAL_FEATURES
)
MODEL_VERSION_PREFIX = "lst-next-observation"
TARGET_COLUMN = "lst_celsius"
OBSERVATION_TABLE = "environment_observations"
PREDICTION_TABLE = "ml_predictions"
RECOMMENDATION_TABLE = "environmental_recommendations"


@dataclass(frozen=True)
class ReadinessRequirements:
    minimum_observations: int = 100
    minimum_dates: int = 30
    minimum_zones: int = 5
    minimum_test_observations: int = 20
    minimum_test_dates: int = 5


READINESS_REQUIREMENTS = ReadinessRequirements()


@dataclass(frozen=True)
class HeatThresholds:
    low_max_c: float = 30.0
    moderate_max_c: float = 35.0
    high_max_c: float = 40.0
    low_ndvi_max: float = 0.25

    @classmethod
    def from_environment(cls):
        return cls(
            low_max_c=float(os.getenv("ML_HEAT_LOW_MAX_C", "30")),
            moderate_max_c=float(os.getenv("ML_HEAT_MODERATE_MAX_C", "35")),
            high_max_c=float(os.getenv("ML_HEAT_HIGH_MAX_C", "40")),
            low_ndvi_max=float(os.getenv("ML_LOW_NDVI_MAX", "0.25")),
        )

    def validate(self):
        if not self.low_max_c < self.moderate_max_c < self.high_max_c:
            raise ValueError(
                "Heat thresholds must satisfy low < moderate < high."
            )
        if not -1 <= self.low_ndvi_max <= 1:
            raise ValueError("The low-NDVI threshold must be between -1 and 1.")


HEAT_THRESHOLDS = HeatThresholds.from_environment()
