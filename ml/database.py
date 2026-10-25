import os
from collections.abc import Mapping

import mysql.connector
import pandas as pd
from streamlit.errors import StreamlitSecretNotFoundError

from ml.config import OBSERVATION_TABLE
from ml.data_validation import missing_feature_report, validate_observations


class HistoryTableMissing(RuntimeError):
    pass


def _mysql_settings():
    try:
        import streamlit as st

        secrets = st.secrets.get("mysql", {})
    except StreamlitSecretNotFoundError:
        secrets = {}
    if not isinstance(secrets, Mapping):
        raise RuntimeError(
            "The [mysql] section in .streamlit/secrets.toml must be a key-value table."
        )
    password = os.getenv("MYSQL_PASSWORD") or secrets.get("password")
    if not password:
        raise RuntimeError(
            "MySQL password is not configured. Set MYSQL_PASSWORD or add a local "
            "[mysql] password in .streamlit/secrets.toml."
        )
    return {
        "host": os.getenv("MYSQL_HOST", secrets.get("host", "127.0.0.1")),
        "port": int(os.getenv("MYSQL_PORT", secrets.get("port", "3306"))),
        "user": os.getenv("MYSQL_USER", secrets.get("user", "root")),
        "password": password,
        "database": os.getenv(
            "MYSQL_DATABASE", secrets.get("database", "greenpulse_pune")
        ),
        "connection_timeout": 5,
    }


def connect_mysql():
    return mysql.connector.connect(**_mysql_settings())


def _table_exists(cursor, table_name):
    cursor.execute(
        """
        SELECT COUNT(*) AS table_count
        FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = %s
        """,
        (table_name,),
    )
    return bool(cursor.fetchone()["table_count"])


