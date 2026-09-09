"""Forecast scoring and performance-monitoring aggregations.

Scoring
-------
A forecast is "scored" once an actual load observation exists for its
target_timestamp. Scoring is idempotent: the ``uq_forecast_score_forecast_id``
constraint (and an explicit anti-join on already-scored forecast ids)
guarantees a forecast is never scored twice.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.forecast import Forecast
from app.models.forecast_score import ForecastScore
from app.models.load_observation import LoadObservation
from app.models.model_version import ModelVersion
from app.utils.time import utcnow

logger = get_logger(__name__)

EPSILON = 1.0


def score_forecasts(db: Session, region_id: int | None = None) -> dict:
    already_scored = select(ForecastScore.forecast_id)

    stmt = (
        select(Forecast, LoadObservation.load_mw)
        .join(
            LoadObservation,
            and_(
                LoadObservation.region_id == Forecast.region_id,
                LoadObservation.timestamp == Forecast.target_timestamp,
            ),
        )
        .where(Forecast.id.notin_(already_scored))
    )
    if region_id is not None:
        stmt = stmt.where(Forecast.region_id == region_id)

    rows = db.execute(stmt).all()

    new_scores = []
    for forecast, actual_load_mw in rows:
        error = actual_load_mw - forecast.predicted_load_mw
        absolute_error = abs(error)
        squared_error = error ** 2
        absolute_percentage_error = absolute_error / max(abs(actual_load_mw), EPSILON)
        new_scores.append(
            {
                "forecast_id": forecast.id,
                "actual_load_mw": actual_load_mw,
                "absolute_error": absolute_error,
                "squared_error": squared_error,
                "absolute_percentage_error": absolute_percentage_error,
            }
        )

    if new_scores:
        insert_stmt = pg_insert(ForecastScore).values(new_scores)
        insert_stmt = insert_stmt.on_conflict_do_nothing(constraint="uq_forecast_score_forecast_id")
        db.execute(insert_stmt)
        db.commit()

    logger.info("Scored %d new forecasts (region_id=%s)", len(new_scores), region_id)
    return {"scored": len(new_scores)}


def _smape_fraction_expr():
    actual = ForecastScore.actual_load_mw
    predicted = Forecast.predicted_load_mw
    denom = func.greatest((func.abs(actual) + func.abs(predicted)) / 2.0, EPSILON)
    return func.abs(actual - predicted) / denom


def get_model_performance_summary(db: Session, region_id: int | None = None) -> list[dict]:
    stmt = (
        select(
            ModelVersion.model_type,
            func.count(ForecastScore.id).label("forecast_count"),
            func.avg(ForecastScore.absolute_error).label("mae"),
            func.avg(ForecastScore.squared_error).label("mean_squared_error"),
            func.avg(ForecastScore.absolute_percentage_error).label("mape_fraction"),
            func.avg(_smape_fraction_expr()).label("smape_fraction"),
        )
        .join(Forecast, Forecast.model_version_id == ModelVersion.id)
        .join(ForecastScore, ForecastScore.forecast_id == Forecast.id)
        .group_by(ModelVersion.model_type)
    )
    if region_id is not None:
        stmt = stmt.where(Forecast.region_id == region_id)

    results = []
    for model_type, count, mae, mse, mape_fraction, smape_fraction in db.execute(stmt).all():
        results.append(
            {
                "model_type": model_type,
                "forecast_count": count,
                "mae": round(float(mae or 0), 3),
                "rmse": round(float((mse or 0) ** 0.5), 3),
                "mape": round(float((mape_fraction or 0) * 100), 3),
                "smape": round(float((smape_fraction or 0) * 100), 3),
            }
        )
    return results


def get_model_comparison(db: Session, region_id: int | None = None) -> dict:
    summary = get_model_performance_summary(db, region_id=region_id)
    best = min(summary, key=lambda r: r["mape"]) if summary else None
    return {
        "models": summary,
        "best_model": best["model_type"] if best else None,
    }


def get_performance_timeseries(db: Session, region_id: int | None = None, granularity: str = "day") -> list[dict]:
    trunc_unit = "week" if granularity == "week" else "day"
    period = func.date_trunc(trunc_unit, Forecast.target_timestamp).label("period")

    stmt = (
        select(
            period,
            ModelVersion.model_type,
            func.count(ForecastScore.id).label("forecast_count"),
            func.avg(ForecastScore.absolute_error).label("mae"),
            func.avg(ForecastScore.squared_error).label("mean_squared_error"),
            func.avg(ForecastScore.absolute_percentage_error).label("mape_fraction"),
            func.avg(_smape_fraction_expr()).label("smape_fraction"),
        )
        .join(Forecast, Forecast.model_version_id == ModelVersion.id)
        .join(ForecastScore, ForecastScore.forecast_id == Forecast.id)
        .group_by(period, ModelVersion.model_type)
        .order_by(period)
    )
    if region_id is not None:
        stmt = stmt.where(Forecast.region_id == region_id)

    return [
        {
            "period": period_val.isoformat(),
            "model_type": model_type,
            "forecast_count": count,
            "mae": round(float(mae or 0), 3),
            "rmse": round(float((mse or 0) ** 0.5), 3),
            "mape": round(float((mape_fraction or 0) * 100), 3),
            "smape": round(float((smape_fraction or 0) * 100), 3),
        }
        for period_val, model_type, count, mae, mse, mape_fraction, smape_fraction in db.execute(stmt).all()
    ]


def get_drift_status(
    db: Session,
    region_id: int | None = None,
    model_type: str | None = None,
    recent_days: int = 7,
    baseline_days: int = 30,
    threshold_pct: float | None = None,
) -> dict:
    threshold_pct = threshold_pct if threshold_pct is not None else settings.drift_mape_degradation_threshold_pct
    now = utcnow()
    recent_start = now - dt.timedelta(days=recent_days)
    baseline_start = recent_start - dt.timedelta(days=baseline_days)

    def _mape_for_window(start: dt.datetime, end: dt.datetime) -> tuple[float | None, int]:
        stmt = (
            select(
                func.avg(ForecastScore.absolute_percentage_error).label("mape_fraction"),
                func.count(ForecastScore.id),
            )
            .join(Forecast, Forecast.id == ForecastScore.forecast_id)
            .join(ModelVersion, ModelVersion.id == Forecast.model_version_id)
            .where(Forecast.target_timestamp >= start, Forecast.target_timestamp < end)
        )
        if region_id is not None:
            stmt = stmt.where(Forecast.region_id == region_id)
        if model_type is not None:
            stmt = stmt.where(ModelVersion.model_type == model_type)

        mape_fraction, count = db.execute(stmt).one()
        if mape_fraction is None:
            return None, count or 0
        return float(mape_fraction) * 100, count

    recent_mape, recent_count = _mape_for_window(recent_start, now)
    baseline_mape, baseline_count = _mape_for_window(baseline_start, recent_start)

    if recent_mape is None or baseline_mape is None or baseline_mape == 0:
        return {
            "status": "insufficient_data",
            "recent_mape": recent_mape,
            "baseline_mape": baseline_mape,
            "change_percent": None,
            "recent_count": recent_count,
            "baseline_count": baseline_count,
            "threshold_pct": threshold_pct,
        }

    change_percent = ((recent_mape - baseline_mape) / baseline_mape) * 100
    status = "degraded" if change_percent > threshold_pct else "healthy"

    return {
        "status": status,
        "recent_mape": round(recent_mape, 3),
        "baseline_mape": round(baseline_mape, 3),
        "change_percent": round(change_percent, 3),
        "recent_count": recent_count,
        "baseline_count": baseline_count,
        "threshold_pct": threshold_pct,
    }
