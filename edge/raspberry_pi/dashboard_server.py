from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import requests


BACKEND_URL = "http://Roys_MacBook:8000"

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
STATE_PATH = BASE_DIR / "state" / "latest_prediction.json"

app = FastAPI(title="CRPS Pi Dashboard")

app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")


@app.get("/api/latest")
def latest_proxy():
    r = requests.get(f"{BACKEND_URL}/api/latest", timeout=3)
    return r.json()

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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)