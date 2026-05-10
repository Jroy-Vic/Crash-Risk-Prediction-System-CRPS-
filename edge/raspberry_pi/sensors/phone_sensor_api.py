import json
from pathlib import Path
from fastapi import APIRouter, Request

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[1]
SENSOR_PATH = BASE_DIR / "state" / "latest_sensors.json"


@router.post("/api/sensors/update")
async def update_phone_sensors(request: Request):
    data = await request.json()

    data["source"] = "phone"

    SENSOR_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(SENSOR_PATH, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "ok", "source": "phone"}