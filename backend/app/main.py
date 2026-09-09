from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, data, evaluation, forecasts, health, models, regions
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.services.auth_service import bootstrap_admin

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="GridCast API",
    description=(
        "Electricity load forecasting and continuous model evaluation platform. "
        "Generates forecasts, persists them, scores them against real observations, "
        "and monitors model accuracy over time."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """A conservative baseline that doesn't interfere with the API/SPA split:
    no CSP here (the frontend is a separate Vite dev server / static bundle
    with its own headers, and a strict CSP on a pure JSON API adds nothing).
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # This API is never meant to be framed - blocks clickjacking-style embeds.
    response.headers["X-Frame-Options"] = "DENY"
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(regions.router)
app.include_router(data.router)
app.include_router(models.router)
app.include_router(forecasts.router)
app.include_router(evaluation.router)


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "GridCast API starting up (environment=%s, electricity_provider=%s, data_mode=%s)",
        settings.environment, settings.electricity_provider, settings.data_mode,
    )
    db = SessionLocal()
    try:
        admin = bootstrap_admin(db)
        if admin is not None:
            logger.info("Admin bootstrap: created initial admin user.")
        elif not settings.admin_bootstrap_username:
            logger.warning(
                "No GRIDCAST_ADMIN_USERNAME/GRIDCAST_ADMIN_PASSWORD configured - "
                "no admin account exists yet. See README for bootstrap instructions."
            )
    finally:
        db.close()
