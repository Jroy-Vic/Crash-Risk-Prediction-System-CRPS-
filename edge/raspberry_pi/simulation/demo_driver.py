# Demo driver to simulate GPS/IMU data for testing the dashboard and backend integration without needing real hardware.
# Updates latest_sensors.json instead of latest_prediction.json
# Note: Must run client.py simultaneously to see the effect of the simulated sensor data on the predictions.

import json
import math
import time
from pathlib import Path
from datetime import datetime, timezone

STATE_DIR = Path("edge/raspberry_pi/state")
SENSOR_PATH = STATE_DIR / "latest_sensors.json"

BASE_LAT = 35.2368
BASE_LON = -120.6425

EARTH_METERS_PER_DEG_LAT = 111_320


def move_position(lat, lon, heading_deg, distance_m):
    heading = math.radians(heading_deg)

    d_lat = (distance_m * math.cos(heading)) / EARTH_METERS_PER_DEG_LAT
    d_lon = (distance_m * math.sin(heading)) / (
        EARTH_METERS_PER_DEG_LAT * math.cos(math.radians(lat))
    )

    return lat + d_lat, lon + d_lon


def scenario(t):
    phase = t % 60

    if phase < 15:
        return {
            "name": "normal_cruise",
            "speed_mph": 62,
            "heading_deg": 315,
            "hard_brake": False,
            "sharp_turn": False,
        }

    if phase < 30:
        return {
            "name": "slowing_traffic",
            "speed_mph": 42,
            "heading_deg": 315,
            "hard_brake": False,
            "sharp_turn": False,
        }

    if phase < 40:
        return {
            "name": "hard_brake_event",
            "speed_mph": 18,
            "heading_deg": 315,
            "hard_brake": True,
            "sharp_turn": False,
        }

    if phase < 50:
        return {
            "name": "sharp_turn_event",
            "speed_mph": 28,
            "heading_deg": 20,
            "hard_brake": False,
            "sharp_turn": True,
        }

    return {
        "name": "recovery",
        "speed_mph": 55,
        "heading_deg": 315,
        "hard_brake": False,
        "sharp_turn": False,
    }


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    lat = BASE_LAT
    lon = BASE_LON
    last_time = time.time()

    print("Demo driver running. Writing simulated GPS/IMU data...")

    while True:
        now = time.time()
        dt = now - last_time
        last_time = now

        sim = scenario(int(now))
        speed_mps = sim["speed_mph"] * 0.44704
        distance_m = speed_mps * dt

        lat, lon = move_position(
            lat,
            lon,
            sim["heading_deg"],
            distance_m,
        )

        sensor_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenario": sim["name"],
            "gps": {
                "fix_valid": True,
                "latitude": lat,
                "longitude": lon,
                "speed_mph": sim["speed_mph"],
                "heading_deg": sim["heading_deg"],
            },
            "imu": {
                "hard_brake": sim["hard_brake"],
                "sharp_turn": sim["sharp_turn"],
                "accel_x": -0.75 if sim["hard_brake"] else 0.05,
                "accel_y": 0.65 if sim["sharp_turn"] else 0.02,
                "yaw_rate_deg_s": 35 if sim["sharp_turn"] else 2,
            },
        }

        with open(SENSOR_PATH, "w") as f:
            json.dump(sensor_data, f, indent=2)

        print(
            f"{sim['name']} | "
            f"lat={lat:.6f}, lon={lon:.6f}, "
            f"speed={sim['speed_mph']} mph, "
            f"heading={sim['heading_deg']}°"
        )

        time.sleep(20)


if __name__ == "__main__":
    main()