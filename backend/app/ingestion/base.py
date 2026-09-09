"""Data provider abstraction.

GridCast must remain fully demoable even when no real electricity load API
is configured/reachable. All electricity providers implement the same
interface so the ingestion pipeline never needs to know which one is active.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LoadRecord:
    timestamp: dt.datetime
    load_mw: float
    source: str


@dataclass(frozen=True)
class WeatherRecord:
    timestamp: dt.datetime
    temperature_c: float
    humidity_percent: float
    precipitation: float
    weather_code: int


class ElectricityDataProvider(Protocol):
    """Interface every electricity load data source must implement."""

    name: str

    def fetch_load(
        self,
        *,
        latitude: float,
        longitude: float,
        start: dt.datetime,
        end: dt.datetime,
    ) -> list[LoadRecord]:
        """Return hourly load observations in [start, end) as UTC timestamps."""
        ...


class WeatherDataProvider(Protocol):
    """Interface every weather data source must implement."""

    name: str

    def fetch_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        start: dt.datetime,
        end: dt.datetime,
    ) -> list[WeatherRecord]:
        """Return hourly weather observations in [start, end) as UTC timestamps."""
        ...
