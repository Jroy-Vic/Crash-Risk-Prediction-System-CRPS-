import sys
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

import json
import time
import requests

from datetime import datetime, timezone
from edge.raspberry_pi.helpers.live_sources import fetch_targeted_tomtom_traffic, fetch_metar_weather

from src.utils.crps_logger import CRPSLogger, get_risk_level
logger = CRPSLogger()

from src.features.feature_reconstructor import reconstruct_features
from src.hardware.sensor_reader import load_latest_sensors
from edge.raspberry_pi.sensors.sensor_sources import load_hardware_sensor_data, load_sensor_data
from src.hardware.refresh_controller import choose_poll_interval

CONFIG_PATH = Path("edge/raspberry_pi/config.json")
ROAD_METADATA_CACHE_PATH = Path("edge/raspberry_pi/helpers/cache/road_metadata_cache.json")
STATE_PATH = Path("edge/raspberry_pi/state/latest_prediction.json")

DEMO_BACKEND_FAILURE = True
DEMO_FAILURE_AFTER_LOOPS = 5
DEMO_FAILURE_DURATION_LOOPS = 5

def load_config():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    config["tomtom_api_key"] = os.getenv("TOMTOM_API_KEY") or config.get("tomtom_api_key")

    return config

def load_road_metadata_cache():
    if not ROAD_METADATA_CACHE_PATH.exists():
        return {}

    with open(ROAD_METADATA_CACHE_PATH, "r") as f:
        return json.load(f)
    
def build_sample_payload():
    speed_mph = 45.0
    free_flow_speed_mph = 65.0

    return {
        "station_id": "demo_station_001",
        "segment_id": "demo_segment_001",
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "latitude": 34.0522,
        "longitude": -118.2437,

        "speed_mph": speed_mph + (datetime.now().second % 10),
        "free_flow_speed_mph": free_flow_speed_mph,
        "speed_ratio": speed_mph / free_flow_speed_mph,

        "flow_veh_per_interval": 1200,
        "occupancy_pct": 18.0,

        "hour": 12,
        "day_of_week": 3,
        "month": 5,
        "is_weekend": 0,
        "is_rush_hour": 0,

        "speed_delta_5min": -4.2,
        "speed_delta_15min": -6.8,
        "speed_rolling_mean_15min": 48.5,
        "speed_rolling_std_15min": 3.1,

        "flow_rolling_mean_15min": 1180,
        "occupancy_rolling_mean_15min": 16.0,

        "temperature_f": 68.0,
        "precipitation_in": 0.0,
        "visibility_miles": 8.0,
        "wind_speed_mph": 6.5,
        "is_rain": 0,
        "is_low_visibility": 0,

        "crash_count_current_window": 0,
        "crash_count_past_1hr": 0,
        "crash_count_past_24hr": 0,
        "crash_count_past_7d": 0,
    }

