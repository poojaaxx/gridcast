"""Password hashing and session-token primitives.

Passwords are hashed with Argon2id (via argon2-cffi's high-level API, which
defaults to Argon2id - the algorithm OWASP currently recommends for password
storage). Sessions are stateless: a short-lived JWT is signed with an HMAC
secret and carried in an HttpOnly cookie, so the browser's JavaScript never
sees or stores it (no localStorage/sessionStorage involved) and the backend
never needs a server-side session store.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.core.config import settings

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_session_token(*, user_id: int, username: str, role: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> dict[str, Any] | None:
    """Returns the decoded payload, or None for any invalid/expired token.
    Never raises - callers treat a bad token the same as "not logged in".
    """
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
