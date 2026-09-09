"""One full continuous-pipeline cycle: ingest -> score -> forecast -> record.

    EVERY HOUR (see app.worker for the scheduler):
        1. Fetch the latest electricity actuals + weather, upsert (idempotent).
        2. Score any previously-issued forecasts whose target timestamp now
           has an actual observation.
        3. Generate fresh 24h and 48h forecasts anchored at the new present,
           for the latest trained version of every model type.
        4. Record one PIPELINE_CYCLE audit entry summarizing the run.

Safe to run repeatedly, including immediately after a crash/restart: every
step is already idempotent (ingestion upsert, forecast unique constraint,
scoring anti-join on already-scored ids), so re-running the same hour twice
is a safe no-op, never a duplicate.

    python -m app.tasks.hourly_pipeline --region nyiso-live
"""
from __future__ import annotations

import argparse
import datetime as dt

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import session_scope
from app.ingestion.pipeline import run_ingestion
from app.models.audit_log import AuditAction, AuditStatus
from app.models.model_version import ModelVersion
from app.models.region import Region
from app.services import evaluation_service
from app.services.audit_service import log_action
from app.services.forecasting_service import generate_forecast, get_latest_model_version
from app.utils.time import utcnow

logger = get_logger(__name__)

FORECAST_HORIZONS = (24, 48)
WORKER_USERNAME = "system:worker"


def run_cycle(region_name: str, ingest_hours: int = 3) -> dict:
    """One cycle for ``region_name``. ``ingest_hours`` widens the ingestion
    window beyond just the last hour so a late-publishing upstream hour is
    naturally picked up on a later cycle without manual backfill - safe
    because re-ingesting already-seen hours is a no-op.
    """
    end = utcnow()
    start = end - dt.timedelta(hours=ingest_hours)
    summary: dict = {"region": region_name, "started_at": end.isoformat()}

    try:
        ingest_result = run_ingestion(region_name, start, end)
        summary["ingest"] = {k: v for k, v in ingest_result.items() if k != "region_id"}

        with session_scope() as db:
            region = db.execute(select(Region).where(Region.name == region_name)).scalar_one_or_none()
            if region is None:
                raise ValueError(f"Region '{region_name}' not found after ingestion.")

            score_result = evaluation_service.score_forecasts(db, region_id=region.id)
            summary["scored"] = score_result["scored"]

            model_types = db.execute(select(ModelVersion.model_type).distinct()).scalars().all()
            forecasts_generated = 0
            forecast_errors = []
            for model_type in model_types:
                version = get_latest_model_version(db, model_type=model_type)
                if version is None:
                    continue
                for horizon in FORECAST_HORIZONS:
                    try:
                        forecasts = generate_forecast(db, region, version, horizon)
                        forecasts_generated += len(forecasts)
                    except Exception as exc:  # noqa: BLE001 - one model's failure shouldn't sink the cycle
                        logger.error("Forecast generation failed (model=%s horizon=%dh): %s", model_type, horizon, exc)
                        forecast_errors.append(f"{model_type}@{horizon}h: {exc}")

            summary["forecasts_generated"] = forecasts_generated
            if forecast_errors:
                summary["forecast_errors"] = forecast_errors
    except Exception as exc:
        summary["error"] = str(exc)
        _log_cycle(summary, AuditStatus.FAILURE)
        raise

    _log_cycle(summary, AuditStatus.SUCCESS)
    return summary


def _log_cycle(summary: dict, status: AuditStatus) -> None:
    with session_scope() as db:
        log_action(db, action=AuditAction.PIPELINE_CYCLE.value, status=status, username=WORKER_USERNAME, detail=summary)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one continuous-pipeline cycle (ingest -> score -> forecast).")
    parser.add_argument("--region", required=True)
    parser.add_argument("--ingest-hours", type=int, default=3)
    args = parser.parse_args()

    result = run_cycle(args.region, ingest_hours=args.ingest_hours)
    logger.info("Pipeline cycle complete: %s", result)


if __name__ == "__main__":
    main()
