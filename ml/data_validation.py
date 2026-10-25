from collections.abc import Iterable

import pandas as pd

REQUIRED_COLUMNS = (
    "zone_id",
    "zone_name",
    "observation_date",
    "lst_celsius",
    "ndvi",
    "data_source",
)
SYNTHETIC_SOURCE_MARKERS = (
    "synthetic",
    "simulated",
    "demo",
    "illustrative",
    "not_real",
    "not real",
    "unknown",
    "unverified",
)


def is_demonstration_source(value):
    if not isinstance(value, str) or not value.strip():
        return True
    normalized = value.casefold()
    return any(marker in normalized for marker in SYNTHETIC_SOURCE_MARKERS)


def validate_observations(observations):
    """Normalize and report observation quality without manufacturing values."""
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in observations.columns
    ]
    if missing_columns:
        raise ValueError(
            "Observation data is missing required columns: "
            + ", ".join(missing_columns)
        )

    normalized = observations.copy()
    original_count = len(normalized)
    normalized["zone_id"] = normalized["zone_id"].astype("string").str.strip()
    normalized["zone_name"] = normalized["zone_name"].astype("string").str.strip()
    normalized["data_source"] = (
        normalized["data_source"].astype("string").str.strip()
    )
    normalized["observation_date"] = pd.to_datetime(
        normalized["observation_date"], errors="coerce"
    ).dt.normalize()
    for column in ("lst_celsius", "ndvi", "latitude", "longitude", "ndbi"):
        if column in normalized:
            normalized[column] = pd.to_numeric(
                normalized[column], errors="coerce"
            )

    identity_valid = (
        normalized["zone_id"].notna()
        & normalized["zone_id"].ne("")
        & normalized["zone_name"].notna()
        & normalized["zone_name"].ne("")
        & normalized["observation_date"].notna()
    )
    measurement_valid = (
        normalized["lst_celsius"].between(-50, 80)
        & normalized["ndvi"].between(-1, 1)
    )
    missing_sources = (
        normalized["data_source"].isna() | normalized["data_source"].eq("")
    )
    normalized = normalized[identity_valid & measurement_valid & ~missing_sources]

    source_counts = normalized.groupby(
        ["zone_id", "observation_date"], dropna=False
    )["data_source"].transform("nunique")
    conflicting_source_mask = source_counts > 1
    conflicting_source_count = int(conflicting_source_mask.sum())
    normalized = normalized.loc[~conflicting_source_mask].copy()

    duplicate_mask = normalized.duplicated(
        ["zone_id", "observation_date"], keep="last"
    )
    duplicate_count = int(duplicate_mask.sum())
    normalized = normalized.loc[~duplicate_mask].copy()
    normalized["is_demonstration"] = normalized["data_source"].map(
        is_demonstration_source
    )
    eligible = normalized.loc[~normalized["is_demonstration"]].copy()

    report = {
        "rows_received": original_count,
        "valid_rows": int(len(normalized)),
        "eligible_non_demo_rows": int(len(eligible)),
        "demonstration_rows_excluded": int(
            normalized["is_demonstration"].sum()
        ),
        "conflicting_source_rows_excluded": conflicting_source_count,
        "missing_or_invalid_rows": int(
            original_count
            - len(normalized)
            - duplicate_count
            - conflicting_source_count
        ),
        "duplicate_rows_removed": duplicate_count,
        "distinct_zones": int(normalized["zone_id"].nunique()),
        "distinct_observation_dates": int(
            normalized["observation_date"].nunique()
        ),
        "eligible_distinct_zones": int(eligible["zone_id"].nunique()),
        "eligible_distinct_dates": int(
            eligible["observation_date"].nunique()
        ),
        "missing_optional_values": {
            column: int(normalized[column].isna().sum())
            for column in ("latitude", "longitude", "ndbi")
            if column in normalized
        },
        "sources": sorted(
            normalized["data_source"].dropna().astype(str).unique().tolist()
        ),
        "eligible_sources": sorted(
            eligible["data_source"].dropna().astype(str).unique().tolist()
        ),
        "provenance_note": (
            "Source identifiers and non-demonstration labels are not independently "
            "verified; review provider provenance and quality flags."
        ),
    }
    return normalized.reset_index(drop=True), eligible.reset_index(drop=True), report


def missing_feature_report(
    available_columns: Iterable[str],
    has_weather=False,
    has_air_quality=False,
    has_electricity=False,
):
    columns = set(available_columns)
    required = set(REQUIRED_COLUMNS)
    return {
        "required_environmental_fields_missing": sorted(required - columns),
        "optional_inputs_available": {
            "weather": bool(has_weather),
            "air_quality": bool(has_air_quality),
            "electricity": bool(has_electricity),
        },
        "note": (
            "Weather, air-quality, and electricity variables are not used unless "
            "they are stored and time-aligned with environmental observations."
        ),
    }
