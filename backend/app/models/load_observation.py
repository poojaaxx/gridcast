from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LoadObservation(Base):
    __tablename__ = "load_observations"
    __table_args__ = (
        UniqueConstraint("region_id", "timestamp", name="uq_load_region_timestamp"),
        Index("ix_load_region_timestamp", "region_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    load_mw: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="synthetic")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    region = relationship("Region", back_populates="load_observations")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LoadObservation region={self.region_id} ts={self.timestamp} load={self.load_mw}>"
