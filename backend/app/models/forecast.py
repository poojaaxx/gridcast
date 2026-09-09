from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint(
            "region_id", "model_version_id", "generated_at", "target_timestamp",
            name="uq_forecast_identity",
        ),
        Index("ix_forecast_target_timestamp", "target_timestamp"),
        Index("ix_forecast_generated_at", "generated_at"),
        Index("ix_forecast_model_version_id", "model_version_id"),
        Index("ix_forecast_region_id", "region_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), nullable=False)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_load_mw: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    upper_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    region = relationship("Region", back_populates="forecasts")
    model_version = relationship("ModelVersion", back_populates="forecasts")
    score = relationship("ForecastScore", back_populates="forecast", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Forecast target={self.target_timestamp} pred={self.predicted_load_mw}>"
