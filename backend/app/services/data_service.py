"""Shared helpers for loading joined load+weather history out of Postgres
into pandas, used by both the training and forecasting services.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.load_observation import LoadObservation
from app.models.weather_observation import WeatherObservation


def load_history_frame(
    db: Session,
    region_id: int,
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
) -> pd.DataFrame:
    """Return a dataframe with columns [timestamp, load_mw, temperature_c,
    humidity_percent], inner-joined on timestamp, sorted ascending.
    Only timestamps present in *both* tables are included since features
    require weather at every observed load timestamp.
    """
    load_stmt = select(LoadObservation.timestamp, LoadObservation.load_mw).where(
        LoadObservation.region_id == region_id
    )
    weather_stmt = select(
        WeatherObservation.timestamp, WeatherObservation.temperature_c, WeatherObservation.humidity_percent
    ).where(WeatherObservation.region_id == region_id)

    if start is not None:
        load_stmt = load_stmt.where(LoadObservation.timestamp >= start)
        weather_stmt = weather_stmt.where(WeatherObservation.timestamp >= start)
    if end is not None:
        load_stmt = load_stmt.where(LoadObservation.timestamp < end)
        weather_stmt = weather_stmt.where(WeatherObservation.timestamp < end)

    load_df = pd.DataFrame(db.execute(load_stmt).all(), columns=["timestamp", "load_mw"])
    weather_df = pd.DataFrame(
        db.execute(weather_stmt).all(), columns=["timestamp", "temperature_c", "humidity_percent"]
    )

    if load_df.empty or weather_df.empty:
        return pd.DataFrame(columns=["timestamp", "load_mw", "temperature_c", "humidity_percent"])

    merged = pd.merge(load_df, weather_df, on="timestamp", how="inner")
    merged = merged.sort_values("timestamp").drop_duplicates(subset="timestamp").reset_index(drop=True)
    return merged