def build_live_payload(config):
    road_cache = load_road_metadata_cache()
    now = datetime.now()
    sensor_data = load_sensor_data()
    gps = sensor_data.get("gps", {})

    vehicle_speed = gps.get("speed_mph")

    traffic = fetch_targeted_tomtom_traffic(
        lat=gps.get("latitude"),
        lon=gps.get("longitude"),
        config=config
    )

    vehicle_speed = gps.get("speed_mph")
    if vehicle_speed is None:
        vehicle_speed = traffic["speed_mph"]

    heading_deg = gps.get("heading_deg")
    if heading_deg is None:
        heading_deg = config.get("default_heading_deg", 0.0)

    try:
        weather = fetch_metar_weather(config)
    except Exception as e:
        print(f"Weather unavailable. Using default weather. Reason: {e}")
        weather = {
            "temperature_f": config.get("default_temperature_f", 60),
            "precipitation_in": 0,
            "visibility_miles": 10,
            "wind_speed_mph": 0,
            "is_rain": 0,
            "is_low_visibility": 0,
        }

    speed_limit = road_cache.get(
        "speed_limit_mph",
        config.get("speed_limit_mph", 65)
    )

    raw_live_data = {
        "station_id": config.get("station_id", "ksbp_live"),
        "segment_id": config.get("segment_id", "slo_live_segment"),
        "timestamp": now.isoformat(),

        "latitude": gps.get("latitude", road_cache.get("target_latitude", config["latitude"])),
        "longitude": gps.get("longitude", road_cache.get("target_longitude", config["longitude"])),
        "vehicle_speed_mph": vehicle_speed,
        "heading_deg": heading_deg,

        "speed_mph": traffic["speed_mph"],
        "free_flow_speed_mph": traffic["free_flow_speed_mph"],
        "speed_ratio": traffic.get("speed_ratio"),

        "temperature_f": weather.get("temperature_f", 60),
        "precipitation": weather.get(
            "precipitation",
            weather.get("precipitation_in", 0)
        ),
        "precipitation_in": weather.get(
            "precipitation_in",
            weather.get("precipitation", 0)
        ),
        "visibility_miles": weather.get("visibility_miles", 10),
        "wind_speed_mph": weather.get("wind_speed_mph", 0),
        "is_rain": weather.get("is_rain", 0),
        "is_low_visibility": weather.get("is_low_visibility", 0),

        "speed_limit_mph": speed_limit,
    }

    payload = reconstruct_features(raw_live_data)

    # Preserve timestamp from live read
    payload["timestamp"] = raw_live_data["timestamp"]

    # Extra model features not produced by basic reconstruction yet
    speed_mph = payload["speed_mph"]

    payload.setdefault("speed_delta_5min", 0)
    payload.setdefault("speed_delta_15min", 0)
    payload.setdefault("speed_rolling_mean_15min", speed_mph)
    payload.setdefault("speed_rolling_std_15min", 0)

    payload.setdefault(
        "flow_rolling_mean_15min",
        payload.get("flow_veh_per_interval")
    )
    payload.setdefault(
        "occupancy_rolling_mean_15min",
        payload.get("occupancy_pct")
    )

    payload.setdefault("crash_count_current_window", 0)
    payload.setdefault("crash_count_past_1hr", 0)
    payload.setdefault("crash_count_past_24hr", 0)
    payload.setdefault("crash_count_past_7d", 0)

    payload.setdefault("is_low_visibility", raw_live_data["is_low_visibility"])

    # Backend may expect precipitation_in
    payload.setdefault("precipitation_in", raw_live_data["precipitation_in"])

    return payload

def request_backend_prediction(config, payload):
    response = requests.post(
        config["backend_url"],
        json=payload,
        timeout=config.get("request_timeout_sec", 3),
    )

    if response.status_code == 422:
        print("FastAPI validation error:")
        print(response.text)

    response.raise_for_status()
    result = response.json()

    result["mode"] = result.get("mode", "online_backend")
    result["inference_mode"] = "online_backend"
    result["backend_reachable"] = True
    result["accuracy_state"] = "normal"

    return result


import onnxruntime as ort
import numpy as np
_onnx_session = None
_onnx_features = None

def load_local_model(config):
    global _onnx_session, _onnx_features

    if _onnx_session is None:
        _onnx_session = ort.InferenceSession(config["local_model_path"])
        with open(config["local_features_path"], "r") as f:
            _onnx_features = json.load(f)

    return _onnx_session, _onnx_features


def recommend_speed(payload, future_congestion_probability):
    speed_mph = payload.get("speed_mph", 45.0)
    free_flow = payload.get("free_flow_speed_mph", 65.0)
    speed_limit = payload.get("speed_limit_mph")

    speed_ratio = speed_mph / free_flow if free_flow > 0 else 1.0

    if speed_ratio < 0.6:
        advisory = 25
    elif future_congestion_probability >= 0.85:
        advisory = max(25, int(free_flow * 0.75))
    elif future_congestion_probability >= 0.70:
        advisory = max(25, int(free_flow * 0.85))
    elif future_congestion_probability >= 0.55:
        advisory = max(25, int(free_flow * 0.95))
    else:
        advisory = int(free_flow)

    if speed_limit is not None:
        advisory = min(advisory, int(speed_limit))

    return advisory


