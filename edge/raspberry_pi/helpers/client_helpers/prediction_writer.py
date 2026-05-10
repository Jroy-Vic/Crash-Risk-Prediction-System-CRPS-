import json
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[2]
STATE_PATH = BASE_DIR / "state" / "latest_prediction.json"

def write_latest_prediction(result):
    output = dict(result)
    output["dashboard_updated_at"] = datetime.now(timezone.utc).isoformat()

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print("--------------------------------")
    print(" ")
    print("WROTE latest prediction to:", STATE_PATH.resolve())
    print(" ")
    print("--------------------------------")