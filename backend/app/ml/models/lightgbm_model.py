"""LightGBM gradient-boosted tree model - the primary production candidate.

Uses the full feature set (calendar + lags + rolling stats + weather).
Hyperparameters are intentionally conservative/sensible defaults rather than
tuned; they are exposed as constructor arguments so they can be adjusted
without touching training logic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from app.ml.features.pipeline import FULL_FEATURE_COLUMNS
from app.ml.models.base import BaseForecastModel


class LightGBMModel(BaseForecastModel):
    model_type = "lightgbm"

    def __init__(
        self,
        n_estimators: int = 400,
        learning_rate: float = 0.03,
        num_leaves: int = 31,
        max_depth: int = -1,
        min_child_samples: int = 20,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
    ) -> None:
        self.feature_columns = list(FULL_FEATURE_COLUMNS)
        self._model = LGBMRegressor(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            num_leaves=num_leaves,
            max_depth=max_depth,
            min_child_samples=min_child_samples,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            random_state=random_state,
            verbosity=-1,
        )

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LightGBMModel":
        self._model.fit(X[self.feature_columns], y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self._model.predict(X[self.feature_columns])

    @property
    def feature_importances(self) -> dict[str, float]:
        return dict(zip(self.feature_columns, self._model.feature_importances_.tolist()))
