from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.region import RegionCreate, RegionOut
from app.services.region_service import RegionAlreadyExistsError, create_region, list_regions

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("", response_model=list[RegionOut])
def get_regions(db: Session = Depends(get_db)) -> list[RegionOut]:
    return list_regions(db)


@router.post("", response_model=RegionOut, status_code=201)
def post_region(payload: RegionCreate, db: Session = Depends(get_db)) -> RegionOut:
    try:
        return create_region(db, **payload.model_dump())
    except RegionAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
