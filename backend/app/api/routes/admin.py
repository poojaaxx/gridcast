from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.admin import AuditLogOut, SystemStatus
from app.services.audit_service import get_last_success_timestamp, get_recent_audit_logs

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status", response_model=SystemStatus)
def get_system_status(current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> SystemStatus:
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception as exc:  # noqa: BLE001
        database_status = f"error: {exc}"

    return SystemStatus(
        backend_status="ok",
        database_status=database_status,
        environment=settings.environment,
        data_mode=settings.data_mode,
        electricity_provider=settings.electricity_provider,
        current_admin=current_user.username,
        last_ingestion_at=get_last_success_timestamp(db, AuditAction.DATA_INGEST.value),
        last_forecast_generated_at=get_last_success_timestamp(db, AuditAction.FORECAST_GENERATE.value),
        last_evaluation_scored_at=get_last_success_timestamp(db, AuditAction.EVALUATION_SCORE.value),
    )


@router.get("/audit-log", response_model=list[AuditLogOut])
def get_audit_log(
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    return get_recent_audit_logs(db, limit=limit)
