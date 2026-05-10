from pathlib import Path
import json
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from hardware.phone_sensor_api import router as phone_sensor_router
from fastapi.staticfiles import StaticFiles
import uvicorn


BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
STATE_PATH = BASE_DIR / "state" / "latest_prediction.json"
SENSOR_PATH = BASE_DIR / "state" / "latest_sensors.json"

app = FastAPI(title="CRPS Pi Dashboard")
ENABLE_PHONE_SENSORS = False     # Set to False to disable phone sensor API and use external hardware sensors instead

if ENABLE_PHONE_SENSORS:
    app.include_router(phone_sensor_router)

app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")


@app.api_route("/", methods=["GET", "HEAD"])
def dashboard():
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.api_route("/api/latest", methods=["GET", "HEAD"])
def latest_prediction():
    if STATE_PATH.exists():
        with open(STATE_PATH, "r") as f:
            return json.load(f)

    return JSONResponse(
        status_code=404,
        content={
            "status": "no_prediction_available",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.api_route("/api/sensors", methods=["GET", "HEAD"])
def latest_sensors():
    if not SENSOR_PATH.exists():
        return {
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


@app.get("/debug/path")
def debug_path():
    return {
        "base_dir": str(BASE_DIR),
        "dashboard_dir": str(DASHBOARD_DIR),
        "state_path": str(STATE_PATH),
        "state_exists": STATE_PATH.exists(),
        "sensor_path": str(SENSOR_PATH),
        "sensor_exists": SENSOR_PATH.exists(),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)