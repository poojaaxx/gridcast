"""CLI: score all unscored forecasts whose target timestamp now has an
actual observation.

    python -m app.tasks.score_forecasts [--region demo-region]
"""
from __future__ import annotations

import argparse

from app.core.logging import get_logger
from app.db.session import session_scope
from app.services import evaluation_service
from app.services.region_service import get_region_by_name

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score forecasts against newly available actuals.")
    parser.add_argument("--region", default=None, help="Limit scoring to a single region; omit to score all regions.")
    args = parser.parse_args()

    with session_scope() as db:
        region_id = None
        if args.region:
            region = get_region_by_name(db, args.region)
            if region is None:
                raise SystemExit(f"Region '{args.region}' not found.")
            region_id = region.id

        result = evaluation_service.score_forecasts(db, region_id=region_id)
        logger.info("Scoring complete: %s", result)


if __name__ == "__main__":
    main()
