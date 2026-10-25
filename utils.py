from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "pune_demo_observations.csv"

REQUIRED_COLUMNS = [
    "zone_id", "zone_name", "latitude", "longitude",
    "observation_date", "lst_celsius", "ndvi"
]

def load_data(path=DATA_PATH):
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    for col in ["latitude", "longitude", "lst_celsius", "ndvi"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["zone_id", "latitude", "longitude", "observation_date", "lst_celsius", "ndvi"])
    df = df.drop_duplicates(subset=["zone_id", "observation_date"])
    if "ndbi" not in df.columns:
        df["ndbi"] = np.nan
    if "valid_pixel_count" not in df.columns:
        df["valid_pixel_count"] = np.nan
    if "data_source" not in df.columns:
        df["data_source"] = "unknown"
    return df.sort_values(["observation_date", "zone_id"]).reset_index(drop=True)

def build_zone_summary(df):
    summary = (
        df.groupby(["zone_id", "zone_name"], as_index=False)
        .agg(
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
            mean_lst_c=("lst_celsius", "mean"),
            max_lst_c=("lst_celsius", "max"),
            mean_ndvi=("ndvi", "mean"),
            mean_ndbi=("ndbi", "mean"),
            observation_count=("observation_date", "nunique"),
        )
    )
    # Min-max normalization; guard against a constant column.
    def norm(series):
        lo, hi = series.min(), series.max()
        if pd.isna(lo) or pd.isna(hi) or hi == lo:
            return pd.Series(0.5, index=series.index)
        return (series - lo) / (hi - lo)
    summary["heat_score"] = norm(summary["mean_lst_c"])
    summary["vegetation_score"] = norm(summary["mean_ndvi"])
    summary["priority_score"] = 0.5 * summary["heat_score"] + 0.5 * (1 - summary["vegetation_score"])
    summary["priority_tier"] = pd.cut(
        summary["priority_score"],
        bins=[-0.001, 0.33, 0.66, 1.001],
        labels=["Lower", "Moderate", "Higher"],
        include_lowest=True,
    ).astype(str)
    return summary.sort_values("priority_score", ascending=False).reset_index(drop=True)
