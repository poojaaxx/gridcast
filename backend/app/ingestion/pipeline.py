"""Idempotent ingestion pipeline.

Fetches electricity load + weather data for a region and upserts it into
PostgreSQL. Safe to re-run: existing (region_id, timestamp) rows are never
duplicated thanks to the unique constraints on ``load_observations`` and
``weather_observations``.

Live vs demo - no silent fallback
----------------------------------
When ``settings.electricity_provider == "real"`` (LIVE mode), a failing or
misconfigured EIA request is never masked by quietly substituting synthetic
data: ``fetch_load`` raises ``LiveProviderError`` instead. Synthetic load is
only ever used when the app is genuinely configured for DEMO mode. Weather
follows the same rule for its own real provider (Open-Meteo): in LIVE mode a
failure is surfaced as a degraded run (``weather_source="unavailable"``,
zero weather rows) rather than fabricated; in DEMO mode Open-Meteo is still
tried first (real weather colocated with synthetic load is more useful for
training than fully synthetic weather) and falls back to the synthetic
weather generator on failure, since the whole run is already synthetic.

CLI usage:
    python -m app.ingestion.pipeline --region demo-region --days 90
"""
from __future__ import annotations

import argparse
import datetime as dt
import time

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


class LiveProviderError(Exception):
    """Raised when LIVE mode's real provider fails. Callers must surface this
    as an error (audit FAILURE, HTTP 502, worker-cycle failure log) - it must
    never be caught-and-replaced with synthetic data."""


