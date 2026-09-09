"""Calendar/holiday feature construction.

All features are computed from the (UTC) timestamp column and are safe to
compute for any timestamp, including future ones used during recursive
forecasting - they never depend on the target variable.
"""
from __future__ import annotations

import holidays
import numpy as np
import pandas as pd

CALENDAR_FEATURE_COLUMNS = [
    "hour",
    "day_of_week",
    "day_of_month",
    "month",
    "week_of_year",
    "is_weekend",
    "is_holiday",
    "hour_sin",
    "hour_cos",
    "day_of_week_sin",
    "day_of_week_cos",
]


def add_calendar_features(df: pd.DataFrame, timestamp_col: str = "timestamp", country: str = "US") -> pd.DataFrame:
    df = df.copy()
    ts = pd.to_datetime(df[timestamp_col])

    df["hour"] = ts.dt.hour
    df["day_of_week"] = ts.dt.dayofweek
    df["day_of_month"] = ts.dt.day
    df["month"] = ts.dt.month
    df["week_of_year"] = ts.dt.isocalendar().week.astype(int)
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    years = sorted(ts.dt.year.unique().tolist())
    country_holidays = holidays.country_holidays(country, years=years)
    df["is_holiday"] = ts.dt.date.isin(country_holidays).astype(int)

    # Cyclical encodings so the model understands hour 23 is close to hour 0.
    df["hour_sin"] = np.sin(df["hour"] * (2 * np.pi / 24))
    df["hour_cos"] = np.cos(df["hour"] * (2 * np.pi / 24))
    df["day_of_week_sin"] = np.sin(df["day_of_week"] * (2 * np.pi / 7))
    df["day_of_week_cos"] = np.cos(df["day_of_week"] * (2 * np.pi / 7))

    return df
