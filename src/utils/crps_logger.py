# crps_logger.py

import csv
import json
from pathlib import Path
from datetime import datetime, timezone


class CRPSLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        self.csv_path = self.log_dir / "crps_predictions.csv"
        self.jsonl_path = self.log_dir / "crps_predictions.jsonl"

        self.fields = [
            "timestamp",
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

            "probability",
            "recommended_speed_mph",
            "speed_limit_mph",
            "risk_level",
            "mode",
            "source",
            "backend_status",
            "error",
        ]

        self._ensure_csv_header()

    def _ensure_csv_header(self):
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                writer.writeheader()
            return

        with open(self.csv_path, "r", newline="") as f:
            reader = csv.reader(f)
            existing_header = next(reader, None)

        if existing_header != self.fields:
            backup_path = self.csv_path.with_suffix(".old.csv")
            self.csv_path.rename(backup_path)

            with open(self.csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.fields)
                writer.writeheader()

            print(f"Log schema changed. Old log backed up to: {backup_path}")

    def log_prediction(self, data: dict):
        row = {field: data.get(field, "") for field in self.fields}

        if not row["timestamp"]:
            row["timestamp"] = datetime.now(timezone.utc).isoformat()

        with open(self.csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            writer.writerow(row)

        with open(self.jsonl_path, "a") as f:
            f.write(json.dumps(row) + "\n")

def get_risk_level(probability: float) -> str:
    if probability >= 0.70:
        return "HIGH"
    elif probability >= 0.40:
        return "MEDIUM"
    return "LOW"