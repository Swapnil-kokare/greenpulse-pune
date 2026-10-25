import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import mysql.connector

from ml.config import READINESS_REPORT_PATH
from ml.database import collect_data_readiness


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def main():
    try:
        report = collect_data_readiness()
    except (RuntimeError, mysql.connector.Error) as error:
        report = {
            "database_available": False,
            "error": str(error),
        }
        status = 2
    else:
        status = 0
    READINESS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    READINESS_REPORT_PATH.write_text(
        json.dumps(report, indent=2, default=_json_default),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, default=_json_default))
    print(f"Readiness report written to {READINESS_REPORT_PATH}")
    return status


if __name__ == "__main__":
    sys.exit(main())
