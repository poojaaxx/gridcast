"""Continuous hourly pipeline scheduler.

Deliberately NOT Celery/Redis/Kafka: GridCast needs one thing done once an
hour, reliably and idempotently - a plain sleep loop in its own container is
simpler, has no extra moving parts to operate, and is trivially safe to
restart (every step ``run_cycle`` performs is already idempotent, so a
restart mid-cycle just safely re-runs/no-ops the current hour).

Runs a cycle only when the app is actually configured for LIVE mode
(``ELECTRICITY_PROVIDER=real``). In DEMO mode the worker stays intentionally
idle - GridCast's demo data progression is already driven explicitly via the
Admin Console / ``make demo`` / ``make simulate``, and this worker
automatically advancing the demo region hour-by-hour forever was never asked
for and would be a surprising, undocumented behavior change to that existing
flow.

    python -m app.worker
"""
from __future__ import annotations

import datetime as dt
import time

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.pipeline import is_live_mode
from app.tasks.hourly_pipeline import run_cycle

logger = get_logger(__name__)

# Minutes past the hour to wait before running, giving the upstream provider
# (EIA) time to publish the just-completed hour's data.
PUBLISH_DELAY_MINUTES = 10
IDLE_POLL_SECONDS = 300  # how often to re-check whether live mode has been enabled


def _seconds_until_next_run(now: dt.datetime) -> float:
    this_hour_run = now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(minutes=PUBLISH_DELAY_MINUTES)
    next_run = this_hour_run if now < this_hour_run else this_hour_run + dt.timedelta(hours=1)
    return max(1.0, (next_run - now).total_seconds())


def main() -> None:
    logger.info("GridCast worker starting - data_mode=%s", settings.data_mode)

    while True:
        if not is_live_mode():
            logger.info(
                "data_mode=demo - worker idle (demo data is advanced explicitly via the Admin "
                "Console / make simulate, not automatically). Re-checking in %ds.",
                IDLE_POLL_SECONDS,
            )
            time.sleep(IDLE_POLL_SECONDS)
            continue

        wait_seconds = _seconds_until_next_run(dt.datetime.now(dt.timezone.utc))
        logger.info("LIVE mode - sleeping %.0fs until next pipeline cycle.", wait_seconds)
        time.sleep(wait_seconds)

        if not is_live_mode():
            continue  # config changed while sleeping; re-evaluate at top of loop

        try:
            result = run_cycle(settings.live_region_name)
            logger.info("Pipeline cycle succeeded: %s", result)
        except Exception as exc:  # noqa: BLE001 - never let one bad cycle crash the worker loop
            logger.error("Pipeline cycle failed, will retry next hour: %s", exc)


if __name__ == "__main__":
    main()
