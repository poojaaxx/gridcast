from __future__ import annotations

import uuid

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.auth_service import bootstrap_admin

from tests.conftest import TEST_USER_PASSWORD


def test_login_success_sets_cookie_and_returns_user(client, admin_user):
    response = client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == admin_user.username
    assert body["role"] == "admin"
    assert settings.session_cookie_name in response.cookies


def test_login_invalid_password_is_rejected(client, admin_user):
    response = client.post("/auth/login", json={"username": admin_user.username, "password": "wrong-password"})
    assert response.status_code == 401
    assert settings.session_cookie_name not in response.cookies


def test_login_unknown_user_is_rejected(client):
    response = client.post("/auth/login", json={"username": f"nobody-{uuid.uuid4().hex[:8]}", "password": "whatever"})
    assert response.status_code == 401


def test_login_inactive_user_is_rejected(client, inactive_user):
    response = client.post("/auth/login", json={"username": inactive_user.username, "password": TEST_USER_PASSWORD})
    assert response.status_code == 401


def test_protected_endpoint_without_authentication_returns_401(client):
    response = client.post("/evaluation/score", json={})
    assert response.status_code == 401


def test_protected_admin_endpoint_with_analyst_returns_403(client, analyst_user):
    login = client.post("/auth/login", json={"username": analyst_user.username, "password": TEST_USER_PASSWORD})
    assert login.status_code == 200

    response = client.post("/evaluation/score", json={})
    assert response.status_code == 403

    client.post("/auth/logout")


def test_protected_admin_endpoint_with_admin_is_allowed(client, admin_user):
    login = client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})
    assert login.status_code == 200

    response = client.post("/evaluation/score", json={})
    assert response.status_code == 200
    assert "scored" in response.json()

    client.post("/auth/logout")


def test_logout_clears_session(client, admin_user):
    client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})
    assert client.get("/auth/me").status_code == 200

    logout = client.post("/auth/logout")
    assert logout.status_code == 200

    assert client.get("/auth/me").status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user_when_authenticated(client, admin_user):
    client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == admin_user.username
    client.post("/auth/logout")


def test_password_hash_is_never_returned(client, admin_user):
    client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})
    me = client.get("/auth/me")
    login = client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})

    assert "password_hash" not in me.json()
    assert "password_hash" not in login.json()
    assert TEST_USER_PASSWORD not in me.text
    client.post("/auth/logout")


def test_admin_bootstrap_is_idempotent(db_session, monkeypatch):
    username = f"bootstrap-test-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(settings, "admin_bootstrap_username", username)
    monkeypatch.setattr(settings, "admin_bootstrap_password", "a-reasonably-strong-password")

    try:
        first = bootstrap_admin(db_session)
        assert first is not None
        assert first.role == "admin"

        second = bootstrap_admin(db_session)
        assert second is None  # no duplicate created on re-run

        count = db_session.query(User).filter_by(username=username).count()
        assert count == 1
    finally:
        db_session.query(User).filter_by(username=username).delete()
        db_session.commit()


def test_audit_log_created_on_login_and_admin_action(client, admin_user, db_session):
    client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})
    client.post("/evaluation/score", json={})

    logs = (
        db_session.query(AuditLog)
        .filter(AuditLog.username == admin_user.username)
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    actions = {log.action for log in logs}
    assert "ADMIN_LOGIN" in actions
    assert "EVALUATION_SCORE" in actions
    assert all(log.status == "success" for log in logs)

    client.post("/auth/logout")


def test_audit_logs_do_not_contain_secrets(client, admin_user, db_session):
    client.post("/auth/login", json={"username": admin_user.username, "password": TEST_USER_PASSWORD})

    logs = db_session.query(AuditLog).filter(AuditLog.username == admin_user.username).all()
    for log in logs:
        serialized = str(log.detail or "")
        assert TEST_USER_PASSWORD not in serialized
        assert "password" not in serialized.lower()
        assert settings.jwt_secret_key not in serialized

    client.post("/auth/logout")
