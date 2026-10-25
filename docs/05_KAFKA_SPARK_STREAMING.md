# 05. Kafka and Spark Structured Streaming

## Implemented workflow

`kafka_producer.py` reads the CSV selected by `GREENPULSE_DATASET_PATH` (default: `data/pune_demo_observations.csv`) and sends one JSON event per row to topic `pune-environmental-observations`. The default pause is 0.25 seconds. The producer waits for delivery/flush and prints its sent count. This is a replay demonstration, not live ingestion.

`spark_streaming.py` subscribes at `localhost:9092` from `startingOffsets=earliest`. It parses messages against the project schema, casts LST/NDVI to doubles, rejects missing zone IDs and null LST/NDVI, and aggregates by zone. The summary query uses `outputMode("complete")` and `foreachBatch`; each batch is committed with MySQL `executemany` and `ON DUPLICATE KEY UPDATE`. Its checkpoint is `outputs/checkpoints/kafka_stream`.

If the optional `environment_observations` table is present, a second append-mode `foreachBatch` sink groups events by zone, name, date, and source. It has its own checkpoint, `outputs/checkpoints/environment_observations`. If the table is absent, the script logs that the history sink is disabled and preserves the existing summary query.

## Kafka service and topic

`docker-compose.yml` defines a single-node KRaft Kafka image (`apache/kafka:3.7.0`) on host port `9092`. Compose sets three default partitions. Kafka auto-topic creation may be enabled by broker defaults; to create the application topic explicitly:

```powershell
docker compose up -d kafka
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic pune-environmental-observations --partitions 3 --replication-factor 1
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic pune-environmental-observations
```

Verify container CLI availability against the exact image if the topic command differs.

## Run commands

Install streaming Python dependencies:

```powershell
pip install -r requirements-streaming.txt
```

Start the producer in one terminal:

```powershell
python kafka_producer.py
```

Start Spark in another terminal after configuring MySQL environment variables:

```powershell
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.2.0 spark_streaming.py
```

The repository pins PySpark 4.2.0; the exact Maven connector coordinate/Scala binary version must match the installed Spark distribution. This command was not exercised end-to-end in this documentation pass; if dependency resolution fails, confirm the Scala version and use the matching published connector before retrying.

## Separate batch Spark script

`spark_batch.py` is not the streaming consumer. It reads the bundled CSV directly, casts and filters required columns, removes duplicate zone/date rows, calculates per-zone summary/priority fields, and writes Parquet to `outputs/spark_batch`. The script's default input is the same synthetic demo CSV.

## Persistence and replay considerations

The summary table has a unique key on `(batch_id, zone_id)`. Each Spark batch writes an aggregate per zone and updates the row when that same key is repeated. The history table uses `(zone_id, observation_date, data_source)` as its unique key and updates weighted means and `records_received` on repeats. Checkpointed Spark offsets and replayed records influence whether a record is processed again; the history upsert is designed to combine repeated records, not deduplicate arbitrary source files independent of source/date identity.

## Evidence and limitations

The inspected database showed batch 4, 18 zones, 288 records received, and a 2025-07-06 observation date. This confirms stored historical output visible to the application; it does not independently prove that Kafka or Spark was running at inspection. No current Kafka/Spark end-to-end log evidence was collected for this documentation task. Dashboard monitoring reports only limited Kafka TCP reachability and does not assert Spark health.

**Figure 5.1.** Producer-to-broker-to-Spark sequence, with MySQL writes and the conditional history sink. [Editable sequence diagram](diagrams/03_kafka_spark_sequence.mmd).

See [architecture](03_SYSTEM_ARCHITECTURE.md), [database behavior](06_DATABASE_DESIGN.md), [local runtime diagram](diagrams/07_local_runtime_architecture.mmd), and [execution instructions](10_SETUP_AND_EXECUTION.md).
