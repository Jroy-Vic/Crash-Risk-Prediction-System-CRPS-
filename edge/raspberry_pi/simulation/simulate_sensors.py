import json
import math
import random
import time
from pathlib import Path
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / ".." / "state"
SENSOR_STATE_PATH = STATE_DIR / "latest_sensors.json"

STATE_DIR.mkdir(parents=True, exist_ok=True)


ROUTE = [
    (35.2368, -120.6425),
    (35.2380, -120.6410),
    (35.2400, -120.6392),
    (35.2425, -120.6378),
    (35.2450, -120.6360),
]


def interpolate(p1, p2, t):
    lat = p1[0] + (p2[0] - p1[0]) * t
    lon = p1[1] + (p2[1] - p1[1]) * t
    return lat, lon


def compute_heading(p1, p2):
    lat1 = math.radians(p1[0])
    lat2 = math.radians(p2[0])
    dlon = math.radians(p2[1] - p1[1])

    x = math.sin(dlon) * math.cos(lat2)
    y = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    )

    heading = math.degrees(math.atan2(x, y))
    return (heading + 360) % 360


def make_sensor_payload(lat, lon, heading, speed_mph, scenario):
    hard_brake = scenario == "hard_brake"
    sharp_turn = scenario == "sharp_turn"

    accel_x = random.uniform(-0.05, 0.05)
    accel_y = random.uniform(-0.08, 0.08)
    accel_z = 9.81 + random.uniform(-0.05, 0.05)
    gyro_z = random.uniform(-0.01, 0.01)

    if hard_brake:
        accel_y = random.uniform(-3.5, -2.2)

    if sharp_turn:
        accel_x = random.uniform(2.0, 3.2)
        gyro_z = random.uniform(0.25, 0.55)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "simulated",

        "gps": {
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "vehicle_speed_mph": round(speed_mph, 1),
            "heading_deg": round(heading, 1),
            "gps_quality": "simulated",
            "fix_valid": True,
        },

        "imu": {
            "accel_x_mps2": round(accel_x, 3),
            "accel_y_mps2": round(accel_y, 3),
            "accel_z_mps2": round(accel_z, 3),
            "gyro_z_rps": round(gyro_z, 3),
            "hard_brake": hard_brake,
            "sharp_turn": sharp_turn,
            "imu_quality": "simulated",
        },

        "scenario": scenario,
    }


def write_payload(payload):
    with open(SENSOR_STATE_PATH, "w") as f:
        json.dump(payload, f, indent=2)


def main():
    print(f"Writing simulated GPS/IMU data to: {SENSOR_STATE_PATH}")

    i = 0

    while True:
        segment_index = i % (len(ROUTE) - 1)
        step = (i % 20) / 20.0

        p1 = ROUTE[segment_index]
        p2 = ROUTE[segment_index + 1]

        lat, lon = interpolate(p1, p2, step)
        heading = compute_heading(p1, p2)

        cycle = i % 60

        if 20 <= cycle < 25:
            scenario = "hard_brake"
            speed_mph = max(15, 55 - (cycle - 20) * 7)
        elif 40 <= cycle < 47:
            scenario = "sharp_turn"
            speed_mph = 35
        else:
            scenario = "normal"
            speed_mph = 55 + random.uniform(-3, 3)

        payload = make_sensor_payload(
            lat=lat,
            lon=lon,
            heading=heading,
            speed_mph=speed_mph,
            scenario=scenario,
        )

        write_payload(payload)

        print(
            f"{payload['timestamp']} | "
            f"{scenario} | "
            f"speed={payload['gps']['vehicle_speed_mph']} mph | "
            f"lat={payload['gps']['latitude']} lon={payload['gps']['longitude']}"
        )

        i += 1
        time.sleep(1)


if __name__ == "__main__":
    main()