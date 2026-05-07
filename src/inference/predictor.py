from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import polars as pl

from src.inference.model_adapters import BaseModelAdapter, XGBoostModelAdapter

@dataclass
class PredictionResult:
    segment_id: str
    station_id: str
    current_speed_mph: float
    free_flow_speed_mph: float
    speed_ratio: float
    current_congestion: bool
    future_congestion_probability: float
    recommended_speed_mph: int
    model_name: str


class TrafficRiskPredictor:
    def __init__(
        self,
        model_adapter: Optional[BaseModelAdapter] = None,
        threshold_current_congestion: float = 0.60,
        min_speed_mph: int = 25,
    ) -> None:
        self.model_adapter = model_adapter or XGBoostModelAdapter()
        self.threshold_current_congestion = threshold_current_congestion
        self.min_speed_mph = min_speed_mph

        self.non_model_cols = [
            "timestamp",
            "timestamp_hour",
            "segment_id",
            "station_id",
            "congestion_label_future",
            "crash_label_future",
            "congestion_now",
            "speed_ratio",
            "speed_mph",
            "free_flow_speed_mph",
        ]

    def predict_one(self, feature_row: pl.DataFrame) -> PredictionResult:
        if feature_row.height != 1:
            raise ValueError("predict_one expects exactly one feature row.")

        row = feature_row.row(0, named=True)

        current_speed = float(row["speed_mph"])
        free_flow_speed = float(row["free_flow_speed_mph"])
        speed_ratio = float(row["speed_ratio"])

        current_congestion = speed_ratio < self.threshold_current_congestion

        model_input = self._model_input(feature_row)
        future_prob = self.model_adapter.predict_probability(model_input)[0]

        recommended_speed = self._recommend_speed(
            current_speed_mph=current_speed,
            free_flow_speed_mph=free_flow_speed,
            speed_ratio=speed_ratio,
            current_congestion=current_congestion,
            future_congestion_probability=future_prob,
        )

        return PredictionResult(
            segment_id=str(row["segment_id"]),
            station_id=str(row["station_id"]),
            current_speed_mph=current_speed,
            free_flow_speed_mph=free_flow_speed,
            speed_ratio=speed_ratio,
            current_congestion=current_congestion,
            future_congestion_probability=future_prob,
            recommended_speed_mph=recommended_speed,
            model_name=self.model_adapter.model_name,
        )

    def predict_batch(self, features: pl.DataFrame) -> pl.DataFrame:
        model_input = self._model_input(features)
        probs = self.model_adapter.predict_probability(model_input)

        results = features.with_columns(
            [
                pl.Series("future_congestion_probability", probs),
                (pl.col("speed_ratio") < self.threshold_current_congestion)
                .alias("current_congestion"),
            ]
        )

        results = results.with_columns(
            [
                pl.struct(
                    [
                        "speed_mph",
                        "free_flow_speed_mph",
                        "speed_ratio",
                        "current_congestion",
                        "future_congestion_probability",
                    ]
                )
                .map_elements(
                    lambda x: self._recommend_speed(
                        current_speed_mph=x["speed_mph"],
                        free_flow_speed_mph=x["free_flow_speed_mph"],
                        speed_ratio=x["speed_ratio"],
                        current_congestion=x["current_congestion"],
                        future_congestion_probability=x[
                            "future_congestion_probability"
                        ],
                    ),
                    return_dtype=pl.Int64,
                )
                .alias("recommended_speed_mph")
            ]
        )

        return results

    def _model_input(self, df: pl.DataFrame) -> pl.DataFrame:
        drop_existing = [c for c in self.non_model_cols if c in df.columns]
        return df.drop(drop_existing)

    def _recommend_speed(
        self,
        current_speed_mph: float,
        free_flow_speed_mph: float,
        speed_ratio: float,
        current_congestion: bool,
        future_congestion_probability: float,
    ) -> int:
        base_speed = min(current_speed_mph, free_flow_speed_mph)

        if current_congestion:
            recommended = base_speed - 20
        elif future_congestion_probability >= 0.85:
            recommended = base_speed - 15
        elif future_congestion_probability >= 0.70:
            recommended = base_speed - 10
        elif future_congestion_probability >= 0.50:
            recommended = base_speed - 5
        else:
            recommended = base_speed

        recommended = max(self.min_speed_mph, recommended)
        return int(round(recommended / 5) * 5)


def main() -> None:
    predictor = TrafficRiskPredictor()

    features = pl.read_parquet("data/processed/gold/features.parquet")

    sample = features.drop_nulls(
        [
            "speed_rolling_mean_15min",
            "speed_rolling_std_15min",
            "flow_rolling_mean_15min",
            "occupancy_rolling_mean_15min",
        ]
    ).head(1)

    result = predictor.predict_one(sample)
    print(result)


if __name__ == "__main__":
    main()