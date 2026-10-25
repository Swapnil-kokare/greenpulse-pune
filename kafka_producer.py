"""Replay historical CSV rows into Kafka; this is not a live satellite feed."""
import csv
import json
import os
import time
from pathlib import Path
from kafka import KafkaProducer
from kafka.errors import KafkaError

ROOT = Path(__file__).resolve().parent
CSV_PATH = Path(
    os.getenv(
        "GREENPULSE_DATASET_PATH",
        str(ROOT / "data" / "pune_demo_observations.csv"),
    )
).expanduser()
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "pune-environmental-observations")
DELAY_SECONDS = float(os.getenv("REPLAY_DELAY_SECONDS", "0.25"))

def json_serializer(value):
    return json.dumps(value).encode("utf-8")

def main():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=json_serializer,
        retries=5,
        acks="all",
    )
    sent = 0
    try:
        with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                for key in ["latitude", "longitude", "lst_celsius", "ndvi", "ndbi"]:
                    if row.get(key) not in (None, ""):
                        row[key] = float(row[key])
                if row.get("valid_pixel_count") not in (None, ""):
                    row["valid_pixel_count"] = int(float(row["valid_pixel_count"]))
                producer.send(TOPIC, row)
                sent += 1
                print(f"Published record {sent}: {row['zone_id']} / {row['observation_date']}")
                time.sleep(DELAY_SECONDS)
        producer.flush(timeout=30)
        print(f"Finished replay: {sent} records sent to topic '{TOPIC}'.")
    except KafkaError as exc:
        raise SystemExit(f"Kafka publish failed: {exc}") from exc
    finally:
        producer.close()

if __name__ == "__main__":
    main()
