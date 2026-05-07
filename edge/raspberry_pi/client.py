import json
import time
from pathlib import Path

import requests

from datetime import datetime
from live_sources import fetch_targeted_tomtom_traffic, fetch_metar_weather


CONFIG_PATH = Path("edge/raspberry_pi/config.json")
ROAD_METADATA_CACHE_PATH = Path("edge/raspberry_pi/helpers/cache/road_metadata_cache.json")
STATE_PATH = Path("edge/raspberry_pi/state/latest_prediction.json")


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

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
        "timestamp": "2026-05-07T12:00:00",

        "latitude": 34.0522,
        "longitude": -118.2437,

        "speed_mph": speed_mph,
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

    traffic = fetch_targeted_tomtom_traffic(config)
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

    speed_mph = traffic["speed_mph"]
    free_flow_speed_mph = traffic["free_flow_speed_mph"]

    speed_limit = road_cache.get(
    "speed_limit_mph",
    config.get("speed_limit_mph")
    )

    return {
        "station_id": config.get("station_id", "ksbp_live"),
        "segment_id": config.get("segment_id", "slo_live_segment"),
        "timestamp": now.isoformat(),

        "latitude": road_cache.get("target_latitude", config["latitude"]),
        "longitude": road_cache.get("target_longitude", config["longitude"]),
        "speed_limit_mph": speed_limit,

        "speed_mph": speed_mph,
        "free_flow_speed_mph": free_flow_speed_mph,
        "speed_ratio": traffic["speed_ratio"],

        "flow_veh_per_interval": config.get("default_flow_veh_per_interval", 300),
        "occupancy_pct": config.get("default_occupancy_pct", 5),

        "speed_delta_5min": 0,
        "speed_delta_15min": 0,
        "speed_rolling_mean_15min": speed_mph,
        "speed_rolling_std_15min": 0,
        "flow_rolling_mean_15min": config.get("default_flow_veh_per_interval", 300),
        "occupancy_rolling_mean_15min": config.get("default_occupancy_pct", 5),

        "temperature_f": weather["temperature_f"],
        "precipitation_in": weather["precipitation_in"],
        "visibility_miles": weather["visibility_miles"],
        "wind_speed_mph": weather["wind_speed_mph"],
        "is_rain": weather["is_rain"],
        "is_low_visibility": weather["is_low_visibility"],

        "crash_count_current_window": 0,
        "crash_count_past_1hr": 0,
        "crash_count_past_24hr": 0,
        "crash_count_past_7d": 0,

        "hour": now.hour,
        "day_of_week": now.weekday(),
        "month": now.month,
        "is_weekend": 1 if now.weekday() >= 5 else 0,
        "is_rush_hour": 1 if now.hour in [7, 8, 9, 16, 17, 18] else 0,
    }

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
    result["mode"] = "online_backend"
    return result


import onnxruntime as ort
import numpy as np

def load_local_model(config):
    session = ort.InferenceSession(config["local_model_path"])

    with open(config["local_features_path"], "r") as f:
        feature_names = json.load(f)

    return session, feature_names


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

    return {
        "mode": "offline_model",
        "future_congestion_probability": probability,
        "recommended_speed_mph": recommended_speed,
    }


def rule_based_fallback(config, payload):
    speed_mph = payload.get("speed_mph", config.get("fallback_speed_mph", 45))
    free_flow = payload.get("free_flow_speed_mph", 65.0)
    occupancy_pct = payload.get("occupancy_pct", 0.0)

    speed_ratio = speed_mph / free_flow if free_flow > 0 else 1.0

    if speed_ratio < 0.6 or occupancy_pct > 25:
        recommended_speed = 25
    elif speed_ratio < 0.8 or occupancy_pct > 18:
        recommended_speed = max(25, int(speed_mph - 10))
    else:
        recommended_speed = int(speed_mph)

    return {
        "mode": "offline_rules",
        "future_congestion_probability": None,
        "recommended_speed_mph": recommended_speed,
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

    output = {
        "timestamp": payload.get("timestamp"),
        "segment_id": payload.get("segment_id"),
        "station_id": payload.get("station_id"),
        "speed_mph": payload.get("speed_mph"),
        "free_flow_speed_mph": payload.get("free_flow_speed_mph"),
        "speed_ratio": payload.get("speed_ratio"),
        "speed_limit_mph": payload.get("speed_limit_mph"),
        "future_congestion_probability": result.get("future_congestion_probability"),
        "recommended_speed_mph": result.get("recommended_speed_mph"),
        "mode": result.get("mode"),
    }

    with open(STATE_PATH, "w") as f:
        json.dump(output, f, indent=2)


def main():
    config = load_config()

    while True:
        try:
            payload = build_live_payload(config)
            print("LIVE PAYLOAD:")
            print(json.dumps(payload, indent=2))
        except Exception as e:
            print("Live data unavailable. Using sample payload.")
            print(f"Live data reason: {e}")
            payload = build_sample_payload()

        result = get_prediction(config, payload)
        write_latest_prediction(payload, result)

        print("BACKEND / PREDICTION RESPONSE:")
        print(json.dumps(result, indent=2))

        print_result(result)
        time.sleep(config.get("poll_interval_sec", 5))


if __name__ == "__main__":
    main()