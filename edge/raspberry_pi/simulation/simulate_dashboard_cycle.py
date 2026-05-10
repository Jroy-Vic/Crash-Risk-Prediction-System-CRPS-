import time
import json
from pathlib import Path
from datetime import datetime, timezone

STATE_PATH = Path("edge/raspberry_pi/state/latest_prediction.json")

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
    },
]

BASE_RESPONSE = {
    "segment_id": "simulation_cycle",
    "station_id": "SIM",

    "current_latitude": 35.2828,
    "current_longitude": -120.6596,
    "target_latitude": 35.2828,
    "target_longitude": -120.6596,

    "free_flow_speed_mph": 65,
    "speed_limit_mph": 65,

    "model_name": "demo_simulation",
    "mode": "simulation_cycle",
    "route_mode": "simulation_cycle",
    "inference_mode": "simulation",
    "backend_reachable": True,
    "accuracy_state": "normal",

    "temperature_f": 65,
    "visibility_miles": 10,
    "wind_speed_mph": 5,
    "precipitation_in": 0,
    "precipitation": 0,
    "is_rain": 0,

    "weather": {
        "temperature_f": 65,
        "visibility_miles": 10,
        "wind_speed_mph": 5,
        "precipitation_in": 0,
        "precipitation": 0,
        "is_rain": 0,
    },

    "route_ahead": {
        "latitude": 35.2828,
        "longitude": -120.6596,
        "horizon_seconds": 300,
        "distance_ahead_m": 1609,
        "eta_timestamp_utc": None,
        "mode": "simulation_cycle",
        "confidence": 1.0,
    },
}


def ml_confidence_from_probability(probability):
    return abs(probability - 0.5) * 2


def write_scenario(scenario):
    now = datetime.now(timezone.utc).isoformat()
    probability = scenario["future_congestion_probability"]

    output = {
        **BASE_RESPONSE,
        "current_speed_mph": scenario["speed_mph"],
        "vehicle_speed_mph": scenario["vehicle_speed_mph"],
        "speed_mph": scenario["speed_mph"],
        "speed_ratio": scenario["speed_ratio"],
        "current_congestion": probability >= 0.4,

        "target_traffic": {
            "speed_mph": scenario["speed_mph"],
            "free_flow_speed_mph": BASE_RESPONSE["free_flow_speed_mph"],
            "speed_ratio": scenario["speed_ratio"],
            "tomtom_raw": None,
        },

        "future_congestion_probability": probability,
        "congestion_probability_5min_ahead": probability,
        "ml_confidence": ml_confidence_from_probability(probability),
        "recommended_speed_mph": scenario["recommended_speed_mph"],

        "simulation_state": scenario["name"],
        "timestamp": now,
    }

    output["route_ahead"] = dict(BASE_RESPONSE["route_ahead"])
    output["route_ahead"]["eta_timestamp_utc"] = now

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(
        f"{datetime.now().strftime('%H:%M:%S')} → {scenario['name']} "
        f"prob={probability:.2f} speed={scenario['recommended_speed_mph']} "
        f"wrote={STATE_PATH}"
    )


def main():
    delay_sec = 8

    while True:
        for scenario in SCENARIOS:
            write_scenario(scenario)
            time.sleep(delay_sec)


if __name__ == "__main__":
    main()