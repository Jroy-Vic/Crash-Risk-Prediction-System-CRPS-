import requests
import numpy as np
import onnxruntime as ort
import json
from datetime import datetime, timezone

_onnx_session = None
_features = None

def load_local_model(config):
    global _onnx_session, _features
    if _onnx_session is None:
        _onnx_session = ort.InferenceSession(config["local_model_path"])
        with open(config["local_features_path"], "r") as f:
            _features = json.load(f)
    return _onnx_session, _features

def request_backend_prediction(config, payload):
    res = requests.post(config["backend_url"], json=payload, timeout=3)
    res.raise_for_status()
    result = res.json()

    result["inference_mode"] = "online_backend"
    result["backend_reachable"] = True
    result["accuracy_state"] = "normal"
    return result

def local_model_prediction(config, payload):
    session, features = load_local_model(config)

    row = [payload[f] for f in features]
    X = np.array([row], dtype=np.float32)

    outputs = session.run(None, {session.get_inputs()[0].name: X})
    prob = float(outputs[1][0][1])

    return {
        "future_congestion_probability": prob,
        "recommended_speed_mph": int(payload["free_flow_speed_mph"]),
        "inference_mode": "onnx_local",
        "backend_reachable": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

def rule_based_fallback(payload):
    return {
        "future_congestion_probability": 0.5,
        "recommended_speed_mph": payload.get("speed_mph", 45),
        "inference_mode": "rule_based",
        "backend_reachable": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Priority 1: Try backend prediction
# Priority 2: Try local model prediction
# If both fail, return a simple rule-based prediction
def get_prediction(config, payload):
    try:
        return request_backend_prediction(config, payload)
    except Exception as e:
        print(f"Backend unavailable: {e}")

    try:
        return local_model_prediction(config, payload)
    except Exception as e:
        print(f"Local model unavailable: {e}")

    return rule_based_fallback(payload)