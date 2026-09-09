"""In-process runner for the admin-triggered historical evaluation backfill.

Why this exists (Render Free-tier constraints)
------------------------------------------------
Render's Free web-service plan has no Shell access, no one-off Jobs, and no
free Cron Jobs (Cron Jobs carry "a minimum monthly charge of $1/service" on
every plan) - confirmed via render.com/docs/free ("Free web services don't
support ... running one-off jobs ... Shell access via SSH or the Render
Dashboard") and render.com/docs/jobs. The only way to run a one-time
server-side operation at all, without upgrading the plan, is through the
already-running web service's own HTTP process.

A 30-45 day walk-forward backtest fits a fresh model per day-block per
model type; a local dry run measured ~26s for 10 days x 3 models, so a
45-day run is on the order of ~2 minutes. Render does not document a
guaranteed minimum HTTP request timeout, and community reports describe
timeouts as low as 15-30s on some configurations - running this inline
inside a single synchronous request response cycle is not safe. Instead,
a POST starts it in a background thread and returns immediately; a GET
polls the in-memory status until it's done.

Render Free is always a single instance/single process for a given service
(horizontal scaling isn't offered on Free either), so a simple in-process,
lock-guarded singleton is sufficient to prevent two runs from overlapping -
no Redis/DB-based locking needed for this. If the process restarts mid-run
(e.g. a redeploy), this state simply resets to idle - the underlying
backfill is idempotent (see backtest_service), so nothing is corrupted and
a fresh trigger safely resumes from wherever it left off.
"""
from __future__ import annotations

import datetime as dt
import threading

from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.audit_log import AuditAction, AuditStatus
from app.services import backtest_service
from app.services.audit_service import log_action
from app.services.region_service import get_region_by_name
from app.utils.time import utcnow

logger = get_logger(__name__)

WORKER_USERNAME = "system:evaluation_history"


def _iso(value):
    return value.isoformat() if isinstance(value, dt.datetime) else value


def _summarize_report(report: dict) -> dict:
    """Reduces the full backfill report to a small, JSON-safe summary -
    counts, dates, and metrics only. Never includes anything from settings/
    the environment, so this is always safe to return over HTTP and to
    store in the audit log.
    """
    before = report["before"]
    plan = report["plan"]

    per_model = []
    for m in report["per_model"]:
        if m.get("skipped"):
            per_model.append({"model_type": m["model_type"], "skipped": True, "reason": m["reason"]})
        else:
            per_model.append(
                {
                    "model_type": m["model_type"],
                    "blocks_run": m["blocks_run"],
                    "forecasts_inserted": m["forecasts_inserted"],
                    "forecasts_skipped_existing": m["forecasts_skipped_existing"],
                    "blocks_failed_count": len(m["blocks_failed"]),
                }
            )

    return {
        "load_count": before["load_count"],
        "load_sources": before["load_sources"],
        "load_earliest": _iso(before["load_earliest"]),
        "load_latest": _iso(before["load_latest"]),
        "weather_count": before["weather_count"],
        "weather_earliest": _iso(before["weather_earliest"]),
        "weather_latest": _iso(before["weather_latest"]),
        "backtest_start": _iso(plan["backtest_start"]),
        "backtest_end": _iso(plan["backtest_end"]),
        "backtest_days": plan["backtest_days"],
        "per_model": per_model,
        "newly_scored": report["newly_scored"],
        "performance": report["performance"],
        "best_model": report["model_comparison"]["best_model"],
        "drift": report["drift"],
    }


class EvaluationHistoryRunner:
    """A single, hard-coded operation only: there is no way to parameterize
    this with a different region, function, or arguments from the outside -
    ``start()`` always runs exactly ``backtest_service.run_evaluation_history_backfill``
    against whatever region name the caller (the admin route, which itself
    hard-codes ``settings.live_region_name``) passes in.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict = {
            "status": "idle",
            "region": None,
            "started_at": None,
            "finished_at": None,
            "started_by": None,
            "error": None,
            "report": None,
        }

    def get_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def start(self, region_name: str, started_by: str) -> bool:
        """Returns False (and starts nothing new) if a run is already in
        progress - callers must surface this as a conflict, never queue or
        silently drop it, so two admins can't accidentally double-run this.
        """
        with self._lock:
            if self._state["status"] == "running":
                return False
            self._state = {
                "status": "running",
                "region": region_name,
                "started_at": utcnow(),
                "finished_at": None,
                "started_by": started_by,
                "error": None,
                "report": None,
            }

        thread = threading.Thread(target=self._run, args=(region_name,), daemon=True)
        thread.start()
        return True

    def _run(self, region_name: str) -> None:
        try:
            with session_scope() as db:
                region = get_region_by_name(db, region_name)
                if region is None:
                    raise ValueError(f"Region '{region_name}' not found.")
                report = backtest_service.run_evaluation_history_backfill(db, region)

            summary = _summarize_report(report)
            with self._lock:
                self._state["status"] = "completed"
                self._state["finished_at"] = utcnow()
                self._state["report"] = summary

            with session_scope() as audit_db:
                log_action(
                    audit_db,
                    action=AuditAction.EVALUATION_HISTORY_BACKFILL.value,
                    status=AuditStatus.SUCCESS,
                    username=WORKER_USERNAME,
                    detail={"region": region_name, **summary},
                )
        except Exception as exc:  # noqa: BLE001 - a background thread must never die silently
            logger.exception("Evaluation history backfill failed for region '%s'", region_name)
            with self._lock:
                self._state["status"] = "failed"
                self._state["finished_at"] = utcnow()
                self._state["error"] = str(exc)

            with session_scope() as audit_db:
                log_action(
                    audit_db,
                    action=AuditAction.EVALUATION_HISTORY_BACKFILL.value,
                    status=AuditStatus.FAILURE,
                    username=WORKER_USERNAME,
                    detail={"region": region_name, "error": str(exc)},
                )


runner = EvaluationHistoryRunner()
