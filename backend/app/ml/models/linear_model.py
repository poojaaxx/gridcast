"""Linear regression baseline using calendar, weather, and a handful of lag
features. Scaled with StandardScaler since raw MW magnitudes and 0/1 flags
otherwise dominate the fit unevenly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.features.pipeline import LINEAR_FEATURE_COLUMNS
from app.ml.models.base import BaseForecastModel


class LinearRegressionModel(BaseForecastModel):
    model_type = "linear_regression"

    def __init__(self) -> None:
        self.feature_columns = list(LINEAR_FEATURE_COLUMNS)
        self._pipeline = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("regressor", LinearRegression()),
            ]
        )

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LinearRegressionModel":
        self._pipeline.fit(X[self.feature_columns], y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self._pipeline.predict(X[self.feature_columns])
