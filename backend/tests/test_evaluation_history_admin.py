"""Tests for the admin-only historical evaluation backfill endpoints.

Covers: authentication/authorization boundaries, the fixed/allowlisted
operation (no arbitrary region or command input is accepted), and
concurrent-run protection - all without actually needing a full multi-day
backtest to complete (the runner itself is unit-tested end-to-end in
test_backtest.py; here we only need to prove the HTTP/auth/concurrency
wiring around it is correct).
"""
from __future__ import annotations

import inspect
import threading

from app.core.config import settings
from app.services.evaluation_history_runner import EvaluationHistoryRunner

from tests.conftest import TEST_USER_PASSWORD


def test_run_endpoint_requires_authentication(client):
    response = client.post("/admin/evaluation-history/run")
    assert response.status_code == 401


def test_status_endpoint_requires_authentication(client):
    response = client.get("/admin/evaluation-history/status")
    assert response.status_code == 401


def test_run_endpoint_rejects_non_admin(client, analyst_user):
    client.post("/auth/login", json={"username": analyst_user.username, "password": TEST_USER_PASSWORD})

    response = client.post("/admin/evaluation-history/run")
    assert response.status_code == 403

    client.post("/auth/logout")


def test_run_endpoint_rejects_demo_mode(client, admin_user, monkeypatch):
    """This backfill only makes sense against real data - refuse outright in
    demo mode rather than starting a run that will immediately fail on
    NonRealDataError."""
    monkeypatch.setattr(settings, "electricity_provider", "synthetic")
    client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})

    response = client.post("/admin/evaluation-history/run")
    assert response.status_code == 400

    client.post("/auth/logout")


def test_run_endpoint_accepts_no_body_or_region_override(client, admin_user, monkeypatch):
    """The operation is hard-coded to settings.live_region_name - there is no
    request parameter that could redirect it at a different region, and
    passing an arbitrary JSON body must not change what region is used.
    """
    monkeypatch.setattr(settings, "electricity_provider", "real")
    started_regions = []
    monkeypatch.setattr(
        "app.api.routes.admin.evaluation_history_runner.start",
        lambda region_name, started_by: started_regions.append(region_name) or True,
    )
    client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})

    response = client.post("/admin/evaluation-history/run", json={"region": "some-other-region", "cmd": "rm -rf /"})
    assert response.status_code == 202
    assert started_regions == [settings.live_region_name]

    client.post("/auth/logout")


def test_run_endpoint_returns_409_when_already_running(client, admin_user, monkeypatch):
    monkeypatch.setattr(settings, "electricity_provider", "real")
    monkeypatch.setattr("app.api.routes.admin.evaluation_history_runner.start", lambda region_name, started_by: False)
    client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})

    response = client.post("/admin/evaluation-history/run")
    assert response.status_code == 409

    client.post("/auth/logout")


def test_status_endpoint_never_exposes_secrets(client, admin_user):
    client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})

    response = client.get("/admin/evaluation-history/status")
    assert response.status_code == 200
    serialized = response.text
    assert settings.jwt_secret_key not in serialized
    assert settings.database_url not in serialized

    client.post("/auth/logout")


# --- Runner-level concurrency test (no HTTP, deterministic) -----------------


def test_runner_rejects_a_second_concurrent_start():
    runner = EvaluationHistoryRunner()
    release = threading.Event()
    started = threading.Event()

    def fake_backfill(region_name):
        started.set()
        release.wait(timeout=5)

    runner._run = fake_backfill  # type: ignore[assignment]

    assert runner.start("nyiso-live", "admin") is True
    assert started.wait(timeout=5)

    # A second start attempt while the first is still "running" must be
    # rejected outright, never queued and never silently dropped-and-ignored.
    assert runner.start("nyiso-live", "admin") is False
    assert runner.get_state()["status"] == "running"

    release.set()


def test_evaluation_history_runner_has_no_command_or_argument_surface():
    """Guards the design invariant: start() takes only a region name and a
    username for attribution - never a free-form command, argument list, or
    kwargs that could be used to run something other than the one hard-coded
    backfill function.
    """
    signature = inspect.signature(EvaluationHistoryRunner.start)
    param_names = list(signature.parameters)
    assert param_names == ["self", "region_name", "started_by"]
