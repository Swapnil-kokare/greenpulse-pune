import json
from pathlib import Path
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from utils import load_data, build_zone_summary, ROOT

OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

def main():
    df = load_data()
    summary = build_zone_summary(df)

    # One row per zone for clustering.
    feature_cols = ["mean_lst_c", "mean_ndvi"]
    if summary["mean_ndbi"].notna().sum() >= 3:
        summary["mean_ndbi"] = summary["mean_ndbi"].fillna(summary["mean_ndbi"].median())
        feature_cols.append("mean_ndbi")
    X = summary[feature_cols].copy()
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    n_clusters = min(4, max(2, len(summary) // 3))
    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    summary["cluster_id"] = model.fit_predict(Xs).astype(int)
    try:
        if len(summary) > n_clusters:
            sil = float(silhouette_score(Xs, summary["cluster_id"]))
        else:
            sil = None
    except Exception:
        sil = None

    # Regression across zone/date rows. These synthetic records are not real evidence.
    model_df = df.copy()
    features = ["ndvi"]
    if model_df["ndbi"].notna().sum() > 0:
        model_df["ndbi"] = model_df["ndbi"].fillna(model_df["ndbi"].median())
        features.append("ndbi")
    model_df["month"] = model_df["observation_date"].dt.month
    features.append("month")
    Xr = model_df[features].fillna(0)
    y = model_df["lst_celsius"]
    X_train, X_test, y_train, y_test = train_test_split(
        Xr, y, test_size=0.25, random_state=42
    )
    reg = RandomForestRegressor(n_estimators=150, random_state=42, min_samples_leaf=2)
    reg.fit(X_train, y_train)
    pred = reg.predict(X_test)
    metrics = {
        "dataset_note": "Synthetic demo data only; metrics are not real-world validation.",
        "rows": int(len(df)),
        "zones": int(df["zone_id"].nunique()),
        "cluster_count": int(n_clusters),
        "silhouette_score": sil,
        "regression_test_mae_c": float(mean_absolute_error(y_test, pred)),
        "regression_test_rmse_c": float(mean_squared_error(y_test, pred) ** 0.5),
        "regression_test_r2": float(r2_score(y_test, pred)),
        "features": features,
    }
    summary.to_csv(OUT / "zone_analysis.csv", index=False)
    with (OUT / "model_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Wrote {OUT / 'zone_analysis.csv'}")
    print(f"Wrote {OUT / 'model_metrics.json'}")
    print(json.dumps(metrics, indent=2))

if __name__ == "__main__":
    main()
