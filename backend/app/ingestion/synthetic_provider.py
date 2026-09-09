"""Realistic synthetic electricity load generator.

Used whenever a real electricity load API is unavailable or unconfigured, so
the full pipeline (ingestion -> features -> training -> forecasting ->
evaluation -> dashboard) always remains demoable.

The signal is a deterministic (seeded) composition of:
    base_load + hourly_seasonality + weekday/weekend effect
    + temperature_effect + long_term_trend + random_noise

It intentionally reuses the *actual* weather observations (real or
synthetic) for the region/time range so temperature sensitivity is
consistent with whatever the weather provider returns.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np

from app.ingestion.base import LoadRecord, WeatherRecord


class SyntheticElectricityProvider:
    """Generates a physically-plausible hourly load series.

    Deterministic given the same (latitude, longitude, start, end, seed):
    the same synthetic history is reproduced across ingestion re-runs.
    """

    name = "synthetic"

    def __init__(self, seed: int = 42, base_load_mw: float = 4200.0):
        self.seed = seed
        self.base_load_mw = base_load_mw

    def fetch_load(
        self,
        *,
        latitude: float,
        longitude: float,
        start: dt.datetime,
        end: dt.datetime,
        weather: list[WeatherRecord] | None = None,
    ) -> list[LoadRecord]:
        hours = int((end - start).total_seconds() // 3600)
        timestamps = [start + dt.timedelta(hours=i) for i in range(hours)]
        temps_by_ts = {w.timestamp: w.temperature_c for w in (weather or [])}

        records: list[LoadRecord] = []
        for i, ts in enumerate(timestamps):
            rng = np.random.default_rng(self._seed_for(ts))
            temperature_c = temps_by_ts.get(ts, self._fallback_temperature(ts))
            load = self._simulate_load(ts, i, temperature_c, rng)
            records.append(LoadRecord(timestamp=ts, load_mw=load, source=self.name))
        return records

    def _seed_for(self, ts: dt.datetime) -> int:
        # Deterministic per-timestamp seed derived from the global seed.
        return (self.seed * 1_000_003 + int(ts.timestamp())) % (2**32 - 1)

    def _fallback_temperature(self, ts: dt.datetime) -> float:
        """Simple seasonal temperature curve used only if no weather is supplied."""
        day_of_year = ts.timetuple().tm_yday
        seasonal = 14 * math.sin(2 * math.pi * (day_of_year - 100) / 365.0)
        daily = 4 * math.sin(2 * math.pi * (ts.hour - 9) / 24.0)
        return 15.0 + seasonal + daily

    def _simulate_load(self, ts: dt.datetime, index: int, temperature_c: float, rng: np.random.Generator) -> float:
        hour = ts.hour
        weekday = ts.weekday()  # 0 = Monday
        is_weekend = weekday >= 5

        # --- Hourly seasonality: two humps (morning ramp + evening peak) ---
        morning = 0.55 * math.exp(-((hour - 8.5) ** 2) / (2 * 2.6**2))
        evening = 1.0 * math.exp(-((hour - 19.5) ** 2) / (2 * 2.4**2))
        overnight_dip = -0.35 * math.exp(-((hour - 3.5) ** 2) / (2 * 2.0**2))
        midday_plateau = 0.30 * math.exp(-((hour - 13) ** 2) / (2 * 4.0**2))
        hourly_seasonality = self.base_load_mw * (morning + evening + midday_plateau + overnight_dip)

        # --- Weekday/weekend effect ---
        if is_weekend:
            weekend_effect = -0.12 * self.base_load_mw
        else:
            weekend_effect = 0.03 * self.base_load_mw

        # --- Temperature sensitivity (cooling above 22C, heating below 10C) ---
        cooling_degree = max(0.0, temperature_c - 22.0)
        heating_degree = max(0.0, 10.0 - temperature_c)
        temperature_effect = 18.0 * cooling_degree + 12.0 * heating_degree

        # --- Long-term trend: slow demand growth over the series ---
        trend = 0.015 * self.base_load_mw * (index / (24 * 365))

        # --- Slow seasonal (annual) effect on top of temperature ---
        day_of_year = ts.timetuple().tm_yday
        seasonal_effect = 0.05 * self.base_load_mw * math.sin(2 * math.pi * (day_of_year - 200) / 365.0)

        # --- Noise ---
        noise = rng.normal(loc=0.0, scale=0.018 * self.base_load_mw)

        load = (
            self.base_load_mw
            + hourly_seasonality
            + weekend_effect
            + temperature_effect
            + trend
            + seasonal_effect
            + noise
        )
        return max(load, 0.05 * self.base_load_mw)


class SyntheticWeatherProvider:
    """Deterministic synthetic weather generator used as a fallback when
    the Open-Meteo API is unreachable.
    """

    name = "synthetic"

    def __init__(self, seed: int = 42):
        self.seed = seed

    def fetch_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        start: dt.datetime,
        end: dt.datetime,
    ) -> list[WeatherRecord]:
        hours = int((end - start).total_seconds() // 3600)
        timestamps = [start + dt.timedelta(hours=i) for i in range(hours)]
        records: list[WeatherRecord] = []
        for ts in timestamps:
            rng = np.random.default_rng((self.seed * 7_919 + int(ts.timestamp())) % (2**32 - 1))
            day_of_year = ts.timetuple().tm_yday
            seasonal = 14 * math.sin(2 * math.pi * (day_of_year - 100) / 365.0)
            daily = 4 * math.sin(2 * math.pi * (ts.hour - 9) / 24.0)
            temperature_c = 15.0 + seasonal + daily + rng.normal(0, 1.2)
            humidity = float(np.clip(60 + 15 * math.sin(2 * math.pi * ts.hour / 24.0) + rng.normal(0, 5), 10, 100))
            precipitation = max(0.0, rng.normal(0.05, 0.3)) if rng.random() < 0.15 else 0.0
            weather_code = 61 if precipitation > 0 else 0
            records.append(
                WeatherRecord(
                    timestamp=ts,
                    temperature_c=round(float(temperature_c), 2),
                    humidity_percent=round(humidity, 2),
                    precipitation=round(float(precipitation), 2),
                    weather_code=weather_code,
                )
            )
        return records
