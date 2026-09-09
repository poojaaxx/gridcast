"""CLI: backfill a historical, walk-forward, out-of-sample forecast +
evaluation-score history using ONLY real observations already ingested for
a region - no synthetic data, no demo-data generator. See
``app.services.backtest_service`` for the full methodology and its one
disclosed simplification (real historical weather stands in for "the
forecast available at run time"; the load/target variable is never leaked).

Safe to run more than once: every forecast is inserted through the same
``uq_forecast_identity`` idempotent upsert live forecast generation uses, so
re-running this never creates duplicates - it just reports 0 newly inserted.

    python -m app.tasks.bootstrap_evaluation_history --region nyiso-live
"""
from __future__ import annotations

import argparse

from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.audit_log import AuditAction, AuditStatus
from app.services import backtest_service
from app.services.audit_service import log_action
from app.services.region_service import get_region_by_name

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill historical forecast/evaluation history from real data only (no fabrication)."
    )
    parser.add_argument("--region", required=True)
    parser.add_argument("--max-days", type=int, default=backtest_service.DEFAULT_MAX_BACKTEST_DAYS)
    parser.add_argument("--block-hours", type=int, default=backtest_service.DEFAULT_BLOCK_HOURS)
    parser.add_argument("--horizon", type=int, default=backtest_service.DEFAULT_HORIZON_HOURS)
    parser.add_argument("--min-backtest-days", type=int, default=backtest_service.MIN_BACKTEST_DAYS)
    args = parser.parse_args()

    with session_scope() as db:
        region = get_region_by_name(db, args.region)
        if region is None:
            raise SystemExit(f"Region '{args.region}' not found. Run ingestion and training first.")

        try:
            report = backtest_service.run_evaluation_history_backfill(
                db,
                region,
                max_days=args.max_days,
                block_hours=args.block_hours,
                horizon_hours=args.horizon,
                min_backtest_days=args.min_backtest_days,
            )
        except (backtest_service.NonRealDataError, backtest_service.BacktestInfeasibleError) as exc:
            logger.error("Evaluation history backfill stopped: %s", exc)
            log_action(
                db, action=AuditAction.EVALUATION_HISTORY_BACKFILL.value, status=AuditStatus.FAILURE,
                username="system:evaluation_history", detail={"region": args.region, "error": str(exc)},
            )
            raise SystemExit(str(exc)) from exc

        for line in backtest_service.format_report(report):
            logger.info(line)

        log_action(
            db, action=AuditAction.EVALUATION_HISTORY_BACKFILL.value, status=AuditStatus.SUCCESS,
            username="system:evaluation_history",
            detail={
                "region": report["region"],
                "backtest_days": report["plan"]["backtest_days"],
                "newly_scored": report["newly_scored"],
                "per_model": [
                    {k: v for k, v in m.items() if k != "blocks_failed"} for m in report["per_model"]
                ],
            },
        )


if __name__ == "__main__":
    main()
