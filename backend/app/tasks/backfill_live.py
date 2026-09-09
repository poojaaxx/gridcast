"""CLI: controlled historical backfill for the LIVE region from EIA.

Resumable and idempotent - safe to re-run or extend the date range; existing
timestamps are never duplicated (same upsert path as regular ingestion, via
app.ingestion.pipeline.backfill_historical).

    python -m app.tasks.backfill_live
    python -m app.tasks.backfill_live --start 2026-06-01 --end 2026-09-01

Falls back to GRIDCAST_BACKFILL_START / GRIDCAST_BACKFILL_END from the
environment if --start/--end are omitted, and to a 90-day trailing window
ending now if neither is set - deliberately not a hardcoded date, which
would go stale.
"""
from __future__ import annotations

import argparse
import datetime as dt

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.pipeline import backfill_historical, is_live_mode
from app.utils.time import utcnow

logger = get_logger(__name__)

DEFAULT_BACKFILL_DAYS = 90


def _resolve_bound(cli_value: str | None, env_value: str, default: dt.datetime) -> dt.datetime:
    raw = cli_value or env_value
    if not raw:
        return default
    parsed = dt.datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical live electricity + weather data from EIA.")
    parser.add_argument("--region", default=None, help="Defaults to the configured live region name.")
    parser.add_argument("--start", default=None, help="ISO date/datetime (UTC). Defaults to GRIDCAST_BACKFILL_START or 90 days ago.")
    parser.add_argument("--end", default=None, help="ISO date/datetime (UTC). Defaults to GRIDCAST_BACKFILL_END or now.")
    parser.add_argument("--chunk-days", type=int, default=200, help="Days per request chunk (EIA caps 5000 rows/request).")
    parser.add_argument("--pace-seconds", type=float, default=2.0, help="Delay between chunk requests (rate-limit friendly).")
    args = parser.parse_args()

    if not is_live_mode():
        raise SystemExit(
            "ELECTRICITY_PROVIDER is not 'real' - backfill fetches from the live EIA provider and "
            "would be pointless (and misleading) to run in demo mode. Set ELECTRICITY_PROVIDER=real "
            "and EIA_API_KEY first."
        )

    now = utcnow()
    end = _resolve_bound(args.end, settings.gridcast_backfill_end, now)
    start = _resolve_bound(args.start, settings.gridcast_backfill_start, now - dt.timedelta(days=DEFAULT_BACKFILL_DAYS))
    region_name = args.region or settings.live_region_name

    logger.info("Starting historical backfill for '%s': %s -> %s", region_name, start.isoformat(), end.isoformat())
    results = backfill_historical(region_name, start, end, chunk_days=args.chunk_days, pace_seconds=args.pace_seconds)

    total_load = sum(r["load_inserted"] for r in results)
    total_weather = sum(r["weather_inserted"] for r in results)
    logger.info(
        "Backfill complete: %d chunk(s), %d load rows inserted, %d weather rows inserted.",
        len(results), total_load, total_weather,
    )


if __name__ == "__main__":
    main()
