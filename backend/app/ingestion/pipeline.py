"""Idempotent ingestion pipeline.

Fetches electricity load + weather data for a region and upserts it into
PostgreSQL. Safe to re-run: existing (region_id, timestamp) rows are never
duplicated thanks to the unique constraints on ``load_observations`` and
``weather_observations``.

CLI usage:
    python -m app.ingestion.pipeline --region demo-region --days 90
"""
from __future__ import annotations

import argparse
import datetime as dt

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.ingestion.base import LoadRecord, WeatherRecord
from app.ingestion.electricity_provider import RealElectricityProvider
from app.ingestion.synthetic_provider import SyntheticElectricityProvider, SyntheticWeatherProvider
from app.ingestion.weather_provider import OpenMeteoWeatherProvider
from app.models.load_observation import LoadObservation
from app.models.region import Region
from app.models.weather_observation import WeatherObservation
from app.utils.time import ensure_utc, floor_to_hour, utcnow

logger = get_logger(__name__)


def get_or_create_region(db: Session, name: str) -> Region:
    region = db.execute(select(Region).where(Region.name == name)).scalar_one_or_none()
    if region is not None:
        return region

    if name == settings.demo_region_slug:
        region = Region(
            name=settings.demo_region_slug,
            country=settings.demo_region_country,
            timezone=settings.demo_region_timezone,
            latitude=settings.demo_region_latitude,
            longitude=settings.demo_region_longitude,
        )
    else:
        region = Region(
            name=name,
            country="US",
            timezone="UTC",
            latitude=settings.demo_region_latitude,
            longitude=settings.demo_region_longitude,
        )
    db.add(region)
    db.flush()
    logger.info("Created new region '%s' (id=%s)", region.name, region.id)
    return region


def fetch_weather(latitude: float, longitude: float, start: dt.datetime, end: dt.datetime) -> tuple[list[WeatherRecord], str]:
    try:
        provider = OpenMeteoWeatherProvider()
        records = provider.fetch_weather(latitude=latitude, longitude=longitude, start=start, end=end)
        if records:
            return records, provider.name
        logger.warning("Open-Meteo returned no data; falling back to synthetic weather.")
    except Exception as exc:  # noqa: BLE001 - any upstream failure triggers fallback
        logger.warning("Weather provider failed (%s); falling back to synthetic weather.", exc)

    provider = SyntheticWeatherProvider(seed=settings.random_seed)
    return provider.fetch_weather(latitude=latitude, longitude=longitude, start=start, end=end), provider.name


def fetch_load(
    latitude: float,
    longitude: float,
    start: dt.datetime,
    end: dt.datetime,
    weather: list[WeatherRecord],
) -> tuple[list[LoadRecord], str]:
    if settings.electricity_provider == "real" and settings.eia_api_key:
        try:
            provider = RealElectricityProvider()
            records = provider.fetch_load(latitude=latitude, longitude=longitude, start=start, end=end)
            if records:
                return records, provider.name
            logger.warning("Real electricity provider returned no data; falling back to synthetic.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Real electricity provider failed (%s); falling back to synthetic.", exc)

    provider = SyntheticElectricityProvider(seed=settings.random_seed)
    records = provider.fetch_load(latitude=latitude, longitude=longitude, start=start, end=end, weather=weather)
    return records, provider.name


def upsert_load_observations(db: Session, region_id: int, records: list[LoadRecord]) -> tuple[int, int]:
    if not records:
        return 0, 0

    existing = set(
        db.execute(
            select(LoadObservation.timestamp).where(LoadObservation.region_id == region_id)
        ).scalars()
    )
    to_insert = [r for r in records if ensure_utc(r.timestamp) not in existing]
    skipped = len(records) - len(to_insert)

    if to_insert:
        stmt = pg_insert(LoadObservation).values(
            [
                {
                    "region_id": region_id,
                    "timestamp": ensure_utc(r.timestamp),
                    "load_mw": r.load_mw,
                    "source": r.source,
                }
                for r in to_insert
            ]
        )
        stmt = stmt.on_conflict_do_nothing(constraint="uq_load_region_timestamp")
        db.execute(stmt)

    return len(to_insert), skipped


def upsert_weather_observations(db: Session, region_id: int, records: list[WeatherRecord]) -> tuple[int, int]:
    if not records:
        return 0, 0

    existing = set(
        db.execute(
            select(WeatherObservation.timestamp).where(WeatherObservation.region_id == region_id)
        ).scalars()
    )
    to_insert = [r for r in records if ensure_utc(r.timestamp) not in existing]
    skipped = len(records) - len(to_insert)

    if to_insert:
        stmt = pg_insert(WeatherObservation).values(
            [
                {
                    "region_id": region_id,
                    "timestamp": ensure_utc(r.timestamp),
                    "temperature_c": r.temperature_c,
                    "humidity_percent": r.humidity_percent,
                    "precipitation": r.precipitation,
                    "weather_code": r.weather_code,
                }
                for r in to_insert
            ]
        )
        stmt = stmt.on_conflict_do_nothing(constraint="uq_weather_region_timestamp")
        db.execute(stmt)

    return len(to_insert), skipped


def run_ingestion(region_name: str, start: dt.datetime, end: dt.datetime) -> dict:
    start, end = floor_to_hour(ensure_utc(start)), floor_to_hour(ensure_utc(end))

    with session_scope() as db:
        region = get_or_create_region(db, region_name)

        weather_records, weather_source = fetch_weather(region.latitude, region.longitude, start, end)
        weather_inserted, weather_skipped = upsert_weather_observations(db, region.id, weather_records)
        logger.info(
            "Weather [%s]: inserted %d new records, skipped %d existing",
            weather_source, weather_inserted, weather_skipped,
        )

        load_records, load_source = fetch_load(region.latitude, region.longitude, start, end, weather_records)
        load_inserted, load_skipped = upsert_load_observations(db, region.id, load_records)
        logger.info(
            "Load [%s]: ingested %d records total, inserted %d new, skipped %d existing",
            load_source, len(load_records), load_inserted, load_skipped,
        )

        return {
            "region": region.name,
            "region_id": region.id,
            "weather_source": weather_source,
            "weather_inserted": weather_inserted,
            "weather_skipped": weather_skipped,
            "load_source": load_source,
            "load_inserted": load_inserted,
            "load_skipped": load_skipped,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest electricity + weather data for a region.")
    parser.add_argument("--region", required=True, help="Region name/slug, e.g. demo-region")
    parser.add_argument("--days", type=int, default=90, help="Number of trailing days to ingest")
    parser.add_argument("--end", type=str, default=None, help="ISO end timestamp (UTC). Defaults to now.")
    args = parser.parse_args()

    end = dt.datetime.fromisoformat(args.end) if args.end else utcnow()
    start = end - dt.timedelta(days=args.days)

    result = run_ingestion(args.region, start, end)
    logger.info("Ingestion complete: %s", result)


if __name__ == "__main__":
    main()
