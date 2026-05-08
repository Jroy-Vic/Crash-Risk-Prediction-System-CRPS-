from pydantic import BaseModel
from typing import Optional


class PredictionRequest(BaseModel):
    segment_id: str
    station_id: str

    speed_mph: float
    free_flow_speed_mph: float
    speed_ratio: float
    speed_limit_mph: Optional[float] = None
    vehicle_speed_mph: float = 0.0
    heading_deg: float = 0.0
    horizon_seconds: int = 300

    flow_veh_per_interval: float
    occupancy_pct: float
    speed_delta_5min: Optional[float] = 0
    speed_delta_15min: Optional[float] = 0
    speed_rolling_mean_15min: Optional[float] = 0
    speed_rolling_std_15min: Optional[float] = 0
    flow_rolling_mean_15min: Optional[float] = 0
    occupancy_rolling_mean_15min: Optional[float] = 0
    demo_probability: float | None = None

    latitude: Optional[float] = 0
    longitude: Optional[float] = 0

    temperature_f: Optional[float] = 0
    precipitation_in: Optional[float] = 0
    visibility_miles: Optional[float] = 0
    wind_speed_mph: Optional[float] = 0
    is_rain: Optional[int] = 0
    is_low_visibility: Optional[int] = 0

    crash_count_current_window: Optional[int] = 0
    crash_count_past_1hr: Optional[int] = 0
    crash_count_past_24hr: Optional[int] = 0
    crash_count_past_7d: Optional[int] = 0

    hour: int
    day_of_week: int
    month: int
    is_weekend: int
    is_rush_hour: int


class PredictionResponse(BaseModel):
    segment_id: str
    station_id: str
    current_speed_mph: float
    speed_ratio: float
    current_congestion: bool
    future_congestion_probability: float
    recommended_speed_mph: int
    model_name: str
    