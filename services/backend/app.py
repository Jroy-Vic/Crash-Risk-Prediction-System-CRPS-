from pathlib import Path
import sys
from datetime import datetime, timezone
import traceback
import polars as pl
from fastapi import FastAPI
import uvicorn

from route_ahead_predictor import get_route_ahead_target_dict
from tomtom_client import fetch_tomtom_flow

# Allow backend to import from src/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from src.inference.predictor import TrafficRiskPredictor
from schemas import PredictionRequest, PredictionResponse


app = FastAPI(
    title="Crash Risk Prediction System Backend",
    version="0.2.0",
)

predictor = TrafficRiskPredictor()
latest_prediction = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "crps-backend",
        "model": predictor.model_adapter.model_name,
        "prediction_mode": "route_ahead_5min",
    }


@app.post("/predict")
def predict(request: PredictionRequest):
    try:
        return predict_impl(request)
    except Exception as e:
        return {
            "error": "predict_endpoint_failed",
            "detail": str(e),
            "traceback": traceback.format_exc(),
        }

def predict_impl(request: PredictionRequest):
    """
    Route-ahead prediction endpoint.

    Flow:
    1. Receive current vehicle location/speed/heading.
    2. Compute target point approximately 5 minutes ahead.
    3. Run existing model using the same feature schema for now.
    4. Return prediction plus route-ahead metadata.

    Important:
    This version computes the 5-minute-ahead target but does not yet
    refetch TomTom traffic at the target coordinate unless your caller
    has already done that before calling /predict.
    """

    horizon_seconds = getattr(request, "horizon_seconds", 300)

    vehicle_speed_mph = getattr(
        request,
        "vehicle_speed_mph",
        request.speed_mph,
    )

    heading_deg = getattr(request, "heading_deg", 0.0)

    route_ahead = get_route_ahead_target_dict(
        latitude=request.latitude,
        longitude=request.longitude,
        vehicle_speed_mph=vehicle_speed_mph,
        heading_deg=heading_deg,
        horizon_seconds=horizon_seconds,
    )

    eta_timestamp = datetime.fromisoformat(
        route_ahead["eta_timestamp_utc"]
    )

    eta_hour = eta_timestamp.hour
    eta_day_of_week = eta_timestamp.weekday()
    eta_month = eta_timestamp.month
    eta_is_weekend = eta_day_of_week >= 5

    eta_rush_hour = (
        eta_day_of_week < 5 and
        (
            7 <= eta_hour <= 9 or
            16 <= eta_hour <= 18
        )
    )

    request_data = request.model_dump()

    try:
        target_traffic = fetch_tomtom_flow(
            route_ahead["latitude"],
            route_ahead["longitude"],
        )

        request_data["speed_mph"] = target_traffic["speed_mph"]
        request_data["free_flow_speed_mph"] = target_traffic["free_flow_speed_mph"]
        request_data["speed_ratio"] = target_traffic["speed_ratio"]

    except Exception:
        target_traffic = {
            "speed_mph": request.speed_mph,
            "free_flow_speed_mph": getattr(request, "free_flow_speed_mph", None),
            "speed_ratio": request.speed_ratio,
            "tomtom_raw": None,
        }

    request_data["hour"] = eta_hour
    request_data["day_of_week"] = eta_day_of_week
    request_data["month"] = eta_month
    request_data["is_weekend"] = int(eta_is_weekend)
    request_data["rush_hour"] = int(eta_rush_hour)
    request_data["is_rush_hour"] = int(eta_rush_hour)

    # Preserve current vehicle location.
    request_data["current_latitude"] = request.latitude
    request_data["current_longitude"] = request.longitude

    # Use route-ahead target as the prediction location.
    request_data["latitude"] = route_ahead["latitude"]
    request_data["longitude"] = route_ahead["longitude"]

    # Keep useful route-ahead metadata out of the model if it was not trained on it.
    model_input = {
        key: value
        for key, value in request_data.items()
        if key not in {
            "vehicle_speed_mph",
            "heading_deg",
            "horizon_seconds",
            "current_latitude",
            "current_longitude",
        }
    }

    feature_row = pl.DataFrame([model_input])

    try:
        result = predictor.predict_one(feature_row)
        
        probability = getattr(request, "demo_probability", None)

        if probability is None:
            probability = result.future_congestion_probability

    except Exception as e:
        return {
            "error": "predictor_failed",
            "detail": str(e),
            "model_input_columns": list(model_input.keys()),
            "model_input": model_input,
        }

    recommended_speed_mph = result.recommended_speed_mph

    if request.speed_limit_mph is not None:
        recommended_speed_mph = min(
            recommended_speed_mph,
            int(request.speed_limit_mph),
        )

    global latest_prediction
    is_simulation = request.segment_id == "simulation_cycle"

    response = {
        "segment_id": result.segment_id,
        "station_id": result.station_id,

        "current_latitude": request.latitude,
        "current_longitude": request.longitude,
        "target_latitude": route_ahead["latitude"],
        "target_longitude": route_ahead["longitude"],

        "current_speed_mph": getattr(result, "current_speed_mph", None),
        "vehicle_speed_mph": vehicle_speed_mph,
        "speed_ratio": result.speed_ratio,
        "current_congestion": result.current_congestion,

        "target_traffic": target_traffic,

       "future_congestion_probability": probability,
        "congestion_probability_5min_ahead": probability,

        "recommended_speed_mph": recommended_speed_mph,
        "model_name": result.model_name,

        "mode": route_ahead["mode"],
        "route_mode": route_ahead["mode"],
        "inference_mode": "simulation" if is_simulation else "online_backend",
        "route_ahead": route_ahead,
        "eta_features": {
            "eta_hour": eta_hour,
            "eta_day_of_week": eta_day_of_week,
            "eta_month": eta_month,
            "eta_is_weekend": eta_is_weekend,
            "eta_rush_hour": eta_rush_hour,
        },

        "temperature_f": request.temperature_f,
        "visibility_miles": request.visibility_miles,
        "wind_speed_mph": request.wind_speed_mph,
        "precipitation_in": request.precipitation_in,
        "precipitation": request.precipitation_in,
        "is_rain": request.is_rain,
        "weather": {
            "temperature_f": request.temperature_f,
            "visibility_miles": request.visibility_miles,
            "wind_speed_mph": request.wind_speed_mph,
            "precipitation_in": request.precipitation_in,
            "precipitation": request.precipitation_in,
            "is_rain": request.is_rain,
        },

        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    latest_prediction = response

    return response


@app.get("/api/latest")
def get_latest_prediction():
    if latest_prediction is None:
        return {
            "status": "no_prediction_yet",
            "future_congestion_probability": None,
            "congestion_probability_5min_ahead": None,
            "recommended_speed_mph": None,
            "mode": "waiting",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return latest_prediction


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)