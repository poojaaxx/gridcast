"""Reusable feature engineering pipeline shared by training and inference.

Feature families
----------------
Calendar   : hour, day_of_week, day_of_month, month, week_of_year, is_weekend,
             is_holiday, plus cyclical sin/cos encodings of hour & day_of_week.
Lag        : load_lag_{1,2,3,24,48,72,168} - previous observed load values.
Rolling    : rolling_mean/std over 24/72/168h windows, shifted to avoid leakage.
Weather    : temperature_c, humidity_percent, temperature_squared,
             cooling_degree_proxy, heating_degree_proxy.

``build_feature_frame`` is the single entry point used by both the training
service (on historical data) and the forecasting service (recursively, one
step at a time, on a mix of historical + previously-predicted values).
"""
from __future__ import annotations

import pandas as pd

from app.ml.features.calendar_features import CALENDAR_FEATURE_COLUMNS, add_calendar_features
from app.ml.features.lag_features import (
    LAG_FEATURE_COLUMNS,
    ROLLING_MEAN_COLUMNS,
    ROLLING_STD_COLUMNS,
    add_lag_features,
    add_rolling_features,
)

WEATHER_FEATURE_COLUMNS = [
    "temperature_c",
    "humidity_percent",
    "temperature_squared",
    "cooling_degree_proxy",
    "heating_degree_proxy",
]

FULL_FEATURE_COLUMNS = (
    CALENDAR_FEATURE_COLUMNS + LAG_FEATURE_COLUMNS + ROLLING_MEAN_COLUMNS + ROLLING_STD_COLUMNS + WEATHER_FEATURE_COLUMNS
)

# Linear model uses a smaller, less collinear subset.
LINEAR_FEATURE_COLUMNS = (
    CALENDAR_FEATURE_COLUMNS
    + ["load_lag_1", "load_lag_24", "load_lag_168"]
    + ["rolling_mean_24", "rolling_mean_168"]
    + WEATHER_FEATURE_COLUMNS
)


def add_weather_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["temperature_squared"] = df["temperature_c"] ** 2
    df["cooling_degree_proxy"] = (df["temperature_c"] - 22.0).clip(lower=0)
    df["heating_degree_proxy"] = (10.0 - df["temperature_c"]).clip(lower=0)
    return df


def build_feature_frame(df: pd.DataFrame, country: str = "US") -> pd.DataFrame:
    """Build the full feature set on a dataframe with columns
    ``timestamp``, ``load_mw``, ``temperature_c``, ``humidity_percent``.

    Rows sorted ascending by timestamp are required for lag/rolling
    correctness. Rows with insufficient history for a given feature will
    contain NaNs, which callers should drop before training.
    """
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = add_calendar_features(df, country=country)
    df = add_lag_features(df)
    df = add_rolling_features(df)
    df = add_weather_derived_features(df)
    return df
