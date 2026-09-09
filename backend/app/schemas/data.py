from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class LoadObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    region_id: int
    timestamp: dt.datetime
    load_mw: float
    source: str


class WeatherObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    region_id: int
    timestamp: dt.datetime
    temperature_c: float
    humidity_percent: float
    precipitation: float
    weather_code: int
