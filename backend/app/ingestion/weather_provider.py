"""Open-Meteo weather provider.

Open-Meteo requires no API key for non-commercial use, so this is used as the
default weather source. If it is unreachable, callers fall back to
``SyntheticWeatherProvider`` (see ``app.ingestion.pipeline``).
"""
from __future__ import annotations

import datetime as dt

import requests

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.base import WeatherRecord

logger = get_logger(__name__)


class OpenMeteoWeatherProvider:
    name = "open-meteo"

    def __init__(self, base_url: str | None = None, archive_url: str | None = None):
        self.base_url = base_url or settings.open_meteo_base_url
        self.archive_url = archive_url or settings.open_meteo_archive_url

    def fetch_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        start: dt.datetime,
        end: dt.datetime,
    ) -> list[WeatherRecord]:
        now = dt.datetime.now(dt.timezone.utc)
        # Open-Meteo's forecast endpoint only covers recent past + future;
        # anything older must go through the archive endpoint.
        if start < now - dt.timedelta(days=5):
            url = self.archive_url
        else:
            url = self.base_url

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start.date().isoformat(),
            "end_date": (end - dt.timedelta(hours=1)).date().isoformat(),
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
            "timezone": "UTC",
        }
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Open-Meteo request failed: %s", exc)
            raise

        payload = response.json()
        hourly = payload.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        humidity = hourly.get("relative_humidity_2m", [])
        precipitation = hourly.get("precipitation", [])
        weather_codes = hourly.get("weather_code", [])

        records: list[WeatherRecord] = []
        for i, time_str in enumerate(times):
            ts = dt.datetime.fromisoformat(time_str).replace(tzinfo=dt.timezone.utc)
            if not (start <= ts < end):
                continue
            records.append(
                WeatherRecord(
                    timestamp=ts,
                    temperature_c=float(temps[i]) if i < len(temps) else 0.0,
                    humidity_percent=float(humidity[i]) if i < len(humidity) else 0.0,
                    precipitation=float(precipitation[i]) if i < len(precipitation) else 0.0,
                    weather_code=int(weather_codes[i]) if i < len(weather_codes) else 0,
                )
            )
        return records
