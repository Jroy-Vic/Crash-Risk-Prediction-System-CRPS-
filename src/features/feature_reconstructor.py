# src/utils/feature_reconstructor.py

from datetime import datetime
from zoneinfo import ZoneInfo


def clamp(value, low, high):
    return max(low, min(high, value))


def estimate_occupancy_pct(speed_ratio: float) -> float:
    """
    Approximate PeMS-style occupancy from speed_ratio.

    speed_ratio near 1.0 = free-flow traffic
    speed_ratio near 0.0 = severe congestion
    """

    speed_ratio = clamp(speed_ratio, 0.0, 1.2)

    if speed_ratio >= 0.95:
        occupancy = 5
    elif speed_ratio >= 0.80:
        occupancy = 8 + (0.95 - speed_ratio) * 40
    elif speed_ratio >= 0.60:
        occupancy = 14 + (0.80 - speed_ratio) * 55
    elif speed_ratio >= 0.40:
        occupancy = 25 + (0.60 - speed_ratio) * 75
    else:
        occupancy = 40 + (0.40 - speed_ratio) * 60

    return round(clamp(occupancy, 3, 65), 2)


def estimate_flow_veh_per_interval(speed_ratio: float, hour: int, is_weekend: int) -> int:
    """
    Approximate flow for a freeway segment.

    This is not true detector flow.
    It is a realism-preserving estimate to avoid corrupting model input.
    """

    speed_ratio = clamp(speed_ratio, 0.0, 1.2)

    # Base freeway flow estimate
    if is_weekend:
        base_flow = 900
    else:
        if 7 <= hour <= 9:
            base_flow = 1800
        elif 16 <= hour <= 18:
            base_flow = 2000
        elif 10 <= hour <= 15:
            base_flow = 1300
        elif 19 <= hour <= 22:
            base_flow = 900
        else:
            base_flow = 450

    # Lower speed ratio usually means reduced throughput,
    # but not necessarily zero flow.
    if speed_ratio >= 0.9:
        multiplier = 1.0
    elif speed_ratio >= 0.75:
        multiplier = 0.9
    elif speed_ratio >= 0.55:
        multiplier = 0.75
    elif speed_ratio >= 0.35:
        multiplier = 0.55
    else:
        multiplier = 0.35

    flow = int(base_flow * multiplier)

    return int(clamp(flow, 100, 2600))


def get_time_features(now=None, timezone="America/Los_Angeles"):
    if now is None:
        now = datetime.now(ZoneInfo(timezone))

    hour = now.hour
    day_of_week = now.weekday()
    month = now.month

    is_weekend = int(day_of_week >= 5)
    is_rush_hour = int(
        not is_weekend and (
            7 <= hour <= 9 or
            16 <= hour <= 18
        )
    )

    return {
        "hour": hour,
        "day_of_week": day_of_week,
        "month": month,
        "is_weekend": is_weekend,
        "is_rush_hour": is_rush_hour,
        "rush_hour": is_rush_hour,
    }


def reconstruct_features(raw: dict, timezone="America/Los_Angeles") -> dict:
    """
    Converts sparse live API data into backend/model-ready CRPS features.
    """

    speed_mph = float(raw.get("speed_mph", 0))
    free_flow_speed_mph = float(raw.get("free_flow_speed_mph", max(speed_mph, 1)))

    if free_flow_speed_mph <= 0:
        speed_ratio = 1.0
    else:
        speed_ratio = speed_mph / free_flow_speed_mph

    speed_ratio = round(clamp(speed_ratio, 0.0, 1.2), 3)

    time_features = get_time_features(timezone=timezone)

    flow = raw.get("flow")
    occupancy = raw.get("occupancy")

    if flow is None:
        flow = estimate_flow_veh_per_interval(
            speed_ratio=speed_ratio,
            hour=time_features["hour"],
            is_weekend=time_features["is_weekend"],
        )

    if occupancy is None:
        occupancy = estimate_occupancy_pct(speed_ratio)

    segment_id = raw.get("segment_id", "unknown_segment")

    payload = {
        "segment_id": segment_id,
        "station_id": raw.get("station_id", segment_id),

        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),

        "speed_mph": speed_mph,
        "free_flow_speed_mph": free_flow_speed_mph,
        "speed_ratio": speed_ratio,

        # Backend schema names
        "flow_veh_per_interval": int(flow),
        "occupancy_pct": float(occupancy),

        # Logger/simple aliases
        "flow": int(flow),
        "occupancy": float(occupancy),

        "temperature_f": float(raw.get("temperature_f", 60)),
        "visibility_miles": float(raw.get("visibility_miles", 10)),
        "wind_speed_mph": float(raw.get("wind_speed_mph", 0)),
        "precipitation": float(raw.get("precipitation", 0)),
        "is_rain": int(raw.get("is_rain", 0)),

        "speed_limit_mph": int(raw.get("speed_limit_mph", 65)),

        **time_features,
    }

    return payload