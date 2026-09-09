"""Time helpers. All timestamps are stored and reasoned about in UTC internally."""
from __future__ import annotations

import datetime as dt


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def floor_to_hour(timestamp: dt.datetime) -> dt.datetime:
    return timestamp.replace(minute=0, second=0, microsecond=0)


def ensure_utc(timestamp: dt.datetime) -> dt.datetime:
    """Normalize a possibly-naive datetime to timezone-aware UTC."""
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=dt.timezone.utc)
    return timestamp.astimezone(dt.timezone.utc)


def hourly_range(start: dt.datetime, end: dt.datetime) -> list[dt.datetime]:
    """Inclusive-start, exclusive-end hourly range."""
    start = floor_to_hour(ensure_utc(start))
    end = floor_to_hour(ensure_utc(end))
    hours = int((end - start).total_seconds() // 3600)
    return [start + dt.timedelta(hours=i) for i in range(hours)]
