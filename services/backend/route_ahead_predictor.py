from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Optional


EARTH_RADIUS_M = 6_371_000.0
DEFAULT_HORIZON_SECONDS = 300


@dataclass
class VehicleState:
    latitude: float
    longitude: float
    vehicle_speed_mph: float
    heading_deg: float


@dataclass
class RouteAheadTarget:
    latitude: float
    longitude: float
    horizon_seconds: int
    distance_ahead_m: float
    eta_timestamp_utc: str
    mode: str
    confidence: float


def mph_to_mps(speed_mph: float) -> float:
    return speed_mph * 0.44704


def normalize_heading(heading_deg: float) -> float:
    return heading_deg % 360.0


def project_forward(
    latitude: float,
    longitude: float,
    heading_deg: float,
    distance_m: float,
) -> tuple[float, float]:
    heading_rad = math.radians(normalize_heading(heading_deg))
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)

    angular_distance = distance_m / EARTH_RADIUS_M

    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(heading_rad)
    )

    lon2 = lon1 + math.atan2(
        math.sin(heading_rad) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )

    return math.degrees(lat2), math.degrees(lon2)


def get_route_ahead_target(
    vehicle: VehicleState,
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
    now_utc: Optional[datetime] = None,
) -> RouteAheadTarget:
    """
    Step 1 implementation:
    Predicts the target point approximately `horizon_seconds` ahead
    using current GPS, heading, and speed.

    This is the no-destination fallback mode.
    Later, this can be upgraded to follow TomTom route geometry.
    """

    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    safe_speed_mph = max(vehicle.vehicle_speed_mph, 0.0)
    distance_ahead_m = mph_to_mps(safe_speed_mph) * horizon_seconds

    target_lat, target_lon = project_forward(
        latitude=vehicle.latitude,
        longitude=vehicle.longitude,
        heading_deg=vehicle.heading_deg,
        distance_m=distance_ahead_m,
    )

    eta = now_utc + timedelta(seconds=horizon_seconds)

    confidence = 0.65 if safe_speed_mph > 3 else 0.35

    return RouteAheadTarget(
        latitude=target_lat,
        longitude=target_lon,
        horizon_seconds=horizon_seconds,
        distance_ahead_m=distance_ahead_m,
        eta_timestamp_utc=eta.isoformat(),
        mode="heading_projection",
        confidence=confidence,
    )


def get_route_ahead_target_dict(
    latitude: float,
    longitude: float,
    vehicle_speed_mph: float,
    heading_deg: float,
    horizon_seconds: int = DEFAULT_HORIZON_SECONDS,
) -> dict:
    vehicle = VehicleState(
        latitude=latitude,
        longitude=longitude,
        vehicle_speed_mph=vehicle_speed_mph,
        heading_deg=heading_deg,
    )

    return asdict(
        get_route_ahead_target(
            vehicle=vehicle,
            horizon_seconds=horizon_seconds,
        )
    )