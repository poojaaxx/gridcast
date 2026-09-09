"""Centralized application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=())

    # Database
    database_url: str = "postgresql+psycopg2://gridcast:gridcast@localhost:5432/gridcast"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Data providers
    electricity_provider: str = "synthetic"
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    eia_api_key: str = ""
    eia_api_base_url: str = "https://api.eia.gov/v2"

    # Demo region defaults
    demo_region_slug: str = "demo-region"
    demo_region_name: str = "Demo Metro Area"
    demo_region_country: str = "US"
    demo_region_timezone: str = "America/New_York"
    demo_region_latitude: float = 40.7128
    demo_region_longitude: float = -74.0060

    # ML
    model_artifact_dir: str = "./data/models"
    random_seed: int = 42

    # Drift detection
    drift_mape_degradation_threshold_pct: float = 15.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
