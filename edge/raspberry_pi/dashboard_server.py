from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn


BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
STATE_PATH = BASE_DIR / "state" / "latest_prediction.json"


app = FastAPI(title="CRPS Pi Dashboard")

app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")


@app.get("/")
def dashboard():
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/api/latest")
def latest_prediction():
    if not STATE_PATH.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "No prediction available yet"},
        )

    return FileResponse(STATE_PATH)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)