from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class GenerateForecastRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    region: str = Field(..., description="Region name, e.g. demo-region")
    model_version: str = Field(default="latest", description="Model version string or 'latest'")
    horizon_hours: int = Field(default=24, ge=1, le=168)


class ForecastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    region_id: int
    model_version_id: int
    generated_at: dt.datetime
    target_timestamp: dt.datetime
    horizon_hours: int
    predicted_load_mw: float
    lower_bound: float | None
    upper_bound: float | None


class ForecastWithModelOut(ForecastOut):
    model_type: str
    model_version: str