def is_live_mode() -> bool:
    return settings.electricity_provider == "real"


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
    elif name == settings.live_region_name:
        region = Region(
            name=settings.live_region_name,
            country=settings.live_region_country,
            timezone=settings.live_region_timezone,
            latitude=settings.live_region_latitude,
            longitude=settings.live_region_longitude,
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


def validate_load_records(records: list[LoadRecord]) -> tuple[list[LoadRecord], dict[str, int]]:
    """Real-world data quality gate for OBSERVED ACTUAL load records.

    Rejects (never repairs/invents a value for): missing timestamps,
    non-finite/negative load, and duplicate timestamps within the same batch
    (keeps the first occurrence). Rejected rows are counted, not silently
    dropped without a trace - counts are surfaced in the ingestion result.
    """
    seen: set[dt.datetime] = set()
    valid: list[LoadRecord] = []
    rejected = {"missing_timestamp": 0, "invalid_load": 0, "duplicate_timestamp": 0}

    for r in records:
        if r.timestamp is None:
            rejected["missing_timestamp"] += 1
            continue
        if r.load_mw is None or not _is_finite(r.load_mw) or r.load_mw < 0:
            rejected["invalid_load"] += 1
            continue
        ts = ensure_utc(r.timestamp)
        if ts in seen:
            rejected["duplicate_timestamp"] += 1
            continue
        seen.add(ts)
        valid.append(r)

    return valid, rejected


def validate_weather_records(records: list[WeatherRecord]) -> tuple[list[WeatherRecord], dict[str, int]]:
    seen: set[dt.datetime] = set()
    valid: list[WeatherRecord] = []
    rejected = {"missing_timestamp": 0, "invalid_reading": 0, "duplicate_timestamp": 0}

    for r in records:
        if r.timestamp is None:
            rejected["missing_timestamp"] += 1
            continue
        if r.temperature_c is None or not _is_finite(r.temperature_c) or not _is_finite(r.humidity_percent):
            rejected["invalid_reading"] += 1
            continue
        ts = ensure_utc(r.timestamp)
        if ts in seen:
            rejected["duplicate_timestamp"] += 1
            continue
        seen.add(ts)
        valid.append(r)

    return valid, rejected


def _is_finite(value: float) -> bool:
    try:
        return value == value and value not in (float("inf"), float("-inf"))  # noqa: PLR0124 - NaN check
    except TypeError:
        return False


def fetch_weather(latitude: float, longitude: float, start: dt.datetime, end: dt.datetime) -> tuple[list[WeatherRecord], str]:
    """Real weather (Open-Meteo) is tried first regardless of data_mode - it's
    free/keyless and genuinely improves even a DEMO run's temperature
    sensitivity. On failure: DEMO mode falls back to the synthetic weather
    generator (the whole run is already synthetic, so this is consistent,
    not deceptive). LIVE mode does NOT fabricate a replacement - it returns
    an empty list tagged "unavailable" so the caller can record a degraded
    (not fake) ingestion result.
    """
    try:
        provider = OpenMeteoWeatherProvider()
        records = provider.fetch_weather(latitude=latitude, longitude=longitude, start=start, end=end)
        if records:
            return records, provider.name
        logger.warning("Open-Meteo returned no data for the requested window.")
    except Exception as exc:  # noqa: BLE001 - any upstream failure is handled per data_mode below
        logger.warning("Weather provider failed: %s", exc)

    if is_live_mode():
        logger.error("LIVE mode: weather unavailable and will NOT be fabricated. Pipeline continues in a degraded state.")
        return [], "unavailable"

    provider = SyntheticWeatherProvider(seed=settings.random_seed)
    return provider.fetch_weather(latitude=latitude, longitude=longitude, start=start, end=end), provider.name


def fetch_load(
    latitude: float,
    longitude: float,
    start: dt.datetime,
    end: dt.datetime,
    weather: list[WeatherRecord],
) -> tuple[list[LoadRecord], str]:
    """DEMO mode always uses the synthetic generator - it never even attempts
    the real provider. LIVE mode ONLY ever uses the real EIA provider: a
    failure (missing key, HTTP error, empty response) raises
    ``LiveProviderError`` rather than silently substituting synthetic data
    labeled as live - this is a hard project requirement, not a
    best-effort preference.
    """
    if not is_live_mode():
        provider = SyntheticElectricityProvider(seed=settings.random_seed)
        records = provider.fetch_load(latitude=latitude, longitude=longitude, start=start, end=end, weather=weather)
        return records, provider.name

    try:
        provider = RealElectricityProvider()
        records = provider.fetch_load(latitude=latitude, longitude=longitude, start=start, end=end)
    except Exception as exc:  # noqa: BLE001 - re-raised as a typed, caller-visible failure
        raise LiveProviderError(f"LIVE electricity provider (EIA) failed: {exc}") from exc

    if not records:
        raise LiveProviderError(
            "LIVE electricity provider (EIA) returned no records for the requested window - "
            "not falling back to synthetic data."
        )
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
        valid_weather, weather_rejected = validate_weather_records(weather_records)
        weather_inserted, weather_skipped = upsert_weather_observations(db, region.id, valid_weather)
        # Committed independently of the load fetch below so a LIVE-mode
        # load failure can't roll back weather data that was genuinely
        # fetched successfully this run (see module docstring).
        db.commit()
        logger.info(
            "Weather [%s]: inserted %d new records, skipped %d existing, rejected %s",
            weather_source, weather_inserted, weather_skipped, weather_rejected,
        )

        load_records, load_source = fetch_load(region.latitude, region.longitude, start, end, valid_weather)
        valid_load, load_rejected = validate_load_records(load_records)
        load_inserted, load_skipped = upsert_load_observations(db, region.id, valid_load)
        logger.info(
            "Load [%s]: ingested %d records total, inserted %d new, skipped %d existing, rejected %s",
            load_source, len(load_records), load_inserted, load_skipped, load_rejected,
        )

        return {
            "region": region.name,
            "region_id": region.id,
            "data_mode": settings.data_mode,
            "degraded": weather_source == "unavailable",
            "weather_source": weather_source,
            "weather_inserted": weather_inserted,
            "weather_skipped": weather_skipped,
            "weather_rejected": weather_rejected,
            "load_source": load_source,
            "load_inserted": load_inserted,
            "load_skipped": load_skipped,
            "load_rejected": load_rejected,
        }


def backfill_historical(
    region_name: str,
    start: dt.datetime,
    end: dt.datetime,
    chunk_days: int = 200,
    pace_seconds: float = 2.0,
) -> list[dict]:
    """Controlled historical backfill, run in date-range chunks.

    Resumable and idempotent: each chunk goes through the exact same
    idempotent upsert path as ``run_ingestion``, so re-running this (e.g.
    after an interruption, or with a wider range) never creates duplicate
    rows. ``pace_seconds`` adds a delay between chunk requests to stay
    comfortably under the upstream provider's per-key rate limit.
    """
    start, end = floor_to_hour(ensure_utc(start)), floor_to_hour(ensure_utc(end))
    if end <= start:
        raise ValueError("Backfill end must be after start.")

    chunk_delta = dt.timedelta(days=chunk_days)
    total_hours = (end - start).total_seconds() / 3600
    total_chunks = max(1, -(-int(total_hours) // (chunk_days * 24)))

    results: list[dict] = []
    cursor = start
    chunk_index = 0
    while cursor < end:
        chunk_end = min(cursor + chunk_delta, end)
        chunk_index += 1
        logger.info(
            "Backfill chunk %d/%d for '%s': %s -> %s",
            chunk_index, total_chunks, region_name, cursor.isoformat(), chunk_end.isoformat(),
        )
        result = run_ingestion(region_name, cursor, chunk_end)
        result["chunk"] = chunk_index
        results.append(result)
        cursor = chunk_end
        if cursor < end and pace_seconds > 0:
            time.sleep(pace_seconds)

    return results


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
