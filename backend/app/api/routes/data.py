from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import resolve_region
from app.db.session import get_db
from app.ingestion.pipeline import run_ingestion
from app.models.load_observation import LoadObservation
from app.models.weather_observation import WeatherObservation
from app.schemas.data import LoadObservationOut, WeatherObservationOut
from app.utils.time import utcnow

router = APIRouter(prefix="/data", tags=["data"])


class IngestRequest(BaseModel):
    region: str = Field(..., description="Region name; created automatically if it doesn't exist")
    days: int = Field(default=180, ge=1, le=730)


class IngestResponse(BaseModel):
    region: str
    region_id: int
    weather_source: str
    weather_inserted: int
    weather_skipped: int
    load_source: str
    load_inserted: int
    load_skipped: int


@router.post("/ingest", response_model=IngestResponse)
def post_ingest(payload: IngestRequest) -> IngestResponse:
    """Populate a region with historical load + weather data. Uses the
    real electricity/weather providers when configured and reachable,
    automatically falling back to the deterministic synthetic generator
    otherwise - this is what powers the dashboard's "Generate Demo Data"
    action when the database is empty.
    """
    end = utcnow()
    start = end - dt.timedelta(days=payload.days)
    result = run_ingestion(payload.region, start, end)
    return IngestResponse(**result)


@router.get("/load", response_model=list[LoadObservationOut])
def get_load_data(
    region: str,
    start: dt.datetime | None = Query(default=None),
    end: dt.datetime | None = Query(default=None),
    limit: int = Query(default=5000, le=20000),
    db: Session = Depends(get_db),
) -> list[LoadObservationOut]:
    region_obj = resolve_region(db, region)
    stmt = select(LoadObservation).where(LoadObservation.region_id == region_obj.id)
    if start is not None:
        stmt = stmt.where(LoadObservation.timestamp >= start)
    if end is not None:
        stmt = stmt.where(LoadObservation.timestamp < end)
    stmt = stmt.order_by(LoadObservation.timestamp).limit(limit)
    return list(db.execute(stmt).scalars())


@router.get("/weather", response_model=list[WeatherObservationOut])
def get_weather_data(
    region: str,
    start: dt.datetime | None = Query(default=None),
    end: dt.datetime | None = Query(default=None),
    limit: int = Query(default=5000, le=20000),
    db: Session = Depends(get_db),
) -> list[WeatherObservationOut]:
    region_obj = resolve_region(db, region)
    stmt = select(WeatherObservation).where(WeatherObservation.region_id == region_obj.id)
    if start is not None:
        stmt = stmt.where(WeatherObservation.timestamp >= start)
    if end is not None:
        stmt = stmt.where(WeatherObservation.timestamp < end)
    stmt = stmt.order_by(WeatherObservation.timestamp).limit(limit)
    return list(db.execute(stmt).scalars())
