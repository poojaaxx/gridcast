from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class RegionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    country: str = Field(..., min_length=1, max_length=64)
    timezone: str = Field(..., min_length=1, max_length=64)
    latitude: float
    longitude: float


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
    timezone: str
    latitude: float
    longitude: float
    created_at: dt.datetime