def _columns(cursor, table_name):
    cursor.execute(
        """
        SELECT column_name AS name
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return [row["name"] for row in cursor.fetchall()]


def _local_dataset_report():
    from ml.config import LOCAL_DATASET_PATH

    if not LOCAL_DATASET_PATH.exists():
        return {"exists": False, "rows": 0, "source_note": "File not found."}
    local = pd.read_csv(LOCAL_DATASET_PATH)
    if "data_source" not in local:
        return {
            "exists": True,
            "rows": int(len(local)),
            "source_note": "No source column; excluded from model training.",
        }
    _, _, validation = validate_observations(local)
    return {
        "exists": True,
        **validation,
        "source_note": "Local bundled dataset; source provenance is reported below.",
    }


def collect_data_readiness():
    """Inspect existing summary/history tables without modifying the database."""
    connection = connect_mysql()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        summary_exists = _table_exists(cursor, "zone_environment_summary")
        summary = {"exists": summary_exists, "row_count": 0}
        summary_columns = (
            _columns(cursor, "zone_environment_summary") if summary_exists else []
        )
        if summary_exists:
            required_summary = {
                "zone_id",
                "latest_observation_date",
                "batch_id",
                "records_received",
            }
            missing_summary = sorted(required_summary - set(summary_columns))
            if missing_summary:
                summary["schema_error"] = (
                    "Summary table is missing columns: "
                    + ", ".join(missing_summary)
                )
            else:
                processing_expression = (
                    "MAX(processed_at)"
                    if "processed_at" in summary_columns
                    else "NULL"
                )
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS row_count,
                           COUNT(DISTINCT zone_id) AS distinct_zones,
                           COUNT(DISTINCT latest_observation_date) AS distinct_dates,
                           COUNT(DISTINCT batch_id) AS distinct_batches,
                           MIN(latest_observation_date) AS earliest_observation,
                           MAX(latest_observation_date) AS latest_observation,
                           SUM(records_received) AS records_received,
                           {processing_expression} AS latest_processing_time
                    FROM zone_environment_summary
                    """
                )
                summary.update(cursor.fetchone())

        history_exists = _table_exists(cursor, OBSERVATION_TABLE)
        history = {"exists": history_exists, "rows": 0, "validation": None}
        history_columns = _columns(cursor, OBSERVATION_TABLE) if history_exists else []
        if history_exists:
            required = {
                "zone_id",
                "zone_name",
                "observation_date",
                "lst_celsius",
                "ndvi",
                "data_source",
            }
            missing = sorted(required - set(history_columns))
            if missing:
                history["schema_error"] = (
                    "History table is missing required columns: " + ", ".join(missing)
                )
            else:
                valid = (
                    "o.zone_id IS NOT NULL AND TRIM(o.zone_id) <> '' "
                    "AND o.zone_name IS NOT NULL AND TRIM(o.zone_name) <> '' "
                    "AND o.observation_date IS NOT NULL "
                    "AND o.lst_celsius BETWEEN -50 AND 80 "
                    "AND o.ndvi BETWEEN -1 AND 1 "
                    "AND o.data_source IS NOT NULL "
                    "AND TRIM(o.data_source) <> ''"
                )
                demo = (
                    "LOWER(o.data_source) LIKE '%synthetic%' "
                    "OR LOWER(o.data_source) LIKE '%simulated%' "
                    "OR LOWER(o.data_source) LIKE '%demo%' "
                    "OR LOWER(o.data_source) LIKE '%illustrative%' "
                    "OR LOWER(o.data_source) LIKE '%not_real%' "
                    "OR LOWER(o.data_source) LIKE '%not real%' "
                    "OR LOWER(o.data_source) LIKE '%unknown%' "
                    "OR LOWER(o.data_source) LIKE '%unverified%'"
                )
                processing_expression = (
                    "MAX(o.processed_at)"
                    if "processed_at" in history_columns
                    else "NULL"
                )
                batch_expression = (
                    "MAX(o.last_batch_id)"
                    if "last_batch_id" in history_columns
                    else "NULL"
                )
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS rows_received,
                           SUM(CASE WHEN {valid} THEN 1 ELSE 0 END) AS valid_rows,
                           SUM(CASE WHEN {valid} AND ({demo})
                                    THEN 1 ELSE 0 END) AS demonstration_rows,
                           SUM(CASE WHEN {valid} AND NOT ({demo})
                                         AND conflicts.zone_id IS NULL
                                    THEN 1 ELSE 0 END) AS eligible_rows,
                           SUM(CASE WHEN {valid}
                                         AND conflicts.zone_id IS NOT NULL
                                    THEN 1 ELSE 0 END)
                               AS conflicting_source_rows,
                           COUNT(DISTINCT CASE
                               WHEN {valid} AND NOT ({demo})
                                    AND conflicts.zone_id IS NULL
                               THEN o.zone_id END) AS eligible_zones,
                           COUNT(DISTINCT CASE
                               WHEN {valid} AND NOT ({demo})
                                    AND conflicts.zone_id IS NULL
                               THEN o.observation_date END) AS eligible_dates,
                           MIN(CASE WHEN {valid} AND NOT ({demo})
                                    AND conflicts.zone_id IS NULL
                                    THEN o.observation_date END)
                               AS earliest_eligible_observation,
                           MAX(CASE WHEN {valid} AND NOT ({demo})
                                    AND conflicts.zone_id IS NULL
                                    THEN o.observation_date END)
                               AS latest_observation,
                           {processing_expression} AS latest_processing_time,
                           {batch_expression} AS latest_batch_id
                    FROM environment_observations AS o
                    LEFT JOIN (
                        SELECT zone_id, observation_date
                        FROM environment_observations
                        GROUP BY zone_id, observation_date
                        HAVING COUNT(DISTINCT data_source) > 1
                    ) AS conflicts
                      ON conflicts.zone_id = o.zone_id
                     AND conflicts.observation_date = o.observation_date
                    """
                )
                counts = cursor.fetchone()
                history.update(
                    {
                        "rows": int(counts["rows_received"] or 0),
                        "latest_observation": counts["latest_observation"],
                        "earliest_eligible_observation": counts[
                            "earliest_eligible_observation"
                        ],
                        "latest_processing_time": counts[
                            "latest_processing_time"
                        ],
                        "latest_batch_id": counts["latest_batch_id"],
                        "eligible_rows": int(counts["eligible_rows"] or 0),
                        "eligible_dates": int(counts["eligible_dates"] or 0),
                        "eligible_zones": int(counts["eligible_zones"] or 0),
                        "validation": {
                            "rows_received": int(counts["rows_received"] or 0),
                            "valid_rows": int(counts["valid_rows"] or 0),
                            "eligible_non_demo_rows": int(
                                counts["eligible_rows"] or 0
                            ),
                            "demonstration_rows_excluded": int(
                                counts["demonstration_rows"] or 0
                            ),
                            "conflicting_source_rows_excluded": int(
                                counts["conflicting_source_rows"] or 0
                            ),
                            "distinct_zones": int(counts["eligible_zones"] or 0),
                            "distinct_observation_dates": int(
                                counts["eligible_dates"] or 0
                            ),
                        },
                    }
                )
                cursor.execute(
                    """
                    SELECT DISTINCT data_source
                    FROM environment_observations
                    WHERE data_source IS NOT NULL AND TRIM(data_source) <> ''
                    ORDER BY data_source
                    """
                )
                history["validation"]["sources"] = [
                    row["data_source"] for row in cursor.fetchall()
                ]
                history["missing_optional_inputs"] = missing_feature_report(
                    history_columns,
                    has_weather={"temperature_c", "precipitation_mm"}
                    <= set(history_columns),
                    has_air_quality={"pm25", "pm10"} <= set(history_columns),
                    has_electricity={"electricity_kwh"} <= set(history_columns),
                )
        return {
            "database_available": True,
            "summary_table": summary,
            "summary_columns": summary_columns,
            "history_table": history,
            "history_columns": history_columns,
            "local_demo_dataset": _local_dataset_report(),
        }
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def read_training_observations():
    connection = connect_mysql()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        if not _table_exists(cursor, OBSERVATION_TABLE):
            raise HistoryTableMissing(
                "The environment_observations table is missing. Apply "
                "database/migrations/001_environmental_ml.sql, then restart the "
                "Spark streaming job to collect new records."
            )
        columns = set(_columns(cursor, OBSERVATION_TABLE))
        required = {
            "zone_id",
            "zone_name",
            "observation_date",
            "lst_celsius",
            "ndvi",
            "data_source",
        }
        missing = sorted(required - columns)
        if missing:
            raise RuntimeError(
                "The environment_observations table is missing columns: "
                + ", ".join(missing)
            )
        optional = [
            column
            for column in ("latitude", "longitude", "ndbi", "coordinates_verified")
            if column in columns
        ]
        selection = [
            "zone_id",
            "zone_name",
            "observation_date",
            "lst_celsius",
            "ndvi",
            "data_source",
            *optional,
        ]
        cursor.execute(
            f"SELECT {', '.join(selection)} FROM environment_observations"
        )
        observations = pd.DataFrame.from_records(cursor.fetchall())
        _, eligible, validation = validate_observations(observations)
        if eligible.empty:
            raise ValueError(
                "No eligible non-demonstration observations are available. "
                f"Received {validation['rows_received']} rows; excluded "
                f"{validation['demonstration_rows_excluded']} demonstration rows."
            )
        return eligible, validation
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def read_saved_ml_outputs(limit=200):
    connection = connect_mysql()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        outputs = {"predictions": [], "recommendations": []}
        for table, key, sql in (
            (
                "ml_predictions",
                "predictions",
                """
                SELECT prediction_id, zone_id, zone_name,
                       input_observation_date, target_observation_date,
                       forecast_horizon_days, predicted_lst_c,
                       predicted_lst_lower_c, predicted_lst_upper_c,
                       model_version, created_at, data_source_status,
                       latitude, longitude, coordinates_verified
                FROM ml_predictions ORDER BY created_at DESC LIMIT %s
                """,
            ),
            (
                "environmental_recommendations",
                "recommendations",
                """
                SELECT recommendation_id, zone_id, zone_name,
                       environmental_issue, issue_type, supporting_evidence,
                       recommended_intervention, reason, priority, confidence,
                       recommendation_timestamp, follow_up_measurement,
                       related_prediction_id, source_status
                FROM environmental_recommendations
                ORDER BY recommendation_timestamp DESC LIMIT %s
                """,
            ),
        ):
            if _table_exists(cursor, table):
                cursor.execute(sql, (limit,))
                outputs[key] = cursor.fetchall()
        return outputs
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def persist_predictions_and_recommendations(predictions, recommendations):
    connection = connect_mysql()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SET time_zone = '+00:00'")
        if predictions:
            cursor.executemany(
                """
                INSERT INTO ml_predictions (
                    prediction_id, zone_id, zone_name, input_observation_date,
                    target_observation_date, forecast_horizon_days,
                    predicted_lst_c, predicted_lst_lower_c,
                    predicted_lst_upper_c, model_version, data_source_status,
                    latitude, longitude, coordinates_verified
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    predicted_lst_c = VALUES(predicted_lst_c),
                    predicted_lst_lower_c = VALUES(predicted_lst_lower_c),
                    predicted_lst_upper_c = VALUES(predicted_lst_upper_c),
                    created_at = CURRENT_TIMESTAMP
                """,
                predictions,
            )
        if recommendations:
            cursor.executemany(
                """
                INSERT INTO environmental_recommendations (
                    recommendation_id, zone_id, zone_name, environmental_issue,
                    issue_type, supporting_evidence, recommended_intervention,
                    reason, priority, confidence, recommendation_timestamp,
                    follow_up_measurement, related_prediction_id,
                    deduplication_key, source_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    supporting_evidence = VALUES(supporting_evidence),
                    recommendation_timestamp = VALUES(recommendation_timestamp)
                """,
                recommendations,
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
