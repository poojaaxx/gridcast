"""Authentication, admin bootstrap, and login rate limiting.

Rate limiting is a simple in-memory sliding window keyed by (username, IP).
This is intentionally lightweight: the app runs as a single Uvicorn process
(see docker-compose.yml), so process-local state is sufficient and avoids
pulling in Redis for a portfolio-scale deployment. It resets on restart and
would not coordinate across multiple worker processes/replicas - see the
README security section for how to harden this in a real multi-instance
deployment (a shared store such as Redis would be the natural next step).
"""
from __future__ import annotations

import datetime as dt
import time
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.utils.time import utcnow

logger = get_logger(__name__)

# {(username, client_ip): [timestamp, ...]} - failed attempts only.
_failed_attempts: dict[tuple[str, str], list[float]] = defaultdict(list)


def is_rate_limited(username: str, client_ip: str) -> bool:
    key = (username.lower(), client_ip)
    window_start = time.monotonic() - settings.login_rate_limit_window_seconds
    attempts = [t for t in _failed_attempts[key] if t >= window_start]
    _failed_attempts[key] = attempts
    return len(attempts) >= settings.login_rate_limit_max_attempts


def record_failed_attempt(username: str, client_ip: str) -> None:
    _failed_attempts[(username.lower(), client_ip)].append(time.monotonic())


def clear_failed_attempts(username: str, client_ip: str) -> None:
    _failed_attempts.pop((username.lower(), client_ip), None)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Returns the user on success, None on any failure (unknown user, wrong
    password, or inactive account) - callers shouldn't distinguish these
    cases in the response, only in what they log/rate-limit."""
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def record_login(db: Session, user: User) -> None:
    user.last_login_at = utcnow()
    db.commit()


def bootstrap_admin(db: Session) -> User | None:
    """Idempotently create the first admin from GRIDCAST_ADMIN_USERNAME /
    GRIDCAST_ADMIN_PASSWORD. No-ops (returns None) if either is unset, or if
    a user with that username already exists - never overwrites an existing
    account's password, and never creates duplicates on repeated calls
    (e.g. every container start).
    """
    username = settings.admin_bootstrap_username.strip()
    password = settings.admin_bootstrap_password
    if not username or not password:
        return None

    existing = get_user_by_username(db, username)
    if existing is not None:
        return None

    admin = User(
        username=username,
        password_hash=hash_password(password),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info("Bootstrapped first admin user '%s' (password not logged)", username)
    return admin
