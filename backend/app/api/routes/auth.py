from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import create_session_token
from app.db.session import get_db
from app.models.audit_log import AuditAction, AuditStatus
from app.models.user import User
from app.schemas.auth import LoginRequest, UserOut
from app.services import auth_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, user: User) -> None:
    token = create_session_token(user_id=user.id, username=user.username, role=user.role)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    client_ip = _client_ip(request)

    if auth_service.is_rate_limited(payload.username, client_ip):
        logger.warning("Login rate limit exceeded for '%s' from %s", payload.username, client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Please wait before trying again.",
        )

    user = auth_service.authenticate_user(db, payload.username, payload.password)
    if user is None:
        auth_service.record_failed_attempt(payload.username, client_ip)
        log_action(db, action=AuditAction.LOGIN_FAILED.value, status=AuditStatus.FAILURE, username=payload.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    auth_service.clear_failed_attempts(payload.username, client_ip)
    auth_service.record_login(db, user)
    _set_session_cookie(response, user)
    log_action(db, action=AuditAction.ADMIN_LOGIN.value, status=AuditStatus.SUCCESS, user=user)

    return user


@router.post("/logout")
def logout(response: Response, current_user: User | None = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    if current_user is not None:
        log_action(db, action=AuditAction.LOGOUT.value, status=AuditStatus.SUCCESS, user=current_user)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(require_user)) -> UserOut:
    return current_user
