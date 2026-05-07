"""
feature_builder.py

Builds canonical ML feature rows for the traffic congestion / crash risk system.

Inputs:
    - PeMS District 5 station 5-minute .txt.gz files
    - NOAA SLO_weather_2025.csv
    - CCRS crashes_2025.csv

Output:
    - features.parquet

Canonical row:
    segment_id + timestamp -> traffic/weather/crash/time features + labels
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from sklearn.neighbors import BallTree
import numpy as np

import polars as pl


@dataclass(frozen=True)
class FeatureConfig:
    window_minutes: int = 5
    congestion_horizon_minutes: int = 15
    crash_horizon_minutes: int = 30

    congestion_speed_ratio_threshold: float = 0.60
    low_visibility_threshold_miles: float = 2.0
    rain_threshold_inches: float = 0.01

    default_free_flow_speed_mph: float = 65.0
    min_recommended_speed_mph: int = 25


class FeatureBuilder:
    def __init__(self, config: Optional[FeatureConfig] = None) -> None:
        self.config = config or FeatureConfig()

    def build_features(
    self,
        pems_df: pl.DataFrame,
        weather_df: pl.DataFrame,
        crash_df: Optional[pl.DataFrame] = None,
        station_meta_df: Optional[pl.DataFrame] = None,
    ) -> pl.DataFrame:
        pems = self._build_traffic_features(pems_df)

        if station_meta_df is not None:
            station_meta = self._build_station_metadata(station_meta_df)
            pems = pems.join(station_meta, on="station_id", how="left")

        weather = self._build_weather_features(weather_df)

        features = pems.join(weather, on="timestamp_hour", how="left")

        if crash_df is not None and station_meta_df is not None:
            crashes = self._build_crash_features(crash_df, pems, station_meta)
            features = features.join(
                crashes,
                on=["segment_id", "timestamp"],
                how="left",
            )

        features = self._build_temporal_features(features)
        features = self._build_congestion_labels(features)
        features = self._build_crash_labels(features)
        features = self._finalize_schema(features)

        return features
    
    def _build_station_metadata(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Expected PeMS metadata columns vary, so this function normalizes common names.

        Needed output:
            station_id
            latitude
            longitude
        """

        rename_map = {}

        for col in df.columns:
            clean = col.strip().lower()

            if clean in ["station", "station_id", "id"]:
                rename_map[col] = "station_id"
            elif clean in ["latitude", "lat"]:
                rename_map[col] = "latitude"
            elif clean in ["longitude", "lon", "lng"]:
                rename_map[col] = "longitude"

        df = df.rename(rename_map)

        required = ["station_id", "latitude", "longitude"]
        missing = [c for c in required if c not in df.columns]

        if missing:
            raise ValueError(
                f"Station metadata is missing columns: {missing}. "
                f"Available columns: {df.columns}"
            )

        return (
            df.select(["station_id", "latitude", "longitude"])
            .with_columns(
                [
                    pl.col("station_id").cast(pl.Utf8),
                    pl.col("latitude").cast(pl.Float64, strict=False),
                    pl.col("longitude").cast(pl.Float64, strict=False),
                ]
            )
            .drop_nulls(["station_id", "latitude", "longitude"])
            .unique("station_id")
        )

    # ------------------------------------------------------------------
    # PeMS
    # ------------------------------------------------------------------

    def _standardize_pems_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        rename_map = {
            "total_flow": "flow_veh_per_interval",
            "avg_occupancy": "occupancy_pct",
            "avg_speed": "speed_mph",
        }

        existing = {k: v for k, v in rename_map.items() if k in df.columns}
        return df.rename(existing)

    def _build_traffic_features(self, df: pl.DataFrame) -> pl.DataFrame:
        df = self._standardize_pems_columns(df)

        required = [
            "timestamp",
            "station_id",
            "speed_mph",
            "flow_veh_per_interval",
            "occupancy_pct",
        ]

        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"PeMS data is missing columns: {missing}")

        df = df.with_columns(
            [
                pl.col("timestamp")
                .cast(pl.Utf8)
                .str.strip_chars()
                .str.strptime(
                    pl.Datetime,
                    format="%m/%d/%Y %H:%M:%S",
                    strict=False,
                )
                .alias("timestamp"),

                pl.col("station_id").cast(pl.Utf8),

                pl.col("speed_mph").cast(pl.Float64, strict=False),
                pl.col("flow_veh_per_interval").cast(pl.Float64, strict=False),
                pl.col("occupancy_pct").cast(pl.Float64, strict=False),
            ]
        )

        df = df.with_columns(
            [
                pl.col("station_id").alias("segment_id"),
                pl.col("timestamp").dt.truncate("1h").alias("timestamp_hour"),
            ]
        )

        df = df.with_columns(
            [
                pl.when(pl.col("speed_mph") < 0)
                .then(None)
                .otherwise(pl.col("speed_mph"))
                .alias("speed_mph"),

                pl.when(pl.col("flow_veh_per_interval") < 0)
                .then(None)
                .otherwise(pl.col("flow_veh_per_interval"))
                .alias("flow_veh_per_interval"),

                pl.when(pl.col("occupancy_pct") < 0)
                .then(None)
                .otherwise(pl.col("occupancy_pct"))
                .alias("occupancy_pct"),
            ]
        )

        df = df.sort(["segment_id", "timestamp"])

        free_flow = (
            df.group_by("segment_id")
            .agg(
                pl.col("speed_mph")
                .quantile(0.95)
                .fill_null(self.config.default_free_flow_speed_mph)
                .alias("free_flow_speed_mph")
            )
        )

        df = df.join(free_flow, on="segment_id", how="left")

        df = df.with_columns(
            [
                (pl.col("speed_mph") / pl.col("free_flow_speed_mph"))
                .alias("speed_ratio"),

                pl.col("speed_mph")
                .diff()
                .over("segment_id")
                .alias("speed_delta_5min"),

                (
                    pl.col("speed_mph")
                    - pl.col("speed_mph").shift(3).over("segment_id")
                ).alias("speed_delta_15min"),

                pl.col("speed_mph")
                .rolling_mean(window_size=3)
                .over("segment_id")
                .alias("speed_rolling_mean_15min"),

                pl.col("speed_mph")
                .rolling_std(window_size=3)
                .over("segment_id")
                .alias("speed_rolling_std_15min"),

                pl.col("flow_veh_per_interval")
                .rolling_mean(window_size=3)
                .over("segment_id")
                .alias("flow_rolling_mean_15min"),

                pl.col("occupancy_pct")
                .rolling_mean(window_size=3)
                .over("segment_id")
                .alias("occupancy_rolling_mean_15min"),
            ]
        )

        df = df.with_columns(
            [
                (
                    pl.col("speed_ratio")
                    < self.config.congestion_speed_ratio_threshold
                )
                .cast(pl.Int8)
                .alias("congestion_now")
            ]
        )

        return df

    # ------------------------------------------------------------------
    # NOAA Weather
    # ------------------------------------------------------------------

    def _build_weather_features(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Supports already-clean weather columns if present:
            DATE
            TMP
            VIS
            WND
            AA1

        NOAA Global Hourly columns are often encoded:
            TMP: +0167,1   -> 16.7 C
            VIS: 016000,1  -> 16000 meters
            WND: 270,1,N,0041,1 -> 4.1 m/s
            AA1: 01,0003,9,1 -> precipitation depth
        """

        if "DATE" in df.columns:
            df = df.rename({"DATE": "timestamp"})

        if "timestamp" not in df.columns:
            raise ValueError("Weather data must contain DATE or timestamp column.")

        df = df.with_columns(
            [
                pl.col("timestamp")
                .str.strptime(pl.Datetime, strict=False)
                .dt.truncate("1h")
                .alias("timestamp_hour")
            ]
        )

        if "TMP" in df.columns:
            df = df.with_columns(
                [
                    (
                        pl.col("TMP")
                        .str.split(",")
                        .list.get(0)
                        .cast(pl.Float64, strict=False)
                        / 10.0
                    ).alias("temperature_c")
                ]
            )

            df = df.with_columns(
                [
                    ((pl.col("temperature_c") * 9.0 / 5.0) + 32.0)
                    .alias("temperature_f")
                ]
            )
        else:
            df = df.with_columns(pl.lit(None).alias("temperature_f"))

        if "VIS" in df.columns:
            df = df.with_columns(
                [
                    (
                        pl.col("VIS")
                        .str.split(",")
                        .list.get(0)
                        .cast(pl.Float64, strict=False)
                        / 1609.344
                    ).alias("visibility_miles")
                ]
            )
        else:
            df = df.with_columns(pl.lit(None).alias("visibility_miles"))

        if "WND" in df.columns:
            df = df.with_columns(
                [
                    (
                        pl.col("WND")
                        .str.split(",")
                        .list.get(3)
                        .cast(pl.Float64, strict=False)
                        / 10.0
                        * 2.23694
                    ).alias("wind_speed_mph")
                ]
            )
        else:
            df = df.with_columns(pl.lit(None).alias("wind_speed_mph"))

        if "AA1" in df.columns:
            df = df.with_columns(
                [
                    (
                        pl.col("AA1")
                        .str.split(",")
                        .list.get(1)
                        .cast(pl.Float64, strict=False)
                        / 10.0
                        / 25.4
                    ).alias("precipitation_in")
                ]
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias("precipitation_in"))

        df = df.with_columns(
            [
                (
                    pl.col("precipitation_in")
                    >= self.config.rain_threshold_inches
                )
                .cast(pl.Int8)
                .alias("is_rain"),

                (
                    pl.col("visibility_miles")
                    <= self.config.low_visibility_threshold_miles
                )
                .cast(pl.Int8)
                .alias("is_low_visibility"),
            ]
        )

        return (
            df.group_by("timestamp_hour")
            .agg(
                [
                    pl.col("temperature_f").mean().alias("temperature_f"),
                    pl.col("precipitation_in").max().alias("precipitation_in"),
                    pl.col("visibility_miles").mean().alias("visibility_miles"),
                    pl.col("wind_speed_mph").mean().alias("wind_speed_mph"),
                    pl.col("is_rain").max().alias("is_rain"),
                    pl.col("is_low_visibility").max().alias("is_low_visibility"),
                ]
            )
            .sort("timestamp_hour")
        )

    # ------------------------------------------------------------------
    # CCRS Crashes
    # ------------------------------------------------------------------

    def _build_crash_features(
    self,
        crash_df: pl.DataFrame,
        pems_df: pl.DataFrame,
        station_meta_df: pl.DataFrame,
    ) -> pl.DataFrame:

        timestamp_col = self._find_first_existing_column(
            crash_df,
            [
                "Crash Date Time",
                "timestamp",
                "crash_datetime",
                "collision_datetime",
                "crash_date_time",
                "crash_date",
                "collision_date",
                "accident_date",
            ],
        )

        lat_col = self._find_first_existing_column(
            crash_df,
            ["Latitude", "lat", "crash_latitude"],
        )

        lon_col = self._find_first_existing_column(
            crash_df,
            ["Longitude", "lon", "lng", "crash_longitude"],
        )

        if timestamp_col is None:
            raise ValueError("Could not find crash timestamp column.")

        if lat_col is None or lon_col is None:
            raise ValueError("Could not find crash latitude/longitude columns.")

        crashes = (
            crash_df.with_columns(
                [
                    pl.col(timestamp_col)
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.strptime(
                        pl.Datetime,
                        format="%m/%d/%Y %I:%M:%S %p",
                        strict=False,
                    )
                    .dt.truncate(f"{self.config.window_minutes}m")
                    .alias("timestamp"),

                    pl.col(lat_col)
                    .cast(pl.Float64, strict=False)
                    .alias("crash_latitude"),

                    pl.col(lon_col)
                    .cast(pl.Float64, strict=False)
                    .alias("crash_longitude"),
                ]
            )
            .drop_nulls(["timestamp", "crash_latitude", "crash_longitude"])
        )

        stations = (
            station_meta_df
            .select(["station_id", "latitude", "longitude"])
            .drop_nulls(["station_id", "latitude", "longitude"])
            .unique("station_id")
        )

        # Filter crashes to nearby station bounding box.
        # This prevents statewide CCRS crashes from being matched to SLO stations.
        lat_min = stations["latitude"].min() - 0.25
        lat_max = stations["latitude"].max() + 0.25
        lon_min = stations["longitude"].min() - 0.25
        lon_max = stations["longitude"].max() + 0.25

        crashes = crashes.filter(
            (pl.col("crash_latitude") >= lat_min)
            & (pl.col("crash_latitude") <= lat_max)
            & (pl.col("crash_longitude") >= lon_min)
            & (pl.col("crash_longitude") <= lon_max)
        )

        if crashes.height == 0:
            return pl.DataFrame(
                {
                    "segment_id": [],
                    "timestamp": [],
                    "crash_count_current_window": [],
                    "crash_count_past_1hr": [],
                    "crash_count_past_24hr": [],
                    "crash_count_past_7d": [],
                }
            )

        station_coords = np.radians(
            stations.select(["latitude", "longitude"]).to_numpy()
        )

        crash_coords = np.radians(
            crashes.select(["crash_latitude", "crash_longitude"]).to_numpy()
        )

        tree = BallTree(station_coords, metric="haversine")
        distances, indices = tree.query(crash_coords, k=1)

        station_ids = stations["station_id"].to_list()
        nearest_station_ids = [station_ids[i[0]] for i in indices]

        crashes = crashes.with_columns(
            [
                pl.Series("segment_id", nearest_station_ids).cast(pl.Utf8)
            ]
        )

        crash_counts = (
            crashes.group_by(["segment_id", "timestamp"])
            .agg(pl.len().alias("crash_count_current_window"))
            .sort(["segment_id", "timestamp"])
        )

        crash_counts = crash_counts.with_columns(
            [
                pl.col("crash_count_current_window")
                .rolling_sum(window_size=12)
                .over("segment_id")
                .alias("crash_count_past_1hr"),

                pl.col("crash_count_current_window")
                .rolling_sum(window_size=288)
                .over("segment_id")
                .alias("crash_count_past_24hr"),

                pl.col("crash_count_current_window")
                .rolling_sum(window_size=2016)
                .over("segment_id")
                .alias("crash_count_past_7d"),
            ]
        )

        return crash_counts

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def _build_congestion_labels(self, df: pl.DataFrame) -> pl.DataFrame:
        horizon_steps = (
            self.config.congestion_horizon_minutes
            // self.config.window_minutes
        )

        future_exprs = [
            pl.col("congestion_now").shift(-i).over("segment_id")
            for i in range(1, horizon_steps + 1)
        ]

        return df.with_columns(
            [
                pl.max_horizontal(future_exprs)
                .fill_null(0)
                .cast(pl.Int8)
                .alias("congestion_label_future")
            ]
        )

    def _build_crash_labels(self, df: pl.DataFrame) -> pl.DataFrame:
        if "crash_count_current_window" not in df.columns:
            return df.with_columns(pl.lit(0).cast(pl.Int8).alias("crash_label_future"))

        horizon_steps = self.config.crash_horizon_minutes // self.config.window_minutes

        future_exprs = [
            pl.col("crash_count_current_window").shift(-i).over("segment_id")
            for i in range(1, horizon_steps + 1)
        ]

        return df.with_columns(
            [
                (pl.max_horizontal(future_exprs).fill_null(0) > 0)
                .cast(pl.Int8)
                .alias("crash_label_future")
            ]
        )

    # ------------------------------------------------------------------
    # Time features
    # ------------------------------------------------------------------

    def _build_temporal_features(self, df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(
            [
                pl.col("timestamp").dt.hour().alias("hour"),
                pl.col("timestamp").dt.weekday().alias("day_of_week"),
                pl.col("timestamp").dt.month().alias("month"),

                (pl.col("timestamp").dt.weekday() >= 6)
                .cast(pl.Int8)
                .alias("is_weekend"),

                (
                    pl.col("timestamp").dt.hour().is_between(7, 9)
                    | pl.col("timestamp").dt.hour().is_between(16, 18)
                )
                .cast(pl.Int8)
                .alias("is_rush_hour"),
            ]
        )

    # ------------------------------------------------------------------
    # Final schema
    # ------------------------------------------------------------------

    def _finalize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        required_columns = [
            "segment_id",
            "station_id",
            "timestamp",
            "timestamp_hour",
            "latitude",
            "longitude",

            "speed_mph",
            "flow_veh_per_interval",
            "occupancy_pct",
            "free_flow_speed_mph",
            "speed_ratio",
            "speed_delta_5min",
            "speed_delta_15min",
            "speed_rolling_mean_15min",
            "speed_rolling_std_15min",
            "flow_rolling_mean_15min",
            "occupancy_rolling_mean_15min",
            "congestion_now",

            "temperature_f",
            "precipitation_in",
            "visibility_miles",
            "wind_speed_mph",
            "is_rain",
            "is_low_visibility",

            "crash_count_current_window",
            "crash_count_past_1hr",
            "crash_count_past_24hr",
            "crash_count_past_7d",

            "hour",
            "day_of_week",
            "month",
            "is_weekend",
            "is_rush_hour",

            "congestion_label_future",
            "crash_label_future",
        ]

        for col in required_columns:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        df = df.select(required_columns)

        return df.with_columns(
            [
                pl.col("crash_count_current_window").fill_null(0),
                pl.col("crash_count_past_1hr").fill_null(0),
                pl.col("crash_count_past_24hr").fill_null(0),
                pl.col("crash_count_past_7d").fill_null(0),

                pl.col("is_rain").fill_null(0),
                pl.col("is_low_visibility").fill_null(0),
                pl.col("congestion_now").fill_null(0),

                pl.col("congestion_label_future").fill_null(0),
                pl.col("crash_label_future").fill_null(0),
            ]
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_first_existing_column(
        df: pl.DataFrame,
        candidates: list[str],
    ) -> Optional[str]:
        normalized_to_original = {
            c.strip().lower(): c for c in df.columns
        }

        for candidate in candidates:
            key = candidate.strip().lower()
            if key in normalized_to_original:
                return normalized_to_original[key]

        return None


# ----------------------------------------------------------------------
# File loading helpers
# ----------------------------------------------------------------------

def load_pems_files(path_or_dir: str | Path) -> pl.DataFrame:
    path = Path(path_or_dir)

    if path.is_dir():
        files = sorted(path.glob("*.txt.gz"))
    else:
        files = [path]

    if not files:
        raise FileNotFoundError(f"No PeMS .txt.gz files found in {path}")

    pems_columns = [
        "timestamp",
        "station_id",
        "district",
        "freeway",
        "direction",
        "lane_type",
        "station_length",
        "samples",
        "percent_observed",
        "total_flow",
        "avg_occupancy",
        "avg_speed",
    ]

    dfs = []

    for file in files:
        print(f"Loading PeMS file: {file}")

        df = pl.read_csv(
            file,
            has_header=False,
            new_columns=pems_columns,
            infer_schema_length=10000,
        )

        dfs.append(df)

    return pl.concat(dfs, how="vertical_relaxed")


def load_weather_file(path: str | Path) -> pl.DataFrame:
    print(f"Loading weather file: {path}")
    return pl.read_csv(path, infer_schema_length=10000)


def load_crash_file(path: str | Path) -> pl.DataFrame:
    print(f"Loading crash file: {path}")

    return pl.read_csv(
        path,
        infer_schema_length=0,  # read all columns as strings
        ignore_errors=True,
    )

def load_station_metadata_file(path: str | Path) -> pl.DataFrame:
    print(f"Loading PeMS station metadata file: {path}")

    return pl.read_csv(
        path,
        separator="\t",
        infer_schema_length=0,
        ignore_errors=True,
        truncate_ragged_lines=True,
    )

def build_features_from_files(
    pems_path_or_dir: str | Path,
    weather_path: str | Path,
    crash_path: str | Path,
    station_meta_path: str | Path,
    output_path: str | Path,
) -> None:
    builder = FeatureBuilder()

    pems_df = load_pems_files(pems_path_or_dir)
    weather_df = load_weather_file(weather_path)
    crash_df = load_crash_file(crash_path)
    station_meta_df = load_station_metadata_file(station_meta_path)

    features = builder.build_features(
        pems_df=pems_df,
        weather_df=weather_df,
        crash_df=crash_df,
        station_meta_df=station_meta_df,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    features.write_parquet(output_path)

    print(f"Saved feature table to: {output_path}")
    print(f"Rows: {features.height}")
    print(f"Columns: {features.width}")


if __name__ == "__main__":
    build_features_from_files(
        pems_path_or_dir="data/raw/pems/",
        weather_path="data/raw/noaa/SLO_weather_2025.csv",
        crash_path="data/raw/ccrs/crashes_2025.csv",
        station_meta_path="data/raw/pems/d05_text_meta_2025_12_31.txt",
        output_path="data/processed/gold/features.parquet",
    )