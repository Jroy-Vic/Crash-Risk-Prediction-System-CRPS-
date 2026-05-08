# tools/replay_logs.py

import csv
import json
import time
import argparse
from pathlib import Path

import requests


DEFAULT_LOG_PATH = Path("logs/crps_predictions.csv")
DEFAULT_OUTPUT_PATH = Path("logs/replay_results.csv")
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000/predict"


PAYLOAD_FIELDS = [
    "segment_id",
    "latitude",
    "longitude",

    "speed_mph",
    "free_flow_speed_mph",
    "speed_ratio",
    "flow",
    "occupancy",

    "temperature_f",
    "visibility_miles",
    "wind_speed_mph",
    "precipitation",
    "is_rain",

    "hour",
    "day_of_week",
    "rush_hour",

    "speed_limit_mph",
]


def clean_value(value):
    if value is None or value == "":
        return None

    if isinstance(value, str):
        value = value.strip()

    if value in ["True", "true"]:
        return True
    if value in ["False", "false"]:
        return False

    try:
        if "." in str(value):
            return float(value)
        return int(value)
    except ValueError:
        return value


def build_payload(row):
    payload = {}

    # Direct fields
    direct_fields = [
        "latitude",
        "longitude",
        "speed_mph",
        "free_flow_speed_mph",
        "speed_ratio",
        "temperature_f",
        "visibility_miles",
        "wind_speed_mph",
        "precipitation",
        "is_rain",
        "hour",
        "day_of_week",
        "speed_limit_mph",
        "speed_delta_5min",
        "speed_delta_15min",
        "speed_rolling_mean_15min",
        "speed_rolling_std_15min",
        "flow_rolling_mean_15min",
        "occupancy_rolling_mean_15min",
        "is_low_visibility",
        "precipitation_in",
        "crash_count_current_window",
        "crash_count_past_1hr",
        "crash_count_past_24hr",
        "crash_count_past_7d",
    ]

    for field in direct_fields:
        if field in row:
            value = clean_value(row[field])
            if value is not None:
                payload[field] = value

    # Backend schema aliases
    id_value = row.get("segment_id") or row.get("station_id")

    payload["segment_id"] = id_value
    payload["station_id"] = id_value

    payload["flow_veh_per_interval"] = clean_value(row.get("flow"))
    payload["occupancy_pct"] = clean_value(row.get("occupancy"))
    payload["is_rush_hour"] = clean_value(row.get("rush_hour"))

    # Derived fields
    timestamp = row.get("timestamp")
    if timestamp:
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        payload["month"] = dt.month

    day_of_week = clean_value(row.get("day_of_week"))
    if day_of_week is not None:
        payload["is_weekend"] = int(day_of_week >= 5)

    return payload


def replay_row(payload, backend_url):
    response = requests.post(
        backend_url,
        json=payload,
        timeout=5,
    )

    if response.status_code != 200:
        print("\nPayload sent:")
        print(json.dumps(payload, indent=2))
        print("\nBackend response:")
        print(response.text)

    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Replay CRPS logs through backend.")
    parser.add_argument("--input", default=DEFAULT_LOG_PATH)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--backend", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=0.0)

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(exist_ok=True)

    if not input_path.exists():
        print(f"Log file not found: {input_path}")
        return

    results = []

    with open(input_path, "r", newline="") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            if args.limit is not None and i >= args.limit:
                break

            payload = build_payload(row)

            old_probability = clean_value(row.get("probability"))
            old_speed = clean_value(row.get("recommended_speed_mph"))

            try:
                new_result = replay_row(payload, args.backend)

                new_probability = new_result.get("future_congestion_probability")
                new_speed = new_result.get("recommended_speed_mph")

                probability_delta = (
                    new_probability - old_probability
                    if old_probability is not None and new_probability is not None
                    else None
                )

                speed_delta = (
                    new_speed - old_speed
                    if old_speed is not None and new_speed is not None
                    else None
                )

                replay_status = "ok"
                error = ""

            except Exception as e:
                new_probability = None
                new_speed = None
                probability_delta = None
                speed_delta = None
                replay_status = "failed"
                error = str(e)

            drift_flag = (
                probability_delta is not None and
                abs(probability_delta) > 0.20
            )

            results.append({
                "original_timestamp": row.get("timestamp"),
                "segment_id": row.get("segment_id"),

                "old_probability": old_probability,
                "new_probability": new_probability,
                "probability_delta": probability_delta,
                "drift_flag": drift_flag,

                "old_recommended_speed_mph": old_speed,
                "new_recommended_speed_mph": new_speed,
                "speed_delta": speed_delta,

                "old_risk_level": row.get("risk_level"),
                "old_mode": row.get("mode"),
                "replay_status": replay_status,
                "error": error,

                "payload_json": json.dumps(payload),
            })

            print(
                f"[{i + 1}] {replay_status} | "
                f"old_prob={old_probability} new_prob={new_probability} | "
                f"old_speed={old_speed} new_speed={new_speed}"
            )

            if args.sleep > 0:
                time.sleep(args.sleep)

    if not results:
        print("No rows replayed.")
        return

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\nReplay complete.")
    print(f"Rows replayed: {len(results)}")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()