def local_model_prediction(config, payload):
    session, feature_names = load_local_model(config)

    missing = [f for f in feature_names if f not in payload]
    if missing:
        raise ValueError(f"Missing features: {missing}")

    # build feature vector in correct order
    row = [payload[f] for f in feature_names]

    X = np.array([row], dtype=np.float32)

    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: X})

    probs = outputs[1] if len(outputs) > 1 else outputs[0]
    probability = float(probs[0][1])

    recommended_speed = recommend_speed(payload, probability)
    ml_confidence = abs(probability - 0.5) * 2

    return {
        "segment_id": payload.get("segment_id"),
        "station_id": payload.get("station_id"),

        "current_latitude": payload.get("latitude"),
        "current_longitude": payload.get("longitude"),
        "target_latitude": payload.get("latitude"),
        "target_longitude": payload.get("longitude"),

        "current_speed_mph": payload.get("speed_mph"),
        "vehicle_speed_mph": payload.get("vehicle_speed_mph", payload.get("speed_mph")),
        "speed_mph": payload.get("speed_mph"),
        "free_flow_speed_mph": payload.get("free_flow_speed_mph"),
        "speed_ratio": payload.get("speed_ratio"),

        "target_traffic": {
            "speed_mph": payload.get("speed_mph"),
            "free_flow_speed_mph": payload.get("free_flow_speed_mph"),
            "speed_ratio": payload.get("speed_ratio"),
            "tomtom_raw": None,
        },

        "future_congestion_probability": probability,
        "congestion_probability_5min_ahead": probability,
        "ml_confidence": ml_confidence,

        "recommended_speed_mph": recommended_speed,

        "mode": "offline_model",
        "route_mode": "local_cached_position",
        "inference_mode": "onnx_local",
        "backend_reachable": False,
        "accuracy_state": "reduced",

        "route_ahead": {
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "distance_ahead_m": 0,
            "eta_timestamp_utc": payload.get("timestamp"),
            "mode": "local_cached_position",
            "confidence": 0.35,
        },

        "temperature_f": payload.get("temperature_f"),
        "visibility_miles": payload.get("visibility_miles"),
        "wind_speed_mph": payload.get("wind_speed_mph"),
        "precipitation_in": payload.get("precipitation_in", payload.get("precipitation", 0)),
        "precipitation": payload.get("precipitation", payload.get("precipitation_in", 0)),
        "is_rain": payload.get("is_rain"),

        "weather": {
            "temperature_f": payload.get("temperature_f"),
            "visibility_miles": payload.get("visibility_miles"),
            "wind_speed_mph": payload.get("wind_speed_mph"),
            "precipitation_in": payload.get("precipitation_in", payload.get("precipitation", 0)),
            "precipitation": payload.get("precipitation", payload.get("precipitation_in", 0)),
            "is_rain": payload.get("is_rain"),
        },

        "timestamp": payload.get("timestamp"),
        "prediction_generated_at": datetime.now(timezone.utc).isoformat(),
    }


