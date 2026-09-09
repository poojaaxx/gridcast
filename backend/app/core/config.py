"""Centralized application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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
    # "synthetic" (default demo mode) or "real" (live mode via EIA - see
    # README "Data Sources": a genuine Indian hourly electricity-demand API
    # could not be verified as machine-readable/stable within this project's
    # research, so EIA was selected as the documented, honestly-labeled
    # fallback per the project's own escalation rule). data_mode below is
    # derived from this single flag so LIVE/DEMO can never disagree with the
    # provider actually in use.
    electricity_provider: str = "synthetic"
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    eia_api_key: str = ""
    eia_api_base_url: str = "https://api.eia.gov/v2"
    # EIA "respondent" (balancing authority) code to treat as GridCast's live
    # region. NYIS = New York ISO - hourly actual demand back to 2019,
    # verified reachable and correctly time-labeled in UTC (see README).
    eia_respondent_code: str = "NYIS"

    # Metadata for the auto-created live region (distinct from demo_region_*
    # above so live and demo data are never accidentally mixed in one region
    # row). Coordinates are used only for weather lookup (Open-Meteo), not
    # for selecting the EIA respondent, which is chosen by eia_respondent_code.
    live_region_name: str = "nyiso-live"
    live_region_country: str = "US"
    live_region_timezone: str = "America/New_York"
    live_region_latitude: float = 40.7128
    live_region_longitude: float = -74.0060

    # Optional bounds for the historical backfill task
    # (app.tasks.backfill_live). ISO date/datetime strings; left blank to use
    # the task's own sane default window at call time instead of a
    # hardcoded date that would otherwise go stale.
    gridcast_backfill_start: str = ""
    gridcast_backfill_end: str = ""

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

    # --- Auth / sessions ---
    # Deployment environment label surfaced in /health and the Admin Console -
    # not a secret, purely informational (e.g. "development" vs "production").
    environment: str = "development"

    # HMAC secret used to sign session JWTs. Required - no insecure fallback
    # is provided, so a missing value fails application startup loudly
    # (via pydantic-settings validation) instead of silently signing tokens
    # with a known, publicly-visible default. Generate with e.g.
    # `openssl rand -hex 32` and set it in .env; never commit the real value.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8h session; no refresh-token rotation (see README)

    session_cookie_name: str = "gridcast_session"
    # Must be True in any deployment served over HTTPS. Left False by default
    # so local HTTP development (localhost) isn't broken - browsers refuse to
    # store `Secure` cookies over plain HTTP.
    cookie_secure: bool = False
    # "lax" covers the default same-site local/dev topology (frontend and
    # backend both on `localhost`, different ports). A production deployment
    # that splits frontend/backend across different registrable domains needs
    # "none" (which additionally requires cookie_secure=True).
    cookie_samesite: str = "lax"

    # First-admin bootstrap (see app.tasks.bootstrap_admin / startup hook).
    # Left blank by default: no admin is created and bootstrap silently no-ops
    # until both are supplied via environment/secrets. Aliased to the
    # documented GRIDCAST_ADMIN_* names (rather than the pydantic-settings
    # default of ADMIN_BOOTSTRAP_*) since that's the name used throughout
    # .env.example, the README, and the CLI task's error message.
    admin_bootstrap_username: str = Field(default="", validation_alias="GRIDCAST_ADMIN_USERNAME")
    admin_bootstrap_password: str = Field(default="", validation_alias="GRIDCAST_ADMIN_PASSWORD")

    # Login brute-force protection (in-memory, single-process - see README
    # for why this is intentionally lightweight rather than Redis-backed).
    login_rate_limit_max_attempts: int = 10
    login_rate_limit_window_seconds: int = 900

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def data_mode(self) -> str:
        """"live" when a real electricity provider is configured, else "demo"."""
        return "live" if self.electricity_provider == "real" else "demo"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
