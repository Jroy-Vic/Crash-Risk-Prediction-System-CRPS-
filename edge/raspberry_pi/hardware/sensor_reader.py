from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[2]
SENSOR_PATH = BASE_DIR / "edge" / "raspberry_pi" / "state" / "latest_sensors.json"


def load_latest_sensors():
    if not SENSOR_PATH.exists():
        return None

    try:
        with open(SENSOR_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return None