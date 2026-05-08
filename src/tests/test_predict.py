import requests

url = "http://localhost:8000/predict"

payload = {
  "segment_id": "demo_segment_001",
  "station_id": "demo_station_001",
  "latitude": 35.2828,
  "longitude": -120.6596,
  "vehicle_speed_mph": 45,
  "heading_deg": 90,
  "horizon_seconds": 300,
  "speed_mph": 50,
  "free_flow_speed_mph": 65,
  "speed_ratio": 0.77,
  "flow_veh_per_interval": 120,
  "occupancy_pct": 18,
  "temperature_f": 65,
  "visibility_miles": 10,
  "wind_speed_mph": 5,
  "precipitation_in": 0,
  "is_rain": 0,
  "hour": 12,
  "day_of_week": 3,
  "month": 5,
  "is_weekend": 0,
  "rush_hour": 0,
  "is_rush_hour": 0
}

response = requests.post(url, json=payload)

print(response.json())