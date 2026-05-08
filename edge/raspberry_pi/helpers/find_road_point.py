import json
from edge.raspberry_pi.helpers.live_sources import fetch_tomtom_traffic


API_KEY = "r0dOGDbwKMxLS5mer68NVh7yHlhWGc4t"
MIN_FREE_FLOW_MPH = 50

POINTS = [
    (35.2535, -120.6875),
    (35.2550, -120.6865),
    (35.2570, -120.6855),

    (35.2655, -120.6815),
    (35.2670, -120.6805),
    (35.2690, -120.6790),

    (35.2760, -120.6725),
    (35.2790, -120.6700),
    (35.2820, -120.6680),

    (35.2900, -120.6635),
    (35.2930, -120.6615),
]


for lat, lon in POINTS:
    config = {
        "tomtom_api_key": API_KEY,
        "latitude": lat,
        "longitude": lon,
        "request_timeout_sec": 5,
    }

    try:
        traffic = fetch_tomtom_traffic(config)

        free_flow = traffic["free_flow_speed_mph"]
        print(f"Checked {lat}, {lon} -> free flow {free_flow} mph")

        if free_flow >= MIN_FREE_FLOW_MPH:
            print("\nFOUND MATCH")
            print(f"target_latitude: {lat}")
            print(f"target_longitude: {lon}")
            print(json.dumps(traffic, indent=2))
            break

    except Exception as e:
        print(f"Failed {lat}, {lon}: {e}")

else:
    print("\nNo point met the condition.")