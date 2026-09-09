"""Shared pytest fixtures.

DB-dependent tests require a live PostgreSQL instance reachable at
DATABASE_URL (e.g. via `docker compose up -d postgres` or inside the
backend container, which is how `make test` runs them). Pure unit tests
(features, models, metrics) have no such dependency.
"""
from __future__ import annotations

import uuid

import pytest

from app.db import base as db_base
from app.db.session import SessionLocal, engine
from app import models as _models  # noqa: F401 ensures models are registered on Base.metadata
from app.models.region import Region


@pytest.fixture(scope="session")
def _create_tables():
    """Only invoked by tests that actually request a DB session, so pure
    unit tests (features, models, metrics) never require Postgres to be up.
    """
    db_base.Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db_session(_create_tables):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_region(db_session):
    region = Region(
        name=f"test-region-{uuid.uuid4().hex[:10]}",
        country="US",
        timezone="UTC",
        latitude=40.0,
        longitude=-74.0,
    )
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)
    yield region
    db_session.delete(region)
    db_session.commit()
