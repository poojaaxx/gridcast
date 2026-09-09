"""Forecast generation: recursive multi-step forecasting with correct
handling of not-yet-observed lag values, plus persistence to Postgres.

Recursive forecasting
----------------------
To forecast hour t+2 we may need load(t+1) as a lag feature, but load(t+1)
has not been observed yet - only *predicted*. We therefore forecast one step
at a time, appending each prediction back into the working series before
computing features for the next step. Real actual data is never used for
timestamps beyond what has actually been observed; future weather comes
from the same provider-with-fallback used during ingestion.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ingestion.pipeline import fetch_weather
from app.ml.features.pipeline import build_feature_frame
from app.models.forecast import Forecast
from app.models.model_version import ModelVersion
from app.models.region import Region
from app.services.data_service import load_history_frame
from app.services.training_service import load_model_artifact
from app.utils.time import ensure_utc, floor_to_hour, utcnow

logger = get_logger(__name__)

HISTORY_WINDOW_HOURS = 24 * 24  # 24 days: comfortably covers 168h lag/rolling needs


def get_latest_model_version(db: Session, model_type: str | None = None) -> ModelVersion | None:
    stmt = select(ModelVersion)
    if model_type:
        stmt = stmt.where(ModelVersion.model_type == model_type)
    stmt = stmt.order_by(ModelVersion.created_at.desc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def resolve_model_version(db: Session, model_version: str) -> ModelVersion:
    if model_version == "latest":
        version = get_latest_model_version(db)
    else:
        version = db.execute(select(ModelVersion).where(ModelVersion.version == model_version)).scalar_one_or_none()
    if version is None:
        raise ValueError(f"Model version '{model_version}' not found.")
    return version


def generate_forecast(
    db: Session,
    region: Region,
    model_version: ModelVersion,
    horizon_hours: int,
) -> list[Forecast]:
    model = load_model_artifact(model_version)
    residual_std = float(model_version.metrics_json.get("residual_std", 0.0))

    history_df = load_history_frame(db, region.id)
    if history_df.empty:
        raise ValueError(f"No history available for region '{region.name}' to forecast from.")

    last_observed_ts = ensure_utc(history_df["timestamp"].max().to_pydatetime())
    forecast_start = last_observed_ts + dt.timedelta(hours=1)
    forecast_end = forecast_start + dt.timedelta(hours=horizon_hours)

    future_weather, weather_source = fetch_weather(region.latitude, region.longitude, forecast_start, forecast_end)
    weather_by_ts = {ensure_utc(w.timestamp): w for w in future_weather}

    working = history_df.tail(HISTORY_WINDOW_HOURS).reset_index(drop=True)
    generated_at = floor_to_hour(utcnow())

    predictions: list[tuple[dt.datetime, float, float, float]] = []
    target_ts = forecast_start
    for step in range(horizon_hours):
        weather = weather_by_ts.get(target_ts)
        if weather is None:
            logger.warning("No weather for %s; reusing last known weather values.", target_ts)
            temperature_c = working["temperature_c"].iloc[-1]
            humidity_percent = working["humidity_percent"].iloc[-1]
        else:
            temperature_c = weather.temperature_c
            humidity_percent = weather.humidity_percent

        new_row = pd.DataFrame(
            [{"timestamp": target_ts, "load_mw": np.nan, "temperature_c": temperature_c, "humidity_percent": humidity_percent}]
        )
        working = pd.concat([working, new_row], ignore_index=True)

        featured = build_feature_frame(working, country=region.country)
        last_row = featured.iloc[[-1]]
        predicted_value = float(model.predict(last_row[model.feature_columns])[0])

        working.loc[working.index[-1], "load_mw"] = predicted_value

        lower_bound = predicted_value - 1.96 * residual_std
        upper_bound = predicted_value + 1.96 * residual_std
        predictions.append((target_ts, predicted_value, lower_bound, upper_bound))

        target_ts = target_ts + dt.timedelta(hours=1)

    if predictions:
        stmt = pg_insert(Forecast).values(
            [
                {
                    "region_id": region.id,
                    "model_version_id": model_version.id,
                    "generated_at": generated_at,
                    "target_timestamp": ts,
                    "horizon_hours": i + 1,
                    "predicted_load_mw": pred,
                    "lower_bound": lower,
                    "upper_bound": upper,
                }
                for i, (ts, pred, lower, upper) in enumerate(predictions)
            ]
        )
        stmt = stmt.on_conflict_do_nothing(constraint="uq_forecast_identity")
        db.execute(stmt)
        db.commit()

    # Re-select rather than returning the transient values above: a Core
    # INSERT doesn't populate ORM attributes like `id`, and a conflicting
    # row (already forecast for this exact generated_at/target) should
    # surface the original persisted row, not a phantom in-memory one.
    target_timestamps = [ts for ts, _, _, _ in predictions]
    forecasts: list[Forecast] = []
    if target_timestamps:
        select_stmt = (
            select(Forecast)
            .where(
                Forecast.region_id == region.id,
                Forecast.model_version_id == model_version.id,
                Forecast.generated_at == generated_at,
                Forecast.target_timestamp.in_(target_timestamps),
            )
            .order_by(Forecast.target_timestamp)
        )
        forecasts = list(db.execute(select_stmt).scalars())

    logger.info(
        "Generated %d forecasts for region '%s' using model '%s' (horizon=%dh, weather_source=%s)",
        len(forecasts), region.name, model_version.version, horizon_hours, weather_source,
    )
    return forecasts
