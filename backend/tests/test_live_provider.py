"""Tests for the real (EIA) electricity provider and the live/demo pipeline
behavior around it - in particular the project's hard rule that LIVE mode
must never silently fall back to synthetic data.

All EIA HTTP calls are mocked (``requests.get`` is monkeypatched) - these
tests never make real network calls, so they run the same in CI as locally.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.ingestion import pipeline
from app.ingestion.base import LoadRecord, WeatherRecord
from app.ingestion.electricity_provider import RealElectricityProvider
from app.models.region import Region

from tests.conftest import TEST_USER_PASSWORD


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _eia_payload(rows: list[dict], total: int | None = None) -> dict:
    return {"response": {"total": str(total if total is not None else len(rows)), "data": rows}}


def _row(period: str, value, respondent: str = "NYIS", type_: str = "D") -> dict:
    return {"period": period, "respondent": respondent, "type": type_, "value": value}


@pytest.fixture(autouse=True)
def _eia_settings(monkeypatch):
    monkeypatch.setattr(settings, "eia_api_key", "test-key")
    monkeypatch.setattr(settings, "eia_respondent_code", "NYIS")
    yield


# --- 1. Provider response normalization + 2/3. timestamp/timezone handling ---


def test_provider_normalizes_rows_into_utc_load_records(monkeypatch):
    rows = [_row("2026-01-01T00", "1000"), _row("2026-01-01T01", "1050.5")]
    monkeypatch.setattr(
        "app.ingestion.electricity_provider.requests.get",
        lambda *a, **k: _FakeResponse(_eia_payload(rows)),
    )

    provider = RealElectricityProvider()
    records = provider.fetch_load(
        latitude=40.7, longitude=-74.0,
        start=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        end=dt.datetime(2026, 1, 1, 2, tzinfo=dt.timezone.utc),
    )

    assert len(records) == 2
    assert all(isinstance(r, LoadRecord) for r in records)
    assert records[0].timestamp == dt.datetime(2026, 1, 1, 0, tzinfo=dt.timezone.utc)
    assert records[0].timestamp.tzinfo is not None  # never naive
    assert records[0].load_mw == 1000.0
    assert records[1].load_mw == 1050.5
    assert all(r.source == "eia" for r in records)


# --- 4. Invalid records rejected / 5. negative (impossible) loads rejected ---


def test_provider_rejects_malformed_and_negative_rows(monkeypatch):
    rows = [
        _row("2026-01-01T00", "1000"),        # valid
        _row("2026-01-01T01", None),          # null value -> rejected
        _row("2026-01-01T02", "not-a-number"),  # malformed -> rejected
        _row("2026-01-01T03", "-50"),         # impossible negative demand -> rejected
        {"period": "2026-01-01T04", "respondent": "NYIS", "type": "D"},  # missing "value" key -> rejected
    ]
    monkeypatch.setattr(
        "app.ingestion.electricity_provider.requests.get",
        lambda *a, **k: _FakeResponse(_eia_payload(rows)),
    )

    provider = RealElectricityProvider()
    records = provider.fetch_load(
        latitude=40.7, longitude=-74.0,
        start=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        end=dt.datetime(2026, 1, 1, 5, tzinfo=dt.timezone.utc),
    )

    assert len(records) == 1
    assert records[0].load_mw == 1000.0


def test_provider_paginates_beyond_a_single_page(monkeypatch):
    """EIA caps rows per request; a range spanning more than one page must
    be fully retrieved via offset pagination, not silently truncated."""
    page_size = 3
    monkeypatch.setattr("app.ingestion.electricity_provider.PAGE_SIZE", page_size)

    all_rows = [_row(f"2026-01-0{i + 1}T00", str(1000 + i)) for i in range(7)]
    calls = []

    def fake_get(url, params, timeout):  # noqa: ARG001
        param_dict = dict(params)
        offset = int(param_dict["offset"])
        calls.append(offset)
        page = all_rows[offset: offset + page_size]
        return _FakeResponse(_eia_payload(page, total=len(all_rows)))

    monkeypatch.setattr("app.ingestion.electricity_provider.requests.get", fake_get)

    provider = RealElectricityProvider()
    records = provider.fetch_load(
        latitude=40.7, longitude=-74.0,
        start=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        end=dt.datetime(2026, 1, 8, tzinfo=dt.timezone.utc),
    )

    assert len(records) == 7
    assert calls == [0, 3, 6]  # three pages fetched to cover all 7 rows


# --- 9. Provider failure is surfaced correctly ---


def test_provider_raises_on_http_failure(monkeypatch):
    monkeypatch.setattr(
        "app.ingestion.electricity_provider.requests.get",
        lambda *a, **k: _FakeResponse({}, status_code=503),
    )
    provider = RealElectricityProvider()
    with pytest.raises(Exception):
        provider.fetch_load(
            latitude=40.7, longitude=-74.0,
            start=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
            end=dt.datetime(2026, 1, 1, 2, tzinfo=dt.timezone.utc),
        )


def test_provider_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "eia_api_key", "")
    with pytest.raises(ValueError):
        RealElectricityProvider()


# --- 7. LIVE mode does NOT fall back to synthetic data (critical rule) ---


def test_live_mode_raises_instead_of_falling_back_to_synthetic(monkeypatch):
    monkeypatch.setattr(settings, "electricity_provider", "real")

    def _boom(*args, **kwargs):
        raise RuntimeError("EIA is down")

    monkeypatch.setattr("app.ingestion.electricity_provider.requests.get", _boom)

    with pytest.raises(pipeline.LiveProviderError):
        pipeline.fetch_load(
            latitude=40.7, longitude=-74.0,
            start=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
            end=dt.datetime(2026, 1, 1, 2, tzinfo=dt.timezone.utc),
            weather=[],
        )


def test_live_mode_raises_on_empty_provider_response(monkeypatch):
    monkeypatch.setattr(settings, "electricity_provider", "real")
    monkeypatch.setattr(
        "app.ingestion.electricity_provider.requests.get",
        lambda *a, **k: _FakeResponse(_eia_payload([])),
    )

    with pytest.raises(pipeline.LiveProviderError):
        pipeline.fetch_load(
            latitude=40.7, longitude=-74.0,
            start=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
            end=dt.datetime(2026, 1, 1, 2, tzinfo=dt.timezone.utc),
            weather=[],
        )


# --- 8. DEMO mode uses the synthetic provider (and never calls the real one) ---


def test_demo_mode_never_calls_the_real_provider(monkeypatch):
    assert settings.electricity_provider == "synthetic"  # default, not live

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Real EIA provider must not be invoked in demo mode")

    monkeypatch.setattr("app.ingestion.electricity_provider.requests.get", _fail_if_called)

    records, source = pipeline.fetch_load(
        latitude=40.7, longitude=-74.0,
        start=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        end=dt.datetime(2026, 1, 1, 3, tzinfo=dt.timezone.utc),
        weather=[],
    )

    assert source == "synthetic"
    assert len(records) == 3


# --- Data-quality validation (Phase 3) ---


def test_validate_load_records_rejects_bad_rows_without_inventing_values():
    now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    records = [
        LoadRecord(timestamp=now, load_mw=1000.0, source="eia"),
        LoadRecord(timestamp=now, load_mw=1000.0, source="eia"),  # duplicate timestamp
        LoadRecord(timestamp=now + dt.timedelta(hours=1), load_mw=-5.0, source="eia"),  # impossible
        LoadRecord(timestamp=now + dt.timedelta(hours=2), load_mw=float("nan"), source="eia"),  # non-finite
    ]

    valid, rejected = pipeline.validate_load_records(records)

    assert len(valid) == 1
    assert valid[0].load_mw == 1000.0
    assert rejected["duplicate_timestamp"] == 1
    assert rejected["invalid_load"] == 2


def test_validate_weather_records_rejects_bad_readings():
    now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    records = [
        WeatherRecord(timestamp=now, temperature_c=20.0, humidity_percent=50.0, precipitation=0.0, weather_code=0),
        WeatherRecord(timestamp=now + dt.timedelta(hours=1), temperature_c=float("nan"), humidity_percent=50.0, precipitation=0.0, weather_code=0),
    ]
    valid, rejected = pipeline.validate_weather_records(records)
    assert len(valid) == 1
    assert rejected["invalid_reading"] == 1


# --- Historical backfill: resumable / idempotent (Phase 5) ---


def test_backfill_historical_is_idempotent(monkeypatch, db_session, test_region):
    monkeypatch.setattr(settings, "electricity_provider", "real")

    rows = [_row(f"2026-01-01T{h:02d}", str(1000 + h)) for h in range(24)]
    monkeypatch.setattr(
        "app.ingestion.electricity_provider.requests.get",
        lambda *a, **k: _FakeResponse(_eia_payload(rows)),
    )
    # Weather provider (Open-Meteo) isn't mocked here; force it to fail so
    # the pipeline takes the LIVE "unavailable" branch instead of making a
    # real HTTP call out to Open-Meteo during a unit test.
    monkeypatch.setattr(
        "app.ingestion.pipeline.OpenMeteoWeatherProvider.fetch_weather",
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("no network in tests")),
    )

    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    end = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)

    first = pipeline.backfill_historical(test_region.name, start, end, chunk_days=1, pace_seconds=0)
    assert sum(r["load_inserted"] for r in first) == 24
    assert sum(r["load_skipped"] for r in first) == 0

    second = pipeline.backfill_historical(test_region.name, start, end, chunk_days=1, pace_seconds=0)
    assert sum(r["load_inserted"] for r in second) == 0
    assert sum(r["load_skipped"] for r in second) == 24


# --- Provider failure surfaces as a clean, typed HTTP error (not a raw 500) ---


def test_ingest_endpoint_returns_502_on_live_provider_failure(client, admin_user, db_session, monkeypatch):
    monkeypatch.setattr(settings, "electricity_provider", "real")
    monkeypatch.setattr(settings, "eia_api_key", "test-key")

    def _boom(*args, **kwargs):
        raise RuntimeError("EIA is unreachable")

    monkeypatch.setattr("app.ingestion.electricity_provider.requests.get", _boom)
    # Avoid a real network call to Open-Meteo for this route-level test; the
    # weather step runs (and is expected to succeed or degrade) before the
    # load fetch fails, but shouldn't depend on live internet either way.
    monkeypatch.setattr(
        "app.ingestion.pipeline.OpenMeteoWeatherProvider.fetch_weather",
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("no network in tests")),
    )

    login = client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})
    assert login.status_code == 200

    region_name = "nyiso-live-test"
    try:
        response = client.post("/data/ingest", json={"region": region_name, "days": 1})
        assert response.status_code == 502
        assert "EIA" in response.json()["detail"]
    finally:
        client.post("/auth/logout")
        created = db_session.execute(select(Region).where(Region.name == region_name)).scalar_one_or_none()
        if created is not None:
            db_session.delete(created)
            db_session.commit()
