import requests


OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"


def fetch_osm_road_point(config):
    lat = config["latitude"]
    lon = config["longitude"]
    radius_m = config.get("osm_search_radius_m", 1000)
    road_ref = config.get("target_road_ref", "US 101")

    query = f"""
    [out:json][timeout:25];
    (
        way(around:{radius_m},{lat},{lon})["highway"]["ref"~"101"];
        way(around:{radius_m},{lat},{lon})["highway"]["name"~"101"];
        way(around:{radius_m},{lat},{lon})["highway"]["name"~"US 101"];
    );
    out geom;
    """

    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        headers={
            "User-Agent": "CRPS-RaspberryPi-Client/1.0",
            "Accept": "application/json"
        },
        timeout=config.get("osm_request_timeout_sec", 20),
    )
    response.raise_for_status()

    data = response.json()
    ways = data.get("elements", [])

    if not ways:
        raise RuntimeError(f"No OSM roadway found for ref={road_ref}")

    way = ways[0]
    geometry = way.get("geometry", [])

    if not geometry:
        raise RuntimeError("OSM way has no geometry")

    midpoint = geometry[len(geometry) // 2]

    return {
        "osm_way_id": way["id"],
        "road_name": way.get("tags", {}).get("name", "unknown"),
        "road_ref": way.get("tags", {}).get("ref", road_ref),
        "latitude": midpoint["lat"],
        "longitude": midpoint["lon"],
    }