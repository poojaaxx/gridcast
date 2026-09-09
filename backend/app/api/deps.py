from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_session_token
from app.db.session import get_db
from app.models.region import Region
from app.models.user import User
from app.services.auth_service import get_user_by_username
from app.services.region_service import get_region_by_name


def resolve_region(db: Session, region_name: str) -> Region:
    """Look up a region by name, raising a 404 if it doesn't exist. Shared by
    every route that accepts a ``region`` query/body parameter.
    """
    region = get_region_by_name(db, region_name)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Region '{region_name}' not found.")
    return region


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Reads the session cookie and resolves it to a User, or None if the
    request is unauthenticated (missing/invalid/expired token, or the user
    was deleted/deactivated since the token was issued). Never raises - this
    is the dependency GET endpoints that stay public regardless of login
    state would use if they ever needed to know "who's asking", but today no
    read endpoint requires it. It is the base every protected dependency
    below builds on.
    """
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    payload = decode_session_token(token)
    if payload is None:
        return None
    user = get_user_by_username(db, payload.get("username", ""))
    if user is None or not user.is_active:
        return None
    return user


def require_user(current_user: User | None = Depends(get_current_user)) -> User:
    """Any authenticated, active user - the floor every protected endpoint
    (including admin-only ones) requires."""
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return current_user


def require_admin(current_user: User = Depends(require_user)) -> User:
    """The actual authorization boundary for every mutating/administrative
    endpoint. This is a real, independent backend check - it does not trust
    anything the frontend has hidden or shown."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return current_user