def rule_based_fallback(config, payload):
    speed_mph = payload.get("speed_mph", config.get("fallback_speed_mph", 45))
    free_flow = payload.get("free_flow_speed_mph", 65.0)
    occupancy_pct = payload.get("occupancy_pct", 0.0)

    speed_ratio = speed_mph / free_flow if free_flow > 0 else 1.0

    if speed_ratio < 0.6 or occupancy_pct > 25:
        probability = 0.85
        recommended_speed = 25
    elif speed_ratio < 0.8 or occupancy_pct > 18:
        probability = 0.65
        recommended_speed = max(25, int(speed_mph - 10))
    else:
        probability = 0.20
        recommended_speed = int(speed_mph)

    if payload.get("speed_limit_mph") is not None:
        recommended_speed = min(recommended_speed, int(payload["speed_limit_mph"]))

    ml_confidence = abs(probability - 0.5) * 2

    return {
        "segment_id": payload.get("segment_id"),
        "station_id": payload.get("station_id"),

        "current_latitude": payload.get("latitude"),
        "current_longitude": payload.get("longitude"),
        "target_latitude": payload.get("latitude"),
        "target_longitude": payload.get("longitude"),

        "current_speed_mph": speed_mph,
        "vehicle_speed_mph": payload.get("vehicle_speed_mph", speed_mph),
        "speed_mph": speed_mph,
        "free_flow_speed_mph": free_flow,
        "speed_ratio": speed_ratio,
        "speed_limit_mph": payload.get("speed_limit_mph"),

        "target_traffic": {
            "speed_mph": speed_mph,
            "free_flow_speed_mph": free_flow,
            "speed_ratio": speed_ratio,
            "tomtom_raw": None,
        },

        "future_congestion_probability": probability,
        "congestion_probability_5min_ahead": probability,
        "ml_confidence": ml_confidence,

        "recommended_speed_mph": recommended_speed,

        "mode": "offline_rules",
        "route_mode": "local_cached_position",
        "inference_mode": "rule_based",
        "backend_reachable": False,
        "accuracy_state": "reduced",

        "route_ahead": {
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "distance_ahead_m": 0,
            "eta_timestamp_utc": payload.get("timestamp"),
            "mode": "local_cached_position",
            "confidence": 0.35,
        },

        "temperature_f": payload.get("temperature_f"),
        "visibility_miles": payload.get("visibility_miles"),
        "wind_speed_mph": payload.get("wind_speed_mph"),
        "precipitation_in": payload.get("precipitation_in", payload.get("precipitation", 0)),
        "precipitation": payload.get("precipitation", payload.get("precipitation_in", 0)),
        "is_rain": payload.get("is_rain"),

        "weather": {
            "temperature_f": payload.get("temperature_f"),
            "visibility_miles": payload.get("visibility_miles"),
            "wind_speed_mph": payload.get("wind_speed_mph"),
            "precipitation_in": payload.get("precipitation_in", payload.get("precipitation", 0)),
            "precipitation": payload.get("precipitation", payload.get("precipitation_in", 0)),
            "is_rain": payload.get("is_rain"),
        },

        "timestamp": payload.get("timestamp"),
        "prediction_generated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_prediction(config, payload):
    try:
        return request_backend_prediction(config, payload)

    except requests.RequestException as e:
        print("Backend unavailable. Trying local model.")
        print(f"Backend reason: {e}")

    try:
        return local_model_prediction(config, payload)

    except Exception as e:
        print("Local model unavailable. Using rule-based fallback.")
        print(f"Local model reason: {e}")
        return rule_based_fallback(config, payload)


def print_result(result):
    print(f"Mode: {result['mode']}")

    probability = result.get("future_congestion_probability")
    if probability is not None:
        print(f"Future congestion probability: {probability:.3f}")
    else:
        print("Future congestion probability: unavailable")

    print(f"Recommended speed: {result['recommended_speed_mph']} mph")
    print("-" * 40)


def write_latest_prediction(payload, result):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    output = dict(result)

    output.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    output.setdefault("segment_id", payload.get("segment_id"))
    output.setdefault("station_id", payload.get("station_id"))
    output.setdefault("speed_mph", payload.get("speed_mph"))
    output.setdefault("free_flow_speed_mph", payload.get("free_flow_speed_mph"))
    output.setdefault("speed_ratio", payload.get("speed_ratio"))
    output.setdefault("speed_limit_mph", payload.get("speed_limit_mph"))

    with open(STATE_PATH, "w") as f:
        json.dump(output, f, indent=2)


def main():
    config = load_config()
    last_good_payload = None

    # loop_count = 0
    # real_backend_url = config["backend_url"]

    while True:
        try:
            payload = build_live_payload(config)
            print("LIVE PAYLOAD:")
            print(json.dumps(payload, indent=2))
            last_good_payload = payload
        except Exception as e:
            print("Live data unavailable.")
            print(f"Live data reason: {e}")

            if last_good_payload is not None:
                payload = dict(last_good_payload)
                print("Using last good live payload.")
            else:
                payload = build_sample_payload()
                print("Using sample payload.")

        # loop_count += 1
        # demo_step = loop_count % 2

        # if DEMO_BACKEND_FAILURE:
        #     if demo_step == 1:
        #         config["backend_url"] = real_backend_url
        #         print("DEMO MODE: Backend active.")

        #     elif demo_step == 0:
        #         config["backend_url"] = "http://127.0.0.1:9999/predict"
        #         print("DEMO MODE: Backend disconnected. Using ONNX local fallback.")

        result = get_prediction(config, payload)
        write_latest_prediction(payload, result)

        probability = result.get("future_congestion_probability")
        recommended_speed = result.get("recommended_speed_mph")

        risk_level = get_risk_level(probability) if probability is not None else "UNKNOWN"

        log_row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "segment_id": payload.get("segment_id"),
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),

            "speed_mph": payload.get("speed_mph"),
            "free_flow_speed_mph": payload.get("free_flow_speed_mph"),
            "speed_ratio": payload.get("speed_ratio"),

            # Use reconstructed values
            "flow": payload.get("flow", payload.get("flow_veh_per_interval")),
            "occupancy": payload.get("occupancy", payload.get("occupancy_pct")),

            "temperature_f": payload.get("temperature_f"),
            "visibility_miles": payload.get("visibility_miles"),
            "wind_speed_mph": payload.get("wind_speed_mph"),
            "precipitation": payload.get("precipitation", payload.get("precipitation_in", 0)),
            "is_rain": payload.get("is_rain", 0),

            "hour": payload.get("hour"),
            "day_of_week": payload.get("day_of_week"),
            "rush_hour": payload.get("rush_hour", payload.get("is_rush_hour")),

            "speed_delta_5min": payload.get("speed_delta_5min"),
            "speed_delta_15min": payload.get("speed_delta_15min"),
            "speed_rolling_mean_15min": payload.get("speed_rolling_mean_15min"),
            "speed_rolling_std_15min": payload.get("speed_rolling_std_15min"),
            "flow_rolling_mean_15min": payload.get("flow_rolling_mean_15min"),
            "occupancy_rolling_mean_15min": payload.get("occupancy_rolling_mean_15min"),
            "is_low_visibility": payload.get("is_low_visibility"),
            "precipitation_in": payload.get("precipitation_in"),
            "crash_count_current_window": payload.get("crash_count_current_window"),
            "crash_count_past_1hr": payload.get("crash_count_past_1hr"),
            "crash_count_past_24hr": payload.get("crash_count_past_24hr"),
            "crash_count_past_7d": payload.get("crash_count_past_7d"),

            "probability": probability,
            "recommended_speed_mph": recommended_speed,
            "speed_limit_mph": payload.get("speed_limit_mph"),

            "risk_level": risk_level,
            "mode": result.get("mode", "backend"),
            "source": result.get("source", "tomtom_metar_reconstructed"),
            "backend_status": result.get("backend_status", "ok"),
            "error": "",
        }

        logger.log_prediction(log_row)

        print("BACKEND / PREDICTION RESPONSE:")
        print(json.dumps(result, indent=2))

        print_result(result)

        sensor_data = load_sensor_data()

        poll_interval = choose_poll_interval(
            sensor_data,
            default_interval=config.get("poll_interval_sec", 5)
        )

        time.sleep(poll_interval)


if __name__ == "__main__":
    main()