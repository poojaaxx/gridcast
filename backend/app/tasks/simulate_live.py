"""Simulated live production pipeline.

Advances "simulated time" one hour at a time: inserts a new hourly actual
observation, issues fresh forecasts anchored at the new present, and scores
any previously-issued forecasts whose target timestamp just became
observable. This is what makes the "continuous evaluation" story tangible in
a demo without waiting for real wall-clock hours to pass.

    python -m app.tasks.simulate_live --region demo-region --hours 72
"""
from __future__ import annotations

import argparse
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import session_scope
from app.ingestion.pipeline import fetch_load, fetch_weather, upsert_load_observations, upsert_weather_observations
from app.models.load_observation import LoadObservation
from app.models.model_version import ModelVersion
from app.models.region import Region
from app.services import evaluation_service
from app.services.forecasting_service import generate_forecast, get_latest_model_version
from app.services.region_service import get_region_by_name

logger = get_logger(__name__)

FORECAST_HORIZONS = (24, 48)


def _last_observed_timestamp(db: Session, region_id: int) -> dt.datetime:
    ts = db.execute(
        select(LoadObservation.timestamp).where(LoadObservation.region_id == region_id).order_by(LoadObservation.timestamp.desc()).limit(1)
    ).scalar_one_or_none()
    if ts is None:
        raise ValueError("Region has no load history to simulate forward from. Run ingestion first.")
    return ts


def advance_one_hour(db: Session, region: Region) -> dict:
    last_ts = _last_observed_timestamp(db, region.id)
    next_ts = last_ts + dt.timedelta(hours=1)
    window_end = next_ts + dt.timedelta(hours=1)

    weather_records, weather_source = fetch_weather(region.latitude, region.longitude, next_ts, window_end)
    upsert_weather_observations(db, region.id, weather_records)

    load_records, load_source = fetch_load(region.latitude, region.longitude, next_ts, window_end, weather_records)
    load_inserted, _ = upsert_load_observations(db, region.id, load_records)
    db.commit()

    model_types = db.execute(select(ModelVersion.model_type).distinct()).scalars().all()
    forecasts_generated = 0
    for model_type in model_types:
        version = get_latest_model_version(db, model_type=model_type)
        if version is None:
            continue
        for horizon in FORECAST_HORIZONS:
            forecasts = generate_forecast(db, region, version, horizon)
            forecasts_generated += len(forecasts)

    score_result = evaluation_service.score_forecasts(db, region_id=region.id)

    return {
        "timestamp": next_ts.isoformat(),
        "load_inserted": load_inserted,
        "forecasts_generated": forecasts_generated,
        "scored": score_result["scored"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate N hours of live production operation.")
    parser.add_argument("--region", required=True)
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    with session_scope() as db:
        region = get_region_by_name(db, args.region)
        if region is None:
            raise SystemExit(f"Region '{args.region}' not found.")

        total_scored = 0
        for i in range(args.hours):
            step = advance_one_hour(db, region)
            total_scored += step["scored"]
            if (i + 1) % 12 == 0 or (i + 1) == args.hours:
                logger.info(
                    "[%d/%d] simulated hour=%s forecasts_generated=%d scored=%d",
                    i + 1, args.hours, step["timestamp"], step["forecasts_generated"], step["scored"],
                )

        logger.info("Simulation complete: %d hours advanced, %d forecasts scored total.", args.hours, total_scored)


if __name__ == "__main__":
    main()
