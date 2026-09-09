from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"

    return {
        "status": "ok",
        "database": db_status,
        # Public, non-sensitive: lets the dashboard clearly label whether it
        # is showing synthetic demo data or a real configured provider, and
        # which provider/region that is - no credentials are included.
        "data_mode": settings.data_mode,
        "electricity_provider": settings.electricity_provider,
        "region": settings.live_region_name if settings.data_mode == "live" else settings.demo_region_slug,
    }
