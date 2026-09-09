from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ScoreRequest(BaseModel):
    region: str | None = None


class ScoreResponse(BaseModel):
    scored: int


class ModelPerformance(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_type: str
    forecast_count: int
    mae: float
    rmse: float
    mape: float
    smape: float


class ModelComparison(BaseModel):
    models: list[ModelPerformance]
    best_model: str | None


class PerformancePoint(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    period: str
    model_type: str
    forecast_count: int
    mae: float
    rmse: float
    mape: float
    smape: float


class DriftStatus(BaseModel):
    status: str
    recent_mape: float | None
    baseline_mape: float | None
    change_percent: float | None
    recent_count: int
    baseline_count: int
    threshold_pct: float
