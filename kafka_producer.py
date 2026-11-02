"""Replay historical CSV rows into Kafka; this is not a live satellite feed."""
import argparse
import csv
import json
import os
import random
import time
from datetime import date
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


def _read_rows():
    with CSV_PATH.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        for key in ["latitude", "longitude", "lst_celsius", "ndvi", "ndbi"]:
            if row.get(key) not in (None, ""):
                row[key] = float(row[key])
        if row.get("valid_pixel_count") not in (None, ""):
            row["valid_pixel_count"] = int(float(row["valid_pixel_count"]))
    return rows


def _live_demo_record(source_row, cycle, row_number, observation_date):
    row = source_row.copy()
    rng = random.Random(cycle * 1_000_003 + row_number)
    row["lst_celsius"] = round(
        max(-50.0, min(80.0, row["lst_celsius"] + rng.uniform(-2.0, 2.0))),
        2,
    )
    row["ndvi"] = round(
        max(-1.0, min(1.0, row["ndvi"] + rng.uniform(-0.04, 0.04))),
        3,
    )
    if row.get("ndbi") not in (None, ""):
        row["ndbi"] = round(
            max(-1.0, min(1.0, row["ndbi"] + rng.uniform(-0.04, 0.04))),
            3,
        )
    row["observation_date"] = observation_date
    row["data_source"] = "SYNTHETIC_LIVE_DEMO_NOT_REAL"
    return row


def main():
    parser = argparse.ArgumentParser(
        description="Replay the bundled CSV to Kafka, optionally as changing demo data."
    )
    parser.add_argument(
        "--live-demo",
        action="store_true",
        help=(
            "Continuously replay clearly labelled synthetic readings with small "
            "changes each cycle until Ctrl+C."
        ),
    )
    args = parser.parse_args()
    rows = _read_rows()
    if not rows:
        raise ValueError(f"No observations found in CSV: {CSV_PATH}")

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=json_serializer,
        retries=5,
        acks="all",
    )
    sent = 0
    cycle = 0
    try:
        while True:
            cycle += 1
            observation_date = date.today().isoformat()
            cycle_sent = 0
            if args.live_demo:
                print(
                    f"Starting synthetic live-demo cycle {cycle} "
                    f"for {observation_date}."
                )
            for row_number, source_row in enumerate(rows):
                row = (
                    _live_demo_record(
                        source_row, cycle, row_number, observation_date
                    )
                    if args.live_demo
                    else source_row
                )
                producer.send(TOPIC, row)
                sent += 1
                cycle_sent += 1
                if not args.live_demo:
                    print(
                        f"Published record {sent}: {row['zone_id']} / "
                        f"{row['observation_date']}"
                    )
                time.sleep(DELAY_SECONDS)
            producer.flush(timeout=30)
            if not args.live_demo:
                print(
                    f"Finished replay: {sent} records sent to topic '{TOPIC}'."
                )
                break
            print(f"Published {cycle_sent} records in cycle {cycle}.")
    except KafkaError as exc:
        raise SystemExit(f"Kafka publish failed: {exc}") from exc
    except KeyboardInterrupt:
        print(f"Stopped live demo after publishing {sent} records.")
    finally:
        producer.close()

if __name__ == "__main__":
    main()
