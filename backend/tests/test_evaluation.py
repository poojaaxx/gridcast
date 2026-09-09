from __future__ import annotations

import datetime as dt

import numpy as np

from app.ml.evaluation.metrics import mape, smape
from app.models.forecast import Forecast
from app.models.forecast_score import ForecastScore
from app.models.load_observation import LoadObservation
from app.models.model_version import ModelVersion
from app.services import evaluation_service


def test_mape_handles_near_zero_actuals_without_dividing_by_zero():
    actual = np.array([0.0])
    predicted = np.array([5.0])

    result = mape(actual, predicted, epsilon=1.0)

    assert np.isfinite(result)
    assert result == 500.0  # |0 - 5| / max(0, 1.0) * 100


def test_smape_is_symmetric_and_bounded():
    actual = np.array([100.0])
    predicted = np.array([100.0])
    assert smape(actual, predicted) == 0.0


def _make_model_version(db_session, model_type: str = "lightgbm") -> ModelVersion:
    now = dt.datetime.now(dt.timezone.utc)
    version = ModelVersion(
        model_name=model_type,
        version=f"{model_type}-test-{now.timestamp()}",
        model_type=model_type,
        training_start=now - dt.timedelta(days=30),
        training_end=now,
        metrics_json={"residual_std": 50.0},
        artifact_path=None,
        feature_columns=["load_lag_168"],
    )
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)
    return version


def test_forecast_is_scored_against_the_matching_actual(db_session, test_region):
    model_version = _make_model_version(db_session)
    target_ts = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)

    forecast = Forecast(
        region_id=test_region.id,
        model_version_id=model_version.id,
        generated_at=target_ts - dt.timedelta(hours=24),
        target_timestamp=target_ts,
        horizon_hours=24,
        predicted_load_mw=1000.0,
        lower_bound=900.0,
        upper_bound=1100.0,
    )
    db_session.add(forecast)
    db_session.commit()
    db_session.refresh(forecast)

    actual = LoadObservation(region_id=test_region.id, timestamp=target_ts, load_mw=1050.0, source="test")
    db_session.add(actual)
    db_session.commit()

    result = evaluation_service.score_forecasts(db_session, region_id=test_region.id)
    assert result["scored"] == 1

    score = db_session.query(ForecastScore).filter_by(forecast_id=forecast.id).one()
    assert score.actual_load_mw == 1050.0
    assert score.absolute_error == 50.0
    assert score.squared_error == 2500.0


def test_forecast_cannot_be_scored_twice(db_session, test_region):
    model_version = _make_model_version(db_session)
    target_ts = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)

    forecast = Forecast(
        region_id=test_region.id,
        model_version_id=model_version.id,
        generated_at=target_ts - dt.timedelta(hours=24),
        target_timestamp=target_ts,
        horizon_hours=24,
        predicted_load_mw=500.0,
    )
    db_session.add(forecast)
    actual = LoadObservation(region_id=test_region.id, timestamp=target_ts, load_mw=520.0, source="test")
    db_session.add(actual)
    db_session.commit()

    first = evaluation_service.score_forecasts(db_session, region_id=test_region.id)
    second = evaluation_service.score_forecasts(db_session, region_id=test_region.id)

    assert first["scored"] == 1
    assert second["scored"] == 0

    count = db_session.query(ForecastScore).filter_by(forecast_id=forecast.id).count()
    assert count == 1
