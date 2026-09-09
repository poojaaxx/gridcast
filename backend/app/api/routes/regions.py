from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.audit_log import AuditAction, AuditStatus
from app.models.user import User
from app.schemas.region import RegionCreate, RegionOut
from app.services.audit_service import log_action
from app.services.region_service import RegionAlreadyExistsError, create_region, list_regions

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("", response_model=list[RegionOut])
def get_regions(db: Session = Depends(get_db)) -> list[RegionOut]:
    return list_regions(db)


@router.post("", response_model=RegionOut, status_code=201)
def post_region(
    payload: RegionCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RegionOut:
    try:
        region = create_region(db, **payload.model_dump())
    except RegionAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    log_action(db, action=AuditAction.REGION_CREATE.value, status=AuditStatus.SUCCESS, user=current_user, detail={"region": region.name})
    return region
