# 04. End-to-end workflow

## Data flow

The optional pipeline starts when a user runs the Python CSV producer. It reads records sequentially, casts coordinate and environmental fields to numeric types, serializes each row as JSON, and publishes the row to Kafka. The default file is the bundled synthetic dataset; selecting a verified external CSV requires explicitly setting `GREENPULSE_DATASET_PATH` and checking its schema and provenance.

Spark Structured Streaming subscribes to `pune-environmental-observations` from the earliest offsets. It parses JSON against a defined schema, casts LST and NDVI, and filters records lacking a zone ID or required numeric indicators. The summary query groups by `zone_id` and `zone_name`, computes count, mean LST, mean NDVI, and maximum observation date, then writes each micro-batch to MySQL.

When `environment_observations` exists, a second streaming query aggregates by zone, date, and source and persists the result using a separate checkpoint. This is an additive path; it does not change the established summary table. Duplicate zone/date/source records are combined by weighted means and their count is accumulated.

The dashboard loads the latest batch from MySQL. A separate CSV lookup supplies approximate marker coordinates and source labels by matching zone IDs because the summary table itself has neither coordinates nor provenance. Open-Meteo estimates are requested directly by the UI when relevant. Synthetic demo ML reads its bundled CSV and writes separate local artifacts; real inference uses a reviewed model and eligible history, then persists outputs to the ML tables.

## Timing and freshness

Three times should not be conflated:

1. **Observation date** — date carried with an environmental record.
2. **Processing timestamp** — MySQL `processed_at` or the ML output creation timestamp.
3. **Dashboard refresh time** — when the Streamlit UI reloads cached/source data.

A new dashboard timestamp does not update the observation date. A recent processing time can describe a replay of an old observation.

## Operating order for the optional streaming path

1. Start the local Kafka broker.
2. Verify or create the topic.
3. Configure the database environment for Spark.
4. Start Spark Structured Streaming.
5. Start the producer/replay.
6. Check console output and MySQL rows.
7. Open or refresh Streamlit.

The producer can publish before Spark is ready because the consumer starts at earliest offsets, subject to topic retention and checkpoint state. Replays can therefore reprocess old rows, and checkpoints persist offsets across restarts. The code does not constitute a continuously supplied environmental feed.

## Mermaid sequence

See [the Kafka/Spark sequence diagram](diagrams/03_kafka_spark_sequence.mmd) for producer, broker, Spark, and MySQL interactions.

**Figure 4.1.** End-to-end flow from CSV replay through Spark persistence and optional model inference. The flow distinguishes the latest-batch summary from conditional history storage; provider estimates enter the dashboard separately. [Editable diagram source](diagrams/02_end_to_end_data_flow.mmd).

The dashboard workflow is described in [chapter 09](09_DASHBOARD_AND_USER_WORKFLOW.md).
