import requests
import json
from helpers.road_targeting import fetch_osm_road_point


def knots_to_mph(knots):
    return float(knots or 0) * 1.15078


def c_to_f(celsius):
    return (float(celsius) * 9 / 5) + 32


def parse_visibility(value):
    if value is None:
        return 10.0
    if isinstance(value, str) and value.endswith("+"):
        return float(value.replace("+", ""))
    return float(value)


def fetch_tomtom_traffic(config):
    lat = config["latitude"]
    lon = config["longitude"]
    api_key = config["tomtom_api_key"]

    url = (
        "https://api.tomtom.com/traffic/services/4/flowSegmentData/"
        f"absolute/10/json?point={lat},{lon}&unit=mph&key={api_key}"
    )

    response = requests.get(url, timeout=config.get("request_timeout_sec", 3))
    response.raise_for_status()

    data = response.json()["flowSegmentData"]

    speed = float(data["currentSpeed"])
    free_flow = float(data["freeFlowSpeed"])

    return {
        "speed_mph": speed,
        "free_flow_speed_mph": free_flow,
        "speed_ratio": speed / free_flow if free_flow > 0 else 1.0,
    }

def fetch_targeted_tomtom_traffic(lat=None, lon=None, config=None):
    if config is None:
        raise ValueError("config is required")

    targeted_config = dict(config)

    if lat is not None and lon is not None:
        targeted_config["latitude"] = lat
        targeted_config["longitude"] = lon
    elif "target_latitude" in config and "target_longitude" in config:
        targeted_config["latitude"] = config["target_latitude"]
        targeted_config["longitude"] = config["target_longitude"]
    else:
        road = fetch_osm_road_point(config)
        targeted_config["latitude"] = road["latitude"]
        targeted_config["longitude"] = road["longitude"]

    return fetch_tomtom_traffic(targeted_config)


def fetch_metar_weather(config):
    station = config["metar_station"]

    url = (
        "https://aviationweather.gov/api/data/metar"
        f"?ids={station}&format=json"
    )

    response = requests.get(url, timeout=config.get("request_timeout_sec", 3))
    response.raise_for_status()

    reports = response.json()
    if not reports:
        raise RuntimeError(f"No METAR report found for station {station}")

    metar = reports[0]

    wx = metar.get("wxString") or ""
    visibility = parse_visibility(metar.get("visib"))
    precip = float(metar.get("precip") or 0)

    return {
        "temperature_f": c_to_f(metar.get("temp", 0)),
        "visibility_miles": visibility,
        "precipitation_in": precip,
        "wind_speed_mph": knots_to_mph(metar.get("wspd")),
        "is_rain": 1 if "RA" in wx or precip > 0 else 0,
        "is_low_visibility": 1 if visibility < 3 else 0,
    }