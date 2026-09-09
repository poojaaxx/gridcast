from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    username: str
    action: str
    status: str
    detail: dict[str, Any] | None
    created_at: dt.datetime


class SystemStatus(BaseModel):
    backend_status: str
    database_status: str
    environment: str
    data_mode: str
    electricity_provider: str
    live_region: str
    demo_region: str
    current_admin: str
    last_ingestion_at: dt.datetime | None
    last_forecast_generated_at: dt.datetime | None
    last_evaluation_scored_at: dt.datetime | None
    last_pipeline_cycle_at: dt.datetime | None
    last_pipeline_cycle_status: str | None
