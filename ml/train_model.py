import json
import argparse
import sys

import mysql.connector

from ml.config import TRAINING_REPORT_PATH
from ml.database import HistoryTableMissing, read_training_observations
from ml.trainer import train_candidate


def main():
    parser = argparse.ArgumentParser(
        description="Train the real-data model or an explicitly isolated demo model."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Train a clearly labelled demo-only model from the bundled synthetic CSV.",
    )
    args = parser.parse_args()
    if args.demo:
        from ml.demo_mode import train_demo_model

        try:
            report = train_demo_model()
        except (FileNotFoundError, RuntimeError, ValueError) as error:
            report = {"status": "blocked", "reason": str(error), "demo_only": True}
            TRAINING_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            print(json.dumps(report, indent=2))
            return 2
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["status"] == "demo_only" else 2

    try:
        observations, validation = read_training_observations()
        report = train_candidate(observations, validation)
    except (HistoryTableMissing, RuntimeError, ValueError) as error:
        report = {
            "status": "blocked",
            "reason": str(error),
        }
        TRAINING_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRAINING_REPORT_PATH.write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        return 2
    except mysql.connector.Error as error:
        report = {
            "status": "blocked",
            "reason": f"MySQL operation failed: {error}",
        }
        TRAINING_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRAINING_REPORT_PATH.write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        return 2

    print(json.dumps(report, indent=2, default=str))
    return 0 if report["status"] in {"accepted", "rejected"} else 2


if __name__ == "__main__":
    sys.exit(main())
