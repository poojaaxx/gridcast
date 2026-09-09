from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrainModelRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    region: str = Field(..., description="Region name, e.g. demo-region")
    model_type: str = Field(..., description="One of: seasonal_naive, linear_regression, lightgbm")


class ModelVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_name: str
    version: str
    model_type: str
    training_start: dt.datetime
    training_end: dt.datetime
    metrics_json: dict[str, Any]
    artifact_path: str | None
    feature_columns: list[str]
    created_at: dt.datetime
