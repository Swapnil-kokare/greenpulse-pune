import pandas as pd

from ml.config import FEATURE_COLUMNS, TARGET_COLUMN


def make_supervised_dataset(observations):
    """Build one-step-ahead features from only earlier observations per zone."""
    required = {
        "zone_id",
        "zone_name",
        "observation_date",
        "lst_celsius",
        "ndvi",
    }
    missing = required - set(observations.columns)
    if missing:
        raise ValueError(
            "Cannot build model features; columns are missing: "
            + ", ".join(sorted(missing))
        )

    data = observations.copy()
    data["observation_date"] = pd.to_datetime(
        data["observation_date"], errors="coerce"
    ).dt.normalize()
    data["lst_celsius"] = pd.to_numeric(data["lst_celsius"], errors="coerce")
    data["ndvi"] = pd.to_numeric(data["ndvi"], errors="coerce")
    data = data.dropna(
        subset=["zone_id", "observation_date", "lst_celsius", "ndvi"]
    )
    data = data.sort_values(["zone_id", "observation_date"]).drop_duplicates(
        ["zone_id", "observation_date"], keep="last"
    )
    grouped = data.groupby("zone_id", sort=False)
    data["lst_lag_1"] = grouped["lst_celsius"].shift(1)
    data["lst_lag_2"] = grouped["lst_celsius"].shift(2)
    data["ndvi_lag_1"] = grouped["ndvi"].shift(1)
    data["ndvi_lag_2"] = grouped["ndvi"].shift(2)
    data["previous_date"] = grouped["observation_date"].shift(1)
    data["days_since_previous"] = (
        data["observation_date"] - data["previous_date"]
    ).dt.days
    data["target_month"] = data["observation_date"].dt.month
    data["target_day_of_year"] = data["observation_date"].dt.dayofyear
    data = data.dropna(subset=list(FEATURE_COLUMNS) + [TARGET_COLUMN])
    data = data[data["days_since_previous"] > 0]
    return data.reset_index(drop=True)


def build_next_observation_features(observations):
    """Prepare future-row features using each zone's observed median cadence."""
    required = {"zone_id", "zone_name", "observation_date", "lst_celsius", "ndvi"}
    missing = required - set(observations.columns)
    if missing:
        raise ValueError(
            "Cannot build prediction inputs; columns are missing: "
            + ", ".join(sorted(missing))
        )

    data = observations.copy()
    data["observation_date"] = pd.to_datetime(
        data["observation_date"], errors="coerce"
    ).dt.normalize()
    data["lst_celsius"] = pd.to_numeric(data["lst_celsius"], errors="coerce")
    data["ndvi"] = pd.to_numeric(data["ndvi"], errors="coerce")
    data = data.dropna(
        subset=["zone_id", "observation_date", "lst_celsius", "ndvi"]
    ).sort_values(["zone_id", "observation_date"])
    predictions = []

    for zone_id, group in data.groupby("zone_id", sort=False):
        group = group.drop_duplicates("observation_date", keep="last")
        if len(group) < 2:
            continue
        previous = group.iloc[-1]
        prior = group.iloc[-2]
        intervals = group["observation_date"].diff().dt.days.dropna()
        intervals = intervals[intervals > 0]
        if intervals.empty:
            continue
        cadence_days = max(1, int(round(float(intervals.median()))))
        target_date = previous["observation_date"] + pd.to_timedelta(
            cadence_days, unit="D"
        )
        predictions.append(
            {
                "zone_id": str(zone_id),
                "zone_name": str(previous["zone_name"]),
                "input_observation_date": previous["observation_date"],
                "target_observation_date": target_date,
                "forecast_horizon_days": cadence_days,
                "lst_lag_1": float(previous["lst_celsius"]),
                "lst_lag_2": float(prior["lst_celsius"]),
                "ndvi_lag_1": float(previous["ndvi"]),
                "ndvi_lag_2": float(prior["ndvi"]),
                "days_since_previous": cadence_days,
                "target_month": int(target_date.month),
                "target_day_of_year": int(target_date.dayofyear),
            }
        )

    if not predictions:
        return pd.DataFrame()
    feature_columns = [column for column in FEATURE_COLUMNS if column != "zone_id"]
    return pd.DataFrame(predictions)[
        [
            "zone_id",
            "zone_name",
            "input_observation_date",
            "target_observation_date",
            "forecast_horizon_days",
            *feature_columns,
        ]
    ]
