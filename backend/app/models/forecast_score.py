from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ForecastScore(Base):
    __tablename__ = "forecast_scores"
    __table_args__ = (
        UniqueConstraint("forecast_id", name="uq_forecast_score_forecast_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    forecast_id: Mapped[int] = mapped_column(ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=False)
    actual_load_mw: Mapped[float] = mapped_column(Float, nullable=False)
    absolute_error: Mapped[float] = mapped_column(Float, nullable=False)
    squared_error: Mapped[float] = mapped_column(Float, nullable=False)
    absolute_percentage_error: Mapped[float] = mapped_column(Float, nullable=False)
    scored_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    forecast = relationship("Forecast", back_populates="score")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ForecastScore forecast_id={self.forecast_id} ae={self.absolute_error}>"
