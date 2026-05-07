import json
import time
from pathlib import Path
from datetime import datetime


STATE_PATH = Path("edge/raspberry_pi/state/latest_prediction.json")

SCENARIOS = [
    {
        "name": "LOW",
        "speed_mph": 69,
        "speed_ratio": 1.0,
        "future_congestion_probability": 0.05,
        "recommended_speed_mph": 65,
    },
    {
        "name": "MEDIUM",
        "speed_mph": 52,
        "speed_ratio": 0.80,
        "future_congestion_probability": 0.55,
        "recommended_speed_mph": 55,
    },
    {
        "name": "HIGH",
        "speed_mph": 28,
        "speed_ratio": 0.43,
        "future_congestion_probability": 0.92,
        "recommended_speed_mph": 30,
    },
]

BASE_STATE = {
    "segment_id": "simulation_cycle",
    "station_id": "SIM",
    "free_flow_speed_mph": 65,
    "speed_limit_mph": 65,
    "mode": "simulation",
}


def write_state(scenario):
    state = {
        **BASE_STATE,
        **scenario,
        "timestamp": datetime.now().isoformat(),
    }

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Wrote {scenario['name']} risk state")


def main():
    delay_sec = 8

    while True:
        for scenario in SCENARIOS:
            write_state(scenario)
            time.sleep(delay_sec)


if __name__ == "__main__":
    main()