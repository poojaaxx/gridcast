from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    training_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    training_end: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    artifact_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    feature_columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    forecasts = relationship("Forecast", back_populates="model_version", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ModelVersion {self.version}>"
