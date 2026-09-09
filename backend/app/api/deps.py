from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.region import Region
from app.services.region_service import get_region_by_name


def resolve_region(db: Session, region_name: str) -> Region:
    """Look up a region by name, raising a 404 if it doesn't exist. Shared by
    every route that accepts a ``region`` query/body parameter.
    """
    region = get_region_by_name(db, region_name)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Region '{region_name}' not found.")
    return region
