from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.audit_log import AuditAction, AuditStatus
from app.models.model_version import ModelVersion
from app.models.user import User
from app.schemas.model import ModelVersionOut, TrainModelRequest
from app.services.audit_service import log_action
from app.services.region_service import get_region_by_name
from app.services.training_service import InsufficientDataError, train_model

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelVersionOut])
def list_models(db: Session = Depends(get_db)) -> list[ModelVersionOut]:
    stmt = select(ModelVersion).order_by(ModelVersion.created_at.desc())
    return list(db.execute(stmt).scalars())


@router.get("/{model_id}", response_model=ModelVersionOut)
def get_model(model_id: int, db: Session = Depends(get_db)) -> ModelVersionOut:
    model = db.get(ModelVersion, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model version {model_id} not found.")
    return model


@router.post("/train", response_model=ModelVersionOut)
def train(
    payload: TrainModelRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ModelVersionOut:
    region = get_region_by_name(db, payload.region)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Region '{payload.region}' not found.")
    try:
        version = train_model(db, region, payload.model_type)
    except (InsufficientDataError, ValueError) as exc:
        log_action(
            db, action=AuditAction.MODEL_TRAIN.value, status=AuditStatus.FAILURE,
            user=current_user, detail={"region": payload.region, "model_type": payload.model_type, "error": str(exc)},
        )
        status_code = 422 if isinstance(exc, InsufficientDataError) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_action(
        db, action=AuditAction.MODEL_TRAIN.value, status=AuditStatus.SUCCESS,
        user=current_user, detail={"region": payload.region, "model_type": payload.model_type, "version": version.version},
    )
    return version
