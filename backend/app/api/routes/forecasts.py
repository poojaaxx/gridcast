from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin, resolve_region
from app.db.session import get_db
from app.models.audit_log import AuditAction, AuditStatus
from app.models.forecast import Forecast
from app.models.model_version import ModelVersion
from app.models.user import User
from app.schemas.forecast import ForecastWithModelOut, GenerateForecastRequest, ForecastOut
from app.services.audit_service import log_action
from app.services.forecasting_service import generate_forecast, resolve_model_version

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.post("/generate", response_model=list[ForecastOut])
def post_generate_forecast(
    payload: GenerateForecastRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ForecastOut]:
    region = resolve_region(db, payload.region)
    try:
        model_version = resolve_model_version(db, payload.model_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        forecasts = generate_forecast(db, region, model_version, payload.horizon_hours)
    except ValueError as exc:
        log_action(
            db, action=AuditAction.FORECAST_GENERATE.value, status=AuditStatus.FAILURE,
            user=current_user,
            detail={"region": payload.region, "model_version": payload.model_version, "horizon_hours": payload.horizon_hours, "error": str(exc)},
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    log_action(
        db, action=AuditAction.FORECAST_GENERATE.value, status=AuditStatus.SUCCESS,
        user=current_user,
        detail={"region": payload.region, "model_version": model_version.version, "horizon_hours": payload.horizon_hours, "count": len(forecasts)},
    )
    return forecasts


@router.get("/latest", response_model=list[ForecastWithModelOut])
def get_latest_forecasts(
    region: str,
    model_version: str = Query(default="latest"),
    db: Session = Depends(get_db),
) -> list[ForecastWithModelOut]:
    region_obj = resolve_region(db, region)
    try:
        version = resolve_model_version(db, model_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    latest_generated_at = db.execute(
        select(Forecast.generated_at)
        .where(Forecast.region_id == region_obj.id, Forecast.model_version_id == version.id)
        .order_by(Forecast.generated_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_generated_at is None:
        return []

    stmt = (
        select(Forecast, ModelVersion.model_type, ModelVersion.version)
        .join(ModelVersion, ModelVersion.id == Forecast.model_version_id)
        .where(
            Forecast.region_id == region_obj.id,
            Forecast.model_version_id == version.id,
            Forecast.generated_at == latest_generated_at,
        )
        .order_by(Forecast.target_timestamp)
    )
    return [
        ForecastWithModelOut(**forecast.__dict__, model_type=model_type, model_version=version_str)
        for forecast, model_type, version_str in db.execute(stmt).all()
    ]


@router.get("/history", response_model=list[ForecastWithModelOut])
def get_forecast_history(
    region: str,
    model_version: str | None = Query(default=None),
    start: dt.datetime | None = Query(default=None),
    end: dt.datetime | None = Query(default=None),
    limit: int = Query(default=2000, le=20000),
    db: Session = Depends(get_db),
) -> list[ForecastWithModelOut]:
    region_obj = resolve_region(db, region)

    stmt = (
        select(Forecast, ModelVersion.model_type, ModelVersion.version)
        .join(ModelVersion, ModelVersion.id == Forecast.model_version_id)
        .where(Forecast.region_id == region_obj.id)
    )
    if model_version:
        try:
            version = resolve_model_version(db, model_version)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        stmt = stmt.where(Forecast.model_version_id == version.id)
    if start is not None:
        stmt = stmt.where(Forecast.target_timestamp >= start)
    if end is not None:
        stmt = stmt.where(Forecast.target_timestamp < end)

    stmt = stmt.order_by(Forecast.target_timestamp).limit(limit)
    return [
        ForecastWithModelOut(**forecast.__dict__, model_type=model_type, model_version=version_str)
        for forecast, model_type, version_str in db.execute(stmt).all()
    ]
