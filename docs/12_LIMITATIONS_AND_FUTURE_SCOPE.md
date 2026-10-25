# 12. Limitations and future scope

## Observed limitations

| Limitation | Effect on interpretation | Reasonable next step |
|---|---|---|
| Bundled LST/NDVI CSV is labelled `SYNTHETIC_DEMO_NOT_REAL`. | Its statistics, maps, predictions, and recommendations cannot describe measured Pune conditions. | Replace only after documenting dataset provenance, units, quality flags, license, and observation dates. |
| Latest MySQL summary has one observation date and is not a time series. | It supports a latest-batch comparison, not temporal trend or reliable forecasting. | Collect source-consistent observations repeatedly; retain the history sink and monitor data quality. |
| The additive history table was empty in the inspected database. | No eligible real-data training population was available. | Apply/verify the migration and ingest adequate verified history. |
| CSV coordinates are approximate and unverified. | Marker locations are illustrative; they do not identify official ward boundaries or precise hotspots. | Obtain validated ward/grid geometries and perform a documented spatial join. |
| Zone-level air-quality time series are absent. | A single Open-Meteo grid estimate cannot be compared as if it were ward/station data. | Use validated stations or spatially resolved, timestamped observations and retain source metadata. |
| Electricity values are simulated/illustrative. | They cannot quantify consumption, peak demand, or utility impact. | Connect authorized meter/feeder data with time and geography alignment. |
| Demo model has a small two-date chronological holdout and negative R². | Synthetic holdout metrics are weak evidence, and do not demonstrate useful generalization. | Collect multi-season verified data and compare with strong time-aware baselines on a larger untouched holdout. |
| Empirical error band uses holdout residual quantiles. | It is not a calibrated probability interval or guarantee of future coverage. | Evaluate calibration and coverage on sufficiently large, independent future periods. |
| Recommendation rules use thresholds and feature associations. | They do not establish causality, feasibility, benefits, or official alert status. | Validate thresholds and proposed interventions with experts, local context, and outcome measurements. |
| Dashboard does not monitor Spark process health or Kafka protocol/consumer state. | A green database read or TCP probe is not proof of a healthy end-to-end pipeline. | Add explicit producer/consumer health metrics, lag and batch monitoring, and alerting if moving beyond a demo. |
| Local development configuration only. | Authentication, deployment hardening, backups, operational reliability, and scale have not been verified. | Define a deployment/security model and test it before public or operational use. |

## Future scope (not implemented)

1. Collect a larger verified LST/NDVI history with seasonal coverage and quality screening.
2. Add licensed/verified ward or grid polygons and spatially precise visualizations.
3. Integrate station-level air-quality data with measured timestamps and coordinates.
4. Obtain authorized electricity consumption data; remove the illustrative index unless clearly retained as a demo.
5. Compare temporal models with persistence, seasonal, and other appropriate baselines; track model drift and calibration.
6. Add monitored Kafka/Spark status, data-quality reporting, and automated integration tests.
7. Evaluate recommendations with local stakeholders and measured before/after outcomes.
8. Consider secure deployment, authentication, database least privilege, backups, and privacy review.

The project's current outputs are information and software demonstrations, not evidence of reduced urban temperature, improved air quality, or lower electricity use.
