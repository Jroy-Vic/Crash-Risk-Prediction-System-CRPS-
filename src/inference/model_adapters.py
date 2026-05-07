from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import json

import joblib
import polars as pl


class BaseModelAdapter(ABC):
    def __init__(
        self,
        model_path: str | Path,
        feature_schema_path: str | Path,
        model_name: str,
    ) -> None:
        self.model_path = Path(model_path)
        self.feature_schema_path = Path(feature_schema_path)
        self.model_name = model_name

        self.model = joblib.load(self.model_path)

        with open(self.feature_schema_path, "r") as f:
            self.feature_names = json.load(f)

    def prepare_features(self, df: pl.DataFrame):
        X = df.clone()

        for col in self.feature_names:
            if col not in X.columns:
                X = X.with_columns(pl.lit(0).alias(col))

        X = X.select(self.feature_names).fill_null(0)

        return X.to_numpy()

    @abstractmethod
    def predict_probability(self, df: pl.DataFrame) -> list[float]:
        pass


class XGBoostModelAdapter(BaseModelAdapter):
    def __init__(
        self,
        model_path: str | Path = "models/trained/xgboost/xgboost_congestion.pkl",
        feature_schema_path: str | Path = "models/trained/xgboost/xgboost_congestion_features.json",
    ) -> None:
        super().__init__(
            model_path=model_path,
            feature_schema_path=feature_schema_path,
            model_name="xgboost_congestion",
        )

    def predict_probability(self, df: pl.DataFrame) -> list[float]:
        X = self.prepare_features(df)
        probs = self.model.predict_proba(X)[:, 1]
        return probs.tolist()