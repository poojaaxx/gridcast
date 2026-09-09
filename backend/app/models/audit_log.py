from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditAction(str, enum.Enum):
    ADMIN_LOGIN = "ADMIN_LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    DATA_INGEST = "DATA_INGEST"
    MODEL_TRAIN = "MODEL_TRAIN"
    FORECAST_GENERATE = "FORECAST_GENERATE"
    EVALUATION_SCORE = "EVALUATION_SCORE"
    REGION_CREATE = "REGION_CREATE"
    PIPELINE_CYCLE = "PIPELINE_CYCLE"
    EVALUATION_HISTORY_BACKFILL = "EVALUATION_HISTORY_BACKFILL"


class AuditStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class AuditLog(Base):
    """Immutable record of administrative actions. Never stores passwords,
    tokens, or other secrets - only what happened, who did it, and whether it
    succeeded, so the Admin Console can show a truthful operational history.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_action_created_at", "action", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Snapshot so the audit trail stays readable even if the user is later
    # deleted or renamed.
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} by={self.username} status={self.status}>"
