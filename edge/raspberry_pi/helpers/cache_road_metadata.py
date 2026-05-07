import json
import re
from pathlib import Path

import requests


CONFIG_PATH = Path("edge/raspberry_pi/config.json")
CACHE_PATH = Path("edge/raspberry_pi/helpers/cache/road_metadata_cache.json")
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def parse_speed_limit_mph(maxspeed):
    if not maxspeed:
        return None

    text = str(maxspeed).lower()

    match = re.search(r"\d+", text)
    if not match:
        return None

    value = int(match.group())

    if "km/h" in text or "kph" in text:
        return round(value * 0.621371)

    return value


def query_osm_maxspeed(lat, lon, radius_m=50):
    query = f"""
    [out:json][timeout:25];
    (
      way(around:{radius_m},{lat},{lon})["highway"]["maxspeed"];
    );
    out tags center;
    """

    last_error = None

    for url in OVERPASS_URLS:
        try:
            response = requests.post(
                url,
                data={"data": query},
                headers={
                    "User-Agent": "CRPS-SpeedLimit-Cache/1.0",
                    "Accept": "application/json",
                },
                timeout=30,
            )
            response.raise_for_status()

            elements = response.json().get("elements", [])

            if not elements:
                continue

            best = elements[0]
            tags = best.get("tags", {})

            return {
                "osm_way_id": best.get("id"),
                "road_name": tags.get("name"),
                "road_ref": tags.get("ref"),
                "highway": tags.get("highway"),
                "maxspeed_raw": tags.get("maxspeed"),
                "speed_limit_mph": parse_speed_limit_mph(tags.get("maxspeed")),
                "osm_source_url": url,
            }

        except requests.RequestException as e:
            last_error = e
            print(f"Overpass failed at {url}: {e}")

    return None


def main():
    config = load_config()

    lat = config.get("target_latitude", config["latitude"])
    lon = config.get("target_longitude", config["longitude"])

    result = None

    for radius in [25, 50, 100, 200, 500, 1000]:
        print(f"Searching OSM maxspeed within {radius} m...")

        result = query_osm_maxspeed(lat, lon, radius_m=radius)

        if result is not None and result["speed_limit_mph"] is not None:
            print(f"Found maxspeed within {radius} m")
            break

    if result is None or result["speed_limit_mph"] is None:
        raise RuntimeError(
            "Could not find OSM maxspeed near target coordinate. "
            "This road may not have maxspeed mapped in OSM. "
            "Use manual speed_limit_mph in config.json."
        )

    cache = {
        "target_latitude": lat,
        "target_longitude": lon,
        **result,
    }

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

    print("Cached road metadata:")
    print(json.dumps(cache, indent=2))


if __name__ == "__main__":
    main()