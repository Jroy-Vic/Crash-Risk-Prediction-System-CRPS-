from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[1]
SENSOR_PATH = BASE_DIR / "state" / "latest_sensors.json"


def load_sensor_data():
    if not SENSOR_PATH.exists():
        return {
            "source": "none",
            "gps": {
                "fix_valid": False,
                "latitude": None,
                "longitude": None,
            },
            "imu": {
                "hard_brake": False,
                "sharp_turn": False,
            },
        }

    with open(SENSOR_PATH, "r") as f:
        return json.load(f)
    
    
def load_hardware_sensor_data():
    # This function can be expanded in the future to read from actual hardware sensors instead of a JSON file
    return 0