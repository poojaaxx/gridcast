from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from app.ingestion.base import LoadRecord
from app.ingestion.pipeline import upsert_load_observations
from app.models.load_observation import LoadObservation


def _sample_records(start: dt.datetime, hours: int) -> list[LoadRecord]:
    return [
        LoadRecord(timestamp=start + dt.timedelta(hours=i), load_mw=1000.0 + i, source="test")
        for i in range(hours)
    ]


def test_duplicate_ingestion_does_not_duplicate_records(db_session, test_region):
    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    records = _sample_records(start, 24)

    inserted_1, skipped_1 = upsert_load_observations(db_session, test_region.id, records)
    db_session.commit()
    assert inserted_1 == 24
    assert skipped_1 == 0

    # Re-running ingestion with the exact same records must not create duplicates.
    inserted_2, skipped_2 = upsert_load_observations(db_session, test_region.id, records)
    db_session.commit()
    assert inserted_2 == 0
    assert skipped_2 == 24

    total_rows = (
        db_session.query(LoadObservation).filter_by(region_id=test_region.id).count()
    )
    assert total_rows == 24


def test_partial_overlap_only_inserts_new_records(db_session, test_region):
    start = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)
    first_batch = _sample_records(start, 10)
    upsert_load_observations(db_session, test_region.id, first_batch)
    db_session.commit()

    overlapping_batch = _sample_records(start, 20)  # first 10 hours overlap, next 10 are new
    inserted, skipped = upsert_load_observations(db_session, test_region.id, overlapping_batch)
    db_session.commit()

    assert inserted == 10
    assert skipped == 10

    total_rows = db_session.query(LoadObservation).filter_by(region_id=test_region.id).count()
    assert total_rows == 20


def test_timestamp_uniqueness_is_enforced_at_the_database_level(db_session, test_region):
    ts = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)
    db_session.add(LoadObservation(region_id=test_region.id, timestamp=ts, load_mw=100.0, source="test"))
    db_session.commit()

    db_session.add(LoadObservation(region_id=test_region.id, timestamp=ts, load_mw=999.0, source="test"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
