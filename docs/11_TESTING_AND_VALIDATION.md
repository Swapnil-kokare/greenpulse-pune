# 11. Testing and validation

## Test types and evidence

| Area | Evidence/status | Interpretation |
|---|---|---|
| Python syntax/imports | The earlier implementation validation compiled the Python modules and checked dependency availability. | This does not verify Kafka/Spark connectivity. |
| ML unit tests | `tests/test_ml_pipeline.py` contains eight tests for source validation, lag features, chronological splitting, heat thresholds, recommendations, metrics, and inference persistence. The documentation pass ran the command below: all eight tests passed. | Unit fixtures are synthetic/test data, not a model-quality claim. |
| Streamlit rendering | Prior AppTest confirmed overview and ML page rendered without app exceptions and that four ML chart elements and the synthetic-data disclosure appeared. | AppTest is headless component rendering, not a full browser compatibility test. |
| MySQL schema and read | Direct schema inspection and application data-readiness output confirmed MySQL connectivity, the summary schema, 18 summary rows, and an existing empty history table. | The snapshot reflects the local database state inspected; it does not establish future availability. |
| Kafka connectivity/message ingest | Not verified in this documentation pass. | A stored MySQL batch is historical evidence, not proof of current Kafka publish/consume operation. |
| Spark Structured Streaming | Source code and checkpoints are present; current streaming execution was not verified. | Connector resolution, runtime, and database writes must be tested in a configured local environment. |
| External API | Open-Meteo requests and error handling exist. A page inspection displayed a provider weather estimate; this is not a persistent data history. | API outputs are point estimates and network availability can change. |
| Geographic boundaries | CSV coordinate values are present, but the source marks the demo as synthetic and coordinates are not verified. No ward polygon dataset is included. | Marker display does not constitute precise ward mapping. |
| Empty/error states | Code includes DB errors and no-data messaging; the prior AppTest was successful. | Database failure state should be rechecked when credentials or local configuration change. |

## Run the focused unit suite

From the project root with `.venv` activated:

```powershell
python -m unittest tests.test_ml_pipeline -v
```

The test suite exercises:

- rejecting synthetic, unknown, and conflicting-source observations from real-data eligibility;
- building lags from earlier records only and creating future inputs with observed median cadence;
- chronological train/test separation;
- threshold edge cases and missing-value classification;
- recommendation evidence and synthetic exclusion in real mode;
- MAE/RMSE/R² input validation; and
- inference output identity, empirical uncertainty, and unverified coordinates.

## Recommended integration checks

These checks require a configured local broker, Spark installation, and MySQL database; they are not reported as completed here:

1. Start Kafka and inspect topic metadata.
2. Start the Spark consumer, publish a small known fixture, and confirm the `foreachBatch` count, aggregate values, checkpoint offsets, and MySQL row.
3. Replay a repeated zone/date/source and verify the history weighted mean and count update.
4. Stop/restart Spark and verify checkpoint recovery and no unintended duplicate count.
5. Test missing migration behavior: the summary sink should remain while the optional history sink logs its disabled state.
6. Test invalid coordinates, missing LST/NDVI, stale observations, DB outage, and unavailable Open-Meteo responses.
7. Use an independently verified dataset before evaluating the real-data ML acceptance rules.

No performance benchmark, security assessment, or production deployment test has been performed.
