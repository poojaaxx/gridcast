from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.model_version import ModelVersion
from app.schemas.model import ModelVersionOut, TrainModelRequest
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
def train(payload: TrainModelRequest, db: Session = Depends(get_db)) -> ModelVersionOut:
    region = get_region_by_name(db, payload.region)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Region '{payload.region}' not found.")
    try:
        return train_model(db, region, payload.model_type)
    except InsufficientDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
