"""Lag and rolling-window features computed strictly from past observations.

Leakage prevention: rolling statistics are computed on the series shifted by
1 hour *before* the window is applied, so ``rolling_mean_24`` at time ``t``
only ever sees ``load[t-25 : t-1]`` inclusive - never ``load[t]`` itself.
"""
from __future__ import annotations

import pandas as pd

LAG_HOURS = [1, 2, 3, 24, 48, 72, 168]
ROLLING_WINDOWS = [24, 72, 168]

LAG_FEATURE_COLUMNS = [f"load_lag_{h}" for h in LAG_HOURS]
ROLLING_MEAN_COLUMNS = [f"rolling_mean_{w}" for w in ROLLING_WINDOWS]
ROLLING_STD_COLUMNS = [f"rolling_std_{w}" for w in (24, 72)]


def add_lag_features(df: pd.DataFrame, target_col: str = "load_mw") -> pd.DataFrame:
    """Assumes ``df`` is sorted ascending by timestamp with an hourly cadence."""
    df = df.copy()
    for lag in LAG_HOURS:
        df[f"load_lag_{lag}"] = df[target_col].shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame, target_col: str = "load_mw") -> pd.DataFrame:
    """Rolling mean/std computed on data shifted by 1 to exclude the current row."""
    df = df.copy()
    shifted = df[target_col].shift(1)
    for window in ROLLING_WINDOWS:
        df[f"rolling_mean_{window}"] = shifted.rolling(window=window, min_periods=max(1, window // 4)).mean()
    for window in (24, 72):
        df[f"rolling_std_{window}"] = shifted.rolling(window=window, min_periods=max(1, window // 4)).std()
    return df
