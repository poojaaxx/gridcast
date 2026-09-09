"""CLI: train all three forecasting models for a region.

    python -m app.tasks.train_all --region demo-region
"""
from __future__ import annotations

import argparse

from app.core.logging import get_logger
from app.db.session import session_scope
from app.services.region_service import get_region_by_name
from app.services.training_service import MODEL_FACTORIES, train_model

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train all forecasting models for a region.")
    parser.add_argument("--region", required=True)
    args = parser.parse_args()

    with session_scope() as db:
        region = get_region_by_name(db, args.region)
        if region is None:
            raise SystemExit(f"Region '{args.region}' not found. Run ingestion first.")

        for model_type in MODEL_FACTORIES:
            logger.info("Training %s for region '%s'...", model_type, region.name)
            version = train_model(db, region, model_type)
            mean_metrics = version.metrics_json.get("mean_metrics", {})
            logger.info(
                "Trained %s -> mae=%.2f rmse=%.2f mape=%.2f%%",
                version.version, mean_metrics.get("mae", 0), mean_metrics.get("rmse", 0), mean_metrics.get("mape", 0),
            )


if __name__ == "__main__":
    main()
