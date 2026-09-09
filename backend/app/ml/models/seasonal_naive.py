"""Seasonal Naive baseline: predict(t) = load(t - 168 hours), i.e. the same
hour on the same weekday, one week prior. This is the primary baseline every
other model must beat to be considered useful.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.models.base import BaseForecastModel


class SeasonalNaiveModel(BaseForecastModel):
    model_type = "seasonal_naive"

    def __init__(self) -> None:
        self.feature_columns = ["load_lag_168"]
        self._fitted = False

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "SeasonalNaiveModel":
        # Stateless: nothing to learn, but we mark fitted for interface parity.
        self._fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if "load_lag_168" not in X.columns:
            raise ValueError("SeasonalNaiveModel requires a 'load_lag_168' column.")
        return X["load_lag_168"].to_numpy()
