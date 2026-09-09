from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import data, evaluation, forecasts, health, models, regions
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

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

app.include_router(health.router)
app.include_router(regions.router)
app.include_router(data.router)
app.include_router(models.router)
app.include_router(forecasts.router)
app.include_router(evaluation.router)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("GridCast API starting up (electricity_provider=%s)", settings.electricity_provider)
