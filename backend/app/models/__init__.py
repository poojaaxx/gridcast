"""Import all models so Base.metadata is fully populated for Alembic autogenerate."""
from app.models.region import Region
from app.models.load_observation import LoadObservation
from app.models.weather_observation import WeatherObservation
from app.models.model_version import ModelVersion
from app.models.forecast import Forecast
from app.models.forecast_score import ForecastScore
from app.models.user import User
from app.models.audit_log import AuditLog

__all__ = [
    "Region",
    "LoadObservation",
    "WeatherObservation",
    "ModelVersion",
    "Forecast",
    "ForecastScore",
    "User",
    "AuditLog",
]
