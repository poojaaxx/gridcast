from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.region import Region


class RegionAlreadyExistsError(Exception):
    pass


def list_regions(db: Session) -> list[Region]:
    return list(db.execute(select(Region).order_by(Region.name)).scalars())


def get_region_by_name(db: Session, name: str) -> Region | None:
    return db.execute(select(Region).where(Region.name == name)).scalar_one_or_none()


def create_region(
    db: Session,
    *,
    name: str,
    country: str,
    timezone: str,
    latitude: float,
    longitude: float,
) -> Region:
    if get_region_by_name(db, name) is not None:
        raise RegionAlreadyExistsError(f"Region '{name}' already exists.")

    region = Region(name=name, country=country, timezone=timezone, latitude=latitude, longitude=longitude)
    db.add(region)
    db.commit()
    db.refresh(region)
    return region
