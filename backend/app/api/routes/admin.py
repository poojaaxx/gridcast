from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import settings
from app.db.session import get_db
from app.ingestion.pipeline import is_live_mode
from app.models.audit_log import AuditAction, AuditStatus
from app.models.user import User
from app.schemas.admin import AuditLogOut, EvaluationHistoryRunStatus, SystemStatus
from app.services.audit_service import get_last_entry, get_last_success_timestamp, get_recent_audit_logs, log_action
from app.services.evaluation_history_runner import runner as evaluation_history_runner

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status", response_model=SystemStatus)
def get_system_status(current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> SystemStatus:
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception as exc:  # noqa: BLE001
        database_status = f"error: {exc}"

    last_cycle = get_last_entry(db, AuditAction.PIPELINE_CYCLE.value)

    return SystemStatus(
        backend_status="ok",
        database_status=database_status,
        environment=settings.environment,
        data_mode=settings.data_mode,
        electricity_provider=settings.electricity_provider,
        live_region=settings.live_region_name,
        demo_region=settings.demo_region_slug,
        current_admin=current_user.username,
        last_ingestion_at=get_last_success_timestamp(db, AuditAction.DATA_INGEST.value),
        last_forecast_generated_at=get_last_success_timestamp(db, AuditAction.FORECAST_GENERATE.value),
        last_evaluation_scored_at=get_last_success_timestamp(db, AuditAction.EVALUATION_SCORE.value),
        last_pipeline_cycle_at=last_cycle.created_at if last_cycle else None,
        last_pipeline_cycle_status=last_cycle.status if last_cycle else None,
    )


@router.get("/audit-log", response_model=list[AuditLogOut])
def get_audit_log(
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    return get_recent_audit_logs(db, limit=limit)


# --- Historical evaluation backfill: a single hard-coded operation --------
#
# Deliberately takes NO request body / parameters at all - the region is
# always settings.live_region_name, resolved server-side, never client
# input. This is the one operation exposed here, and it always runs the
# exact same function; there is no argument surface for arbitrary command
# execution. See app.services.evaluation_history_runner for why this runs
# as a background thread (started by this POST, polled via the GET below)
# rather than inline in this request - Render's Free plan has no Shell/Jobs/
# Cron to run this out-of-band, and a 30-45 day backtest can take on the
# order of minutes, longer than is safe to hold open a single HTTP request.


@router.post("/evaluation-history/run", response_model=EvaluationHistoryRunStatus, status_code=202)
def start_evaluation_history_run(
    current_user: User = Depends(require_admin), db: Session = Depends(get_db)
) -> EvaluationHistoryRunStatus:
    if not is_live_mode():
        raise HTTPException(
            status_code=400,
            detail="Evaluation history backfill only runs when ELECTRICITY_PROVIDER=real (LIVE mode) - "
            "there is no real data to backfill in demo mode.",
        )

    started = evaluation_history_runner.start(settings.live_region_name, current_user.username)
    if not started:
        raise HTTPException(status_code=409, detail="An evaluation history backfill is already running.")

    log_action(
        db, action=AuditAction.EVALUATION_HISTORY_BACKFILL.value, status=AuditStatus.SUCCESS,
        user=current_user, detail={"event": "started", "region": settings.live_region_name},
    )
    return EvaluationHistoryRunStatus(**evaluation_history_runner.get_state())


@router.get("/evaluation-history/status", response_model=EvaluationHistoryRunStatus)
def get_evaluation_history_run_status(current_user: User = Depends(require_admin)) -> EvaluationHistoryRunStatus:
    return EvaluationHistoryRunStatus(**evaluation_history_runner.get_state())
