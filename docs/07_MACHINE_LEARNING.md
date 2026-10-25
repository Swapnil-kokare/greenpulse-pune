# 07. Machine-learning methodology and status

## Implemented modes

The `ml/` package has two intentionally distinct paths:

1. **Real-data path:** reads eligible rows from MySQL `environment_observations`. The validation layer excludes synthetic, simulated, demo, illustrative, unknown, unverified, missing-source, invalid, duplicate, and conflicting-source records. A source identifier is a label, not independent proof of provenance.
2. **Explicit synthetic demo path:** `python -m ml.train_model --demo` reads the bundled CSV, uses relaxed demo-only readiness minimums, labels all artifacts synthetic, and writes them under `outputs/ml/demo_artifacts/`. Demo inference is explicitly invoked with `python -m ml.predict --demo`. It does not write synthetic predictions or recommendations to MySQL and does not replace the real-data model.

The older root-level `ml_analysis.py` is separate from these modes. It clusters per-zone summary values with K-means and fits a Random Forest using a random train/test split, then writes `outputs/zone_analysis.csv` and `outputs/model_metrics.json`. It uses synthetic observations and a non-chronological split, so its regression metrics are not evidence of future-date forecasting skill.

## Prediction objective and features

The target is the next observed zone-level land-surface temperature in Celsius. It is **not a daily forecast**. Each zone's median positive observation interval determines the target date/horizon. Features include zone ID, the two most recent LST values, the two most recent NDVI values, days since the previous record, target month, and target day-of-year. Rows are sorted per zone/date; the first two records per zone cannot produce a supervised row. Invalid required values are dropped rather than imputed.

The candidate is a scikit-learn pipeline using one-hot zone encoding and a 300-tree `RandomForestRegressor`. The baseline is `DummyRegressor(strategy="mean")`. The split is chronological: earlier dates for training and later dates held out. A model is accepted in the real-data workflow only when candidate MAE improves by at least 5% and candidate RMSE is no worse than baseline.

## Readiness rules

The real-data path requires at least 100 eligible observations, 30 distinct dates, five zones, 20 held-out supervised observations, and five held-out dates. It also needs sufficient per-zone history for lag features and a chronological split. The synthetic demo has separate minimums (50 rows, eight dates, five zones, 20 test rows, and two test dates) to illustrate the workflow. Passing demo criteria does not establish real-data readiness.

At the inspected state, the MySQL history table had zero rows and no eligible non-demonstration history. The saved readiness snapshot reported the bundled CSV as 144 valid rows, 18 zones, eight dates, zero eligible non-demo rows, and 144 synthetic rows excluded. Therefore, no real-data training result is available.

## Saved synthetic-only evaluation

The latest inspected demo report is `outputs/ml/demo_artifacts/training_report.json`, model version `lst-next-observation-demo-20261025T190311Z`. It used 144 validated demo observations, generated 108 supervised rows, trained on 72 rows, and evaluated 36 later rows over two dates (2025-06-20 and 2025-07-06). The report explicitly identifies all of these as synthetic-only results.

| Model on synthetic chronological holdout | MAE (°C) | RMSE (°C) | R² |
|---|---:|---:|---:|
| Mean baseline | 3.661 | 4.104 | -3.893 |
| Random Forest candidate | 2.009 | 2.465 | -0.765 |

The candidate beats the configured demo acceptance comparison, but both R² scores are negative, indicating that these predictions are worse than predicting the held-out target mean under the R² reference definition. The small two-date holdout, generated data, and possible synthetic pattern leakage mean this should be treated as a software demonstration, not evidence that the model predicts Pune temperatures. No statistical confidence or real-world accuracy claim is warranted.

## Inference, uncertainty, and artifacts

The real inference command loads only the accepted artifact from `outputs/ml/artifacts/`, checks that it is not stale relative to available history, builds a next-observation input per zone, rejects implausible predictions outside the code's validated range, estimates an error-band width from the 90th percentile of absolute chronological holdout residuals, then saves predictions and recommendations. That band is empirical and is not a calibrated probability interval or coverage guarantee.

The demo model, metadata, report, predictions, and recommendation evidence live separately under `outputs/ml/demo_artifacts/`. Versioned `.joblib` model files and `latest.json` identify model metadata; outputs are generated files, not source data.

**Figure 7.1.** Real and demo training branches converge on a chronological evaluation shape but retain separate artifacts and output persistence. [Editable ML workflow diagram](diagrams/04_ml_training_inference.mmd).

## Distinguishing ML stages

| Stage | Meaning in this application |
|---|---|
| Stream processing | Kafka/Spark parses, filters, aggregates, and persists incoming/replayed observations. |
| Model training | Prepares eligible history and fits baseline/candidate regression models. |
| Model evaluation | Measures predictions on later chronological dates and applies acceptance criteria. |
| Model inference | Uses an accepted artifact and recent zone history to estimate the next observation. |
| Hotspot classification | Maps observed or predicted LST to configurable exploratory temperature bands. |
| Recommendation generation | Applies separate heuristic rules to qualifying evidence; it is not model training or proof of intervention benefit. |

## Retraining and remaining requirements

Real training should be run only after verified data accumulate and provenance, units, quality flags, coverage, and coordinates are reviewed. Establish a repeatable observation schedule, collect many more dates per zone (including seasonal coverage), compare against simple seasonal baselines, preserve held-out dates, and monitor drift before using results beyond demonstration. See [hotspot rules](08_HOTSPOT_AND_RECOMMENDATION_ENGINE.md), [data provenance](13_DATA_SOURCES_AND_REFERENCES.md), and [limitations](12_LIMITATIONS_AND_FUTURE_SCOPE.md).
