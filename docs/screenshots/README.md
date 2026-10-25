# Dashboard screenshots

These are genuine screenshots captured from the locally running GreenPulse Pune Streamlit app. They show the application UI, not mockups or standalone report charts. The displayed values can change with the database, provider responses, and dashboard refresh time.

## Gallery

1. [Pune overview](01_pune_overview.png) — latest-batch metrics, approximate zone map, and ranking. The visible database values are from the synthetic demonstration replay.
2. [Heat hotspots](02_heat_hotspots.png) — exploratory review threshold and map bands; not an official warning.
3. [Air quality](03_air_quality.png) — Open-Meteo provider/model estimates at one approximate Pune grid point, not ward-level monitoring-station measurements.
4. [Electricity hotspots](04_electricity_hotspots.png) — simulated illustrative index; no utility-meter or feeder-load data are connected.
5. [Zone Explorer](05_zone_explorer.png) — searchable latest-batch summary, not historical zone trends.
6. [ML predictions and data readiness](06_ml_predictions.png) — current summary and eligible-history status.
7. [ML synthetic-demo evidence](06_ml_predictions_outputs.png) — demo-only model metrics and the current absence of saved prediction/recommendation rows in MySQL.
8. [Data and pipeline status](07_data_pipeline_status.png) — database and broker indicators; Spark process health is explicitly not monitored.

## Capture notes

- The global dashboard badge identifies the historical dataset as synthetic demo values. Synthetic observations are not measured Pune conditions.
- CSV coordinates are approximate points, not verified ward boundaries.
- The air-quality values are provider/model estimates and may change or be unavailable on a later capture.
- The electricity index is simulated, not actual consumption or grid status.
- The ML metrics are based on the synthetic dataset; they do not establish real-world forecast skill.
- Database contents and service checks are a snapshot. A successful MySQL connection or Kafka TCP check does not prove current Spark or end-to-end pipeline execution.

To refresh these images, run the app locally, open the relevant sidebar page, and capture the visible UI at a desktop viewport. Keep the synthetic/provider/simulation disclosures visible where possible, avoid exposing credentials, and update the captions and report references whenever a screenshot is replaced.
