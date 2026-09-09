"""Common interface implemented by every forecasting model.

Keeping this interface small (fit/predict/feature_columns) lets the training
service, walk-forward validator, and forecasting service treat Seasonal
Naive, Linear Regression, and LightGBM interchangeably.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class BaseForecastModel(ABC):
    model_type: str
    feature_columns: list[str]

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseForecastModel":
        ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        ...
