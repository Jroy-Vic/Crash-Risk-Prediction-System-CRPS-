from pathlib import Path
import sys
import requests

import polars as pl
from fastapi import FastAPI

# Allow backend to import from src/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from src.inference.predictor import TrafficRiskPredictor
from services.backend.schemas import PredictionRequest, PredictionResponse


app = FastAPI(
    title="Crash Risk Prediction System Backend",
    version="0.1.0",
)

predictor = TrafficRiskPredictor()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "crps-backend",
        "model": predictor.model_adapter.model_name,
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    feature_row = pl.DataFrame([request.model_dump()])

    result = predictor.predict_one(feature_row)

    recommended_speed_mph = result.recommended_speed_mph

    if request.speed_limit_mph is not None:
        recommended_speed_mph = min(
            recommended_speed_mph,
            int(request.speed_limit_mph)
        )

    return PredictionResponse(
        segment_id=result.segment_id,
        station_id=result.station_id,
        current_speed_mph=result.current_speed_mph,
        speed_ratio=result.speed_ratio,
        current_congestion=result.current_congestion,
        future_congestion_probability=result.future_congestion_probability,
        recommended_speed_mph=recommended_speed_mph,
        model_name=result.model_name,
    )