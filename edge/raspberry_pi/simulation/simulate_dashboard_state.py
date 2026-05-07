import json
from pathlib import Path
from datetime import datetime

STATE_PATH = Path("edge/raspberry_pi/state/latest_prediction.json")

state = {
    "timestamp": datetime.now().isoformat(),
    "segment_id": "simulation_high_congestion",
    "station_id": "SIM",
    "speed_mph": 18,
    "free_flow_speed_mph": 65,
    "speed_ratio": 0.28,
    "speed_limit_mph": 65,
    "future_congestion_probability": 0.983,
    "recommended_speed_mph": 30,
    "mode": "simulation"
}

STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(STATE_PATH, "w") as f:
    json.dump(state, f, indent=2)

print("Wrote simulated high-congestion dashboard state.")