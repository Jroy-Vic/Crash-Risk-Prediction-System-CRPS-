import os
import requests


TOMTOM_API_KEY = os.getenv("r0dOGDbwKMxLS5mer68NVh7yHlhWGc4t")


def fetch_tomtom_flow(latitude: float, longitude: float) -> dict:
    if not TOMTOM_API_KEY:
        raise RuntimeError("TOMTOM_API_KEY environment variable is not set")

    url = (
        "https://api.tomtom.com/traffic/services/4/flowSegmentData/"
        f"absolute/10/json?point={latitude},{longitude}&key={TOMTOM_API_KEY}"
    )

    response = requests.get(url, timeout=5)
    response.raise_for_status()

    data = response.json()
    flow = data.get("flowSegmentData", {})

    current_speed_kph = flow.get("currentSpeed")
    free_flow_speed_kph = flow.get("freeFlowSpeed")

    current_speed_mph = (
        current_speed_kph * 0.621371 if current_speed_kph is not None else None
    )

    free_flow_speed_mph = (
        free_flow_speed_kph * 0.621371 if free_flow_speed_kph is not None else None
    )

    speed_ratio = None
    if current_speed_mph is not None and free_flow_speed_mph:
        speed_ratio = current_speed_mph / free_flow_speed_mph

    return {
        "speed_mph": current_speed_mph,
        "free_flow_speed_mph": free_flow_speed_mph,
        "speed_ratio": speed_ratio,
        "tomtom_raw": flow,
    }