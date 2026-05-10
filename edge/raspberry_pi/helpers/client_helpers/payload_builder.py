from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edge.raspberry_pi.helpers.live_sources import fetch_targeted_tomtom_traffic, fetch_metar_weather
from edge.raspberry_pi.hardware.sensor_sources import load_sensor_data
from src.features.feature_reconstructor import reconstruct_features

def build_live_payload(config):
    now = datetime.now()

    sensor_data = load_sensor_data()
    gps = sensor_data.get("gps", {})
    is_simulation = "scenario" in sensor_data       # If "scenario" key exists, we are in simulation mode and should use config GPS instead of sensor GPS

    lat = gps.get("latitude") or config.get("latitude")
    lon = gps.get("longitude") or config.get("longitude")

    try:
        traffic = fetch_targeted_tomtom_traffic(
            lat=lat,
            lon=lon,
            config=config
        )
    except Exception as e:
        print(f"Traffic unavailable: {e}")
        traffic = {
            "speed_mph": config.get("fallback_speed_mph", 45),
            "free_flow_speed_mph": config.get("fallback_speed_mph", 65),
            "speed_ratio": 1.0
        }

    vehicle_speed = gps.get("speed_mph")
    if vehicle_speed is None:
        vehicle_speed = traffic["speed_mph"]

    heading_deg = gps.get("heading_deg")
    if heading_deg is None:
        heading_deg = config.get("default_heading_deg", 0.0)

    try:
        weather = fetch_metar_weather(config)
    except Exception as e:
        print(f"Weather unavailable: {e}")
        weather = {
            "temperature_f": 60,
            "precipitation_in": 0,
            "visibility_miles": 10,
            "wind_speed_mph": 0,
            "is_rain": 0,
            "is_low_visibility": 0,
        }

    raw = {
        "segment_id": config["segment_id"],
        "station_id": config["station_id"],
        "timestamp": now.isoformat(),
        "latitude": lat,
        "longitude": lon,
        "vehicle_speed_mph": vehicle_speed,
        "heading_deg": heading_deg,
        "speed_mph": traffic["speed_mph"],
        "free_flow_speed_mph": traffic["free_flow_speed_mph"],
        "speed_ratio": traffic.get("speed_ratio"),
        "temperature_f": weather["temperature_f"],
        "visibility_miles": weather["visibility_miles"],
        "wind_speed_mph": weather["wind_speed_mph"],
        "precipitation_in": weather["precipitation_in"],
        "is_rain": weather["is_rain"],
    }

    payload = reconstruct_features(raw)

    payload["is_simulation"] = is_simulation
    payload["vehicle_speed_mph"] = vehicle_speed
    payload["heading_deg"] = heading_deg
    payload["timestamp"] = raw["timestamp"]
    speed_mph = payload["speed_mph"]

    payload.setdefault("speed_delta_5min", 0)
    payload.setdefault("speed_delta_15min", 0)
    payload.setdefault("speed_rolling_mean_15min", speed_mph)
    payload.setdefault("speed_rolling_std_15min", 0)
    payload.setdefault("flow_rolling_mean_15min", payload.get("flow_veh_per_interval"))
    payload.setdefault("occupancy_rolling_mean_15min", payload.get("occupancy_pct"))
    payload.setdefault("crash_count_current_window", 0)
    payload.setdefault("crash_count_past_1hr", 0)
    payload.setdefault("crash_count_past_24hr", 0)
    payload.setdefault("crash_count_past_7d", 0)
    payload.setdefault("is_low_visibility", raw.get("is_low_visibility", 0))
    payload.setdefault("precipitation_in", raw.get("precipitation_in", 0))

    return payload