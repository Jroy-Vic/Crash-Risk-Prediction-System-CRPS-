from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import requests

from datetime import datetime, timezone


BACKEND_URL = "http://Roys_MacBook:8000"
BACKEND_TIMEOUT_SEC = 2.0

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
STATE_PATH = BASE_DIR / "state" / "latest_prediction.json"

app = FastAPI(title="CRPS Pi Dashboard")

app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")


@app.get("/api/latest")
def latest_prediction():
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/latest",
            timeout=BACKEND_TIMEOUT_SEC,
        )
        response.raise_for_status()

        data = response.json()

        if data.get("status") == "no_prediction_yet":
            raise RuntimeError("Backend has no prediction yet")

        data["backend_reachable"] = True
        data["inference_mode"] = data.get("inference_mode", "online_backend")
        data["accuracy_state"] = "normal"

        return data

    except Exception as e:
        return run_rule_based_fallback(str(e))

@app.api_route("/", methods=["GET", "HEAD"])
def dashboard():
    return FileResponse(DASHBOARD_DIR / "index.html")

@app.api_route("/api/latest", methods=["GET", "HEAD"])
def latest_prediction():
    if not STATE_PATH.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "No prediction available yet"},
        )

    return FileResponse(STATE_PATH)

@app.get("/api/sensors")
def latest_sensors():
    sensor_path = BASE_DIR / "state" / "latest_sensors.json"

    if not sensor_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "No sensor data available yet"},
        )

    return FileResponse(sensor_path)


def run_rule_based_fallback(reason: str):
    now = datetime.now(timezone.utc).isoformat()

    # Conservative fallback when backend is unavailable.
    probability = 0.55
    speed_limit_mph = 65
    recommended_speed_mph = 45
    traffic_speed_mph = 45

    return {
        "status": "fallback_active",
        "fallback_reason": reason,

        "segment_id": "local_fallback",
        "station_id": "PI_LOCAL",

        "backend_reachable": False,
        "accuracy_state": "reduced",
        "inference_mode": "rule_based",

        "mode": "fallback",
        "route_mode": "unavailable",

        "future_congestion_probability": probability,
        "congestion_probability_5min_ahead": probability,

        "recommended_speed_mph": recommended_speed_mph,
        "speed_limit_mph": speed_limit_mph,

        "current_speed_mph": traffic_speed_mph,
        "vehicle_speed_mph": traffic_speed_mph,
        "speed_ratio": traffic_speed_mph / speed_limit_mph,
        "current_congestion": probability >= 0.4,

        "target_traffic": {
            "speed_mph": traffic_speed_mph,
            "free_flow_speed_mph": speed_limit_mph,
            "speed_ratio": traffic_speed_mph / speed_limit_mph,
            "tomtom_raw": None,
        },

        "route_ahead": {
            "latitude": None,
            "longitude": None,
            "horizon_seconds": 300,
            "distance_ahead_m": None,
            "eta_timestamp_utc": now,
            "mode": "unavailable",
            "confidence": 0.35,
        },

        "temperature_f": None,
        "visibility_miles": None,
        "wind_speed_mph": None,
        "precipitation_in": None,
        "precipitation": None,
        "is_rain": 0,
        "weather": {
            "temperature_f": None,
            "visibility_miles": None,
            "wind_speed_mph": None,
            "precipitation_in": None,
            "precipitation": None,
            "is_rain": 0,
        },

        "timestamp": now,
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)