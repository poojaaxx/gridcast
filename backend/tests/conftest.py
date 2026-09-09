"""Shared pytest fixtures.

DB-dependent tests require a live PostgreSQL instance reachable at
DATABASE_URL (e.g. via `docker compose up -d postgres` or inside the
backend container, which is how `make test` runs them). Pure unit tests
(features, models, metrics) have no such dependency.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import base as db_base
from app.db.session import SessionLocal, engine
from app import models as _models  # noqa: F401 ensures models are registered on Base.metadata
from app.core.security import hash_password
from app.main import app
from app.models.region import Region
from app.models.user import User, UserRole


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


@pytest.fixture()
def client(_create_tables):
    with TestClient(app) as c:
        yield c


TEST_USER_PASSWORD = "correct-horse-battery-staple"


def _make_user(db_session, *, role: str, password: str = TEST_USER_PASSWORD) -> User:
    user = User(
        username=f"test-{role}-{uuid.uuid4().hex[:8]}",
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_user(db_session):
    user = _make_user(db_session, role=UserRole.ADMIN.value)
    yield user
    db_session.delete(user)
    db_session.commit()


@pytest.fixture()
def analyst_user(db_session):
    user = _make_user(db_session, role=UserRole.ANALYST.value)
    yield user
    db_session.delete(user)
    db_session.commit()


@pytest.fixture()
def inactive_user(db_session):
    user = _make_user(db_session, role=UserRole.ADMIN.value)
    user.is_active = False
    db_session.commit()
    yield user
    db_session.delete(user)
    db_session.commit()
