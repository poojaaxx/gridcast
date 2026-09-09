"""CLI: generate forecasts for a region using the latest version of each
trained model type (or a specific --model_version).

    python -m app.tasks.generate_forecasts --region demo-region --horizon 24
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.model_version import ModelVersion
from app.services.forecasting_service import generate_forecast, get_latest_model_version, resolve_model_version
from app.services.region_service import get_region_by_name

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate forecasts for a region.")
    parser.add_argument("--region", required=True)
    parser.add_argument("--horizon", type=int, default=24, choices=[24, 48])
    parser.add_argument("--model_version", default=None, help="Specific model version, or omit for latest of every model type")
    args = parser.parse_args()

    with session_scope() as db:
        region = get_region_by_name(db, args.region)
        if region is None:
            raise SystemExit(f"Region '{args.region}' not found.")

        if args.model_version:
            versions = [resolve_model_version(db, args.model_version)]
        else:
            model_types = db.execute(select(ModelVersion.model_type).distinct()).scalars().all()
            versions = [get_latest_model_version(db, model_type=mt) for mt in model_types]
            versions = [v for v in versions if v is not None]

        if not versions:
            raise SystemExit(f"No trained models found. Run 'python -m app.tasks.train_all --region {args.region}' first.")

        for version in versions:
            forecasts = generate_forecast(db, region, version, args.horizon)
            logger.info("Generated %d forecasts using %s (horizon=%dh)", len(forecasts), version.version, args.horizon)


if __name__ == "__main__":
    main()
