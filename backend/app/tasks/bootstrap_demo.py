"""Single command that takes an empty database to a fully populated,
dashboard-ready demo state.

    python -m app.tasks.bootstrap_demo

Steps:
    1. Create the demo region (idempotent).
    2. Ingest ~6 months of synthetic load + weather history.
    3. Train seasonal naive, linear regression, and LightGBM models.
    4. Generate initial 24h/48h forecasts from each model.
    5. Simulate 72 hours of live operation (new actuals -> new forecasts -> scoring).
    6. Score any remaining unscored forecasts.
"""
from __future__ import annotations

import datetime as dt

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.ingestion.pipeline import run_ingestion
from app.services import evaluation_service
from app.services.forecasting_service import generate_forecast, get_latest_model_version
from app.services.region_service import get_region_by_name
from app.services.training_service import MODEL_FACTORIES, train_model
from app.tasks.simulate_live import advance_one_hour
from app.utils.time import utcnow

logger = get_logger(__name__)

HISTORY_DAYS = 200
SIMULATION_HOURS = 72


def main() -> None:
    region_name = settings.demo_region_slug

    logger.info("=== Step 1/6: Ingesting %d days of history for '%s' ===", HISTORY_DAYS, region_name)
    end = utcnow() - dt.timedelta(hours=SIMULATION_HOURS)  # leave room for the live simulation to "catch up" to now
    start = end - dt.timedelta(days=HISTORY_DAYS)
    run_ingestion(region_name, start, end)

    with session_scope() as db:
        region = get_region_by_name(db, region_name)
        assert region is not None

        logger.info("=== Step 2/6: Training models ===")
        for model_type in MODEL_FACTORIES:
            version = train_model(db, region, model_type)
            logger.info("Trained %s", version.version)

        logger.info("=== Step 3/6: Generating initial forecasts ===")
        for model_type in MODEL_FACTORIES:
            version = get_latest_model_version(db, model_type=model_type)
            for horizon in (24, 48):
                forecasts = generate_forecast(db, region, version, horizon)
                logger.info("Generated %d forecasts (%s, %dh)", len(forecasts), version.version, horizon)

        logger.info("=== Step 4/6: Simulating %d hours of live operation ===", SIMULATION_HOURS)
        for i in range(SIMULATION_HOURS):
            step = advance_one_hour(db, region)
            if (i + 1) % 12 == 0 or (i + 1) == SIMULATION_HOURS:
                logger.info("[%d/%d] %s", i + 1, SIMULATION_HOURS, step)

        logger.info("=== Step 5/6: Final scoring pass ===")
        result = evaluation_service.score_forecasts(db, region_id=region.id)
        logger.info("Scored %d additional forecasts", result["scored"])

        logger.info("=== Step 6/6: Summary ===")
        summary = evaluation_service.get_model_comparison(db, region_id=region.id)
        logger.info("Model comparison: %s", summary)

    logger.info("Demo bootstrap complete. Dashboard: http://localhost:5173  API docs: http://localhost:8000/docs")


if __name__ == "__main__":
    main()
