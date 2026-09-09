from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin, resolve_region
from app.db.session import get_db
from app.models.audit_log import AuditAction, AuditStatus
from app.models.user import User
from app.schemas.evaluation import (
    DriftStatus,
    ModelComparison,
    ModelPerformance,
    PerformancePoint,
    ScoreRequest,
    ScoreResponse,
)
from app.services import evaluation_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


def _resolve_region_id(db: Session, region_name: str | None) -> int | None:
    """Region filtering is optional on every evaluation endpoint (aggregate
    across all regions when omitted), so this wraps ``resolve_region`` to
    additionally allow ``None``.
    """
    if region_name is None:
        return None
    return resolve_region(db, region_name).id


@router.post("/score", response_model=ScoreResponse)
def post_score(
    payload: ScoreRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ScoreResponse:
    region_id = _resolve_region_id(db, payload.region)
    result = evaluation_service.score_forecasts(db, region_id=region_id)
    log_action(
        db, action=AuditAction.EVALUATION_SCORE.value, status=AuditStatus.SUCCESS,
        user=current_user, detail={"region": payload.region, "scored": result["scored"]},
    )
    return ScoreResponse(**result)


@router.get("/summary", response_model=list[ModelPerformance])
def get_summary(region: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[ModelPerformance]:
    region_id = _resolve_region_id(db, region)
    return evaluation_service.get_model_performance_summary(db, region_id=region_id)


@router.get("/timeseries", response_model=list[PerformancePoint])
def get_timeseries(
    region: str | None = Query(default=None),
    granularity: str = Query(default="day", pattern="^(day|week)$"),
    db: Session = Depends(get_db),
) -> list[PerformancePoint]:
    region_id = _resolve_region_id(db, region)
    return evaluation_service.get_performance_timeseries(db, region_id=region_id, granularity=granularity)


@router.get("/model-comparison", response_model=ModelComparison)
def get_model_comparison(region: str | None = Query(default=None), db: Session = Depends(get_db)) -> ModelComparison:
    region_id = _resolve_region_id(db, region)
    return evaluation_service.get_model_comparison(db, region_id=region_id)


@router.get("/drift", response_model=DriftStatus)
def get_drift(
    region: str | None = Query(default=None),
    model_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DriftStatus:
    region_id = _resolve_region_id(db, region)
    return evaluation_service.get_drift_status(db, region_id=region_id, model_type=model_type)
