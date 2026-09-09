from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Region(Base):
    """A grid region/balancing area. ``name`` doubles as the human-friendly
    machine identifier used throughout the CLI and API (e.g. ``demo-region``).
    """

    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    load_observations = relationship("LoadObservation", back_populates="region", cascade="all, delete-orphan")
    weather_observations = relationship("WeatherObservation", back_populates="region", cascade="all, delete-orphan")
    forecasts = relationship("Forecast", back_populates="region", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Region {self.name}>"
