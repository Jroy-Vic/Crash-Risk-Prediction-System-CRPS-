import time
import requests
from datetime import datetime

BACKEND_URL = "http://Roys_MacBook:8000/predict"

SCENARIOS = [
    {
        "name": "LOW",
        "speed_mph": 82,
        "vehicle_speed_mph": 82,
        "speed_ratio": 1.0,
        "future_congestion_probability": 0.05,
        "recommended_speed_mph": 65,
        "flow_veh_per_interval": 35,
        "occupancy_pct": 4,
        "demo_probability": 0.05
    },
    {
        "name": "MEDIUM",
        "speed_mph": 52,
        "vehicle_speed_mph": 52,
        "speed_ratio": 0.80,
        "future_congestion_probability": 0.55,
        "recommended_speed_mph": 55,
        "flow_veh_per_interval": 90,
        "occupancy_pct": 14,
        "demo_probability": 0.55
    },
    {
        "name": "HIGH",
        "speed_mph": 28,
        "vehicle_speed_mph": 28,
        "speed_ratio": 0.43,
        "future_congestion_probability": 0.92,
        "recommended_speed_mph": 30,
        "flow_veh_per_interval": 180,
        "occupancy_pct": 38,
        "demo_probability": 0.92
    },
]

BASE_PAYLOAD = {
    "segment_id": "simulation_cycle",
    "station_id": "SIM",

    "latitude": 35.2828,
    "longitude": -120.6596,
    "heading_deg": 90,
    "horizon_seconds": 300,

    "free_flow_speed_mph": 65,
    "speed_limit_mph": 65,

    "temperature_f": 65,
    "visibility_miles": 10,
    "wind_speed_mph": 5,
    "precipitation_in": 0,
    "is_rain": 0,

    "hour": 12,
    "day_of_week": 3,
    "month": 5,
    "is_weekend": 0,
    "rush_hour": 0,
    "is_rush_hour": 0,
}


def send_scenario(scenario):
    payload = {
        **BASE_PAYLOAD,
        **scenario,
    }

    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=5)

        print(f"{datetime.now().strftime('%H:%M:%S')} → {scenario['name']}")

        if response.status_code != 200:
            print("ERROR:", response.status_code, response.text)
        else:
            data = response.json()
            print(
                f"   prob={round(data['congestion_probability_5min_ahead'], 3)} "
                f"speed={data['recommended_speed_mph']}"
            )

    except Exception as e:
        print("REQUEST FAILED:", e)


def main():
    delay_sec = 8

    while True:
        for scenario in SCENARIOS:
            send_scenario(scenario)
            time.sleep(delay_sec)


if __name__ == "__main__":
    main()