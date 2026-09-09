"""Administrative audit logging.

Every mutating admin action gets one row here - who did it, what, when, and
whether it succeeded. Never pass secrets (passwords, tokens) into `detail`;
it's stored as-is in a JSON column and rendered directly in the Admin
Console's Audit Activity panel.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog, AuditStatus
from app.models.user import User


def log_action(
    db: Session,
    *,
    action: str,
    status: AuditStatus | str = AuditStatus.SUCCESS,
    user: User | None = None,
    username: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user.id if user else None,
        username=username or (user.username if user else "unknown"),
        action=action,
        status=status.value if isinstance(status, AuditStatus) else status,
        detail=detail,
    )
    db.add(entry)
    db.commit()
    return entry


def get_recent_audit_logs(db: Session, limit: int = 50) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())


def get_last_success_timestamp(db: Session, action: str):
    stmt = (
        select(AuditLog.created_at)
        .where(AuditLog.action == action, AuditLog.status == AuditStatus.SUCCESS.value)
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def get_last_entry(db: Session, action: str) -> AuditLog | None:
    """Most recent entry for an action regardless of outcome - used where
    the Admin Console needs to show "did the last run fail", not just "when
    did it last succeed" (e.g. pipeline cycle status).
    """
    stmt = select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at.desc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()
