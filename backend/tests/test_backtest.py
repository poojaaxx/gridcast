"""Tests for the historical evaluation backfill (app.services.backtest_service).

Covers: no future leakage, chronological walk-forward correctness,
idempotency, forecast->actual matching, score persistence, all three
models, and refusal to run on insufficient or non-real data.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from app.models.forecast import Forecast
from app.models.forecast_score import ForecastScore
from app.models.load_observation import LoadObservation
from app.models.model_version import ModelVersion
from app.models.weather_observation import WeatherObservation
from app.services import backtest_service
from app.services.training_service import MODEL_FACTORIES

TEST_MIN_TRAINING_HOURS = 400
TEST_START = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


@pytest.fixture()
def patched_min_training_hours(monkeypatch):
    """The real MIN_TRAINING_HOURS (1440h = 60 days) is a deliberately high
    production floor; tests use a much smaller one so seeding data and
    fitting three models stays fast, without changing production behavior
    (only this module's copy of the name is patched).
    """
    monkeypatch.setattr(backtest_service, "MIN_TRAINING_HOURS", TEST_MIN_TRAINING_HOURS)
    yield TEST_MIN_TRAINING_HOURS


def _seed_real_history(db_session, region, total_hours: int, source: str = "eia", start: dt.datetime = TEST_START):
    loads = []
    weathers = []
    for h in range(total_hours):
        ts = start + dt.timedelta(hours=h)
        load = 1000 + 200 * np.sin(2 * np.pi * ts.hour / 24) + 50 * np.sin(2 * np.pi * ts.weekday() / 7)
        loads.append(LoadObservation(region_id=region.id, timestamp=ts, load_mw=float(load), source=source))
        temp = 15 + 10 * np.sin(2 * np.pi * ts.hour / 24)
        weathers.append(WeatherObservation(region_id=region.id, timestamp=ts, temperature_c=float(temp), humidity_percent=50.0))
    db_session.bulk_save_objects(loads)
    db_session.bulk_save_objects(weathers)
    db_session.commit()


def _seed_attribution_model_versions(db_session):
    now = dt.datetime.now(dt.timezone.utc)
    for model_type in MODEL_FACTORIES:
        db_session.add(
            ModelVersion(
                model_name=model_type,
                version=f"{model_type}-attrib-{now.timestamp()}-{model_type}",
                model_type=model_type,
                training_start=now - dt.timedelta(days=1),
                training_end=now,
                metrics_json={},
                artifact_path=None,
                feature_columns=[],
            )
        )
    db_session.commit()


# --- Pure, DB-free tests of the planning/windowing logic --------------------


def _flat_history_df(total_hours: int, start: dt.datetime = TEST_START) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [start + dt.timedelta(hours=h) for h in range(total_hours)],
            "load_mw": np.zeros(total_hours),
            "temperature_c": np.zeros(total_hours),
            "humidity_percent": np.zeros(total_hours),
        }
    )


def test_plan_backtest_window_reserves_minimum_training_before_backtest_start():
    df = _flat_history_df(500)

    plan = backtest_service.plan_backtest_window(df, min_training_hours=400, max_days=45, block_hours=24)

    rows_before_start = int((df["timestamp"] < plan["backtest_start"]).sum())
    assert rows_before_start >= 400
    assert plan["backtest_end"] == df["timestamp"].iloc[-1].to_pydatetime() + dt.timedelta(hours=1)
    assert plan["n_blocks"] * plan["block_hours"] <= 500 - 400


def test_plan_backtest_window_raises_when_insufficient():
    df = _flat_history_df(300)

    with pytest.raises(backtest_service.BacktestInfeasibleError):
        backtest_service.plan_backtest_window(df, min_training_hours=400, block_hours=24)


def test_plan_backtest_window_caps_at_max_days():
    df = _flat_history_df(400 + 200 * 24)  # far more available than max_days allows

    plan = backtest_service.plan_backtest_window(df, min_training_hours=400, max_days=10, block_hours=24)

    assert plan["backtest_days"] <= 10


# --- DB-backed integration tests --------------------------------------------


def test_backfill_rejects_non_real_data_source(db_session, test_region):
    _seed_real_history(db_session, test_region, 50, source="synthetic")

    with pytest.raises(backtest_service.NonRealDataError):
        backtest_service.inspect_region_history(db_session, test_region)


def test_backfill_raises_on_insufficient_history(db_session, test_region):
    """Uses the REAL (unpatched) MIN_TRAINING_HOURS floor - far too little
    data must be reported, never silently padded or faked."""
    _seed_real_history(db_session, test_region, 50)

    with pytest.raises(backtest_service.BacktestInfeasibleError):
        backtest_service.run_evaluation_history_backfill(db_session, test_region, min_backtest_days=1)


def test_backfill_generates_scored_forecasts_for_all_three_models(db_session, test_region, patched_min_training_hours):
    total_hours = TEST_MIN_TRAINING_HOURS + 48  # 400h training reserve + 2 backtest blocks
    _seed_real_history(db_session, test_region, total_hours)
    _seed_attribution_model_versions(db_session)

    report = backtest_service.run_evaluation_history_backfill(
        db_session, test_region, max_days=45, block_hours=24, horizon_hours=24, min_backtest_days=1,
    )

    assert {m["model_type"] for m in report["per_model"]} == set(MODEL_FACTORIES.keys())
    for m in report["per_model"]:
        assert not m.get("skipped"), m
        assert m["blocks_run"] == 2
        assert m["forecasts_inserted"] == 48  # 2 blocks x 24h horizon each
        assert m["blocks_failed"] == []

    assert report["newly_scored"] > 0
    performance_by_type = {p["model_type"]: p for p in report["performance"]}
    assert set(performance_by_type) == set(MODEL_FACTORIES.keys())
    for perf in performance_by_type.values():
        assert perf["forecast_count"] > 0
        assert perf["mae"] >= 0


def test_backfill_forecasts_never_target_before_their_own_origin(db_session, test_region, patched_min_training_hours):
    total_hours = TEST_MIN_TRAINING_HOURS + 48
    _seed_real_history(db_session, test_region, total_hours)
    _seed_attribution_model_versions(db_session)

    backtest_service.run_evaluation_history_backfill(
        db_session, test_region, max_days=45, block_hours=24, horizon_hours=24, min_backtest_days=1,
    )

    forecasts = db_session.execute(select(Forecast).where(Forecast.region_id == test_region.id)).scalars().all()
    assert forecasts
    for f in forecasts:
        assert f.target_timestamp >= f.generated_at
        # The training reserve is exactly TEST_MIN_TRAINING_HOURS hours; no
        # forecast origin may fall inside that reserved training-only window.
        assert f.generated_at >= TEST_START + dt.timedelta(hours=TEST_MIN_TRAINING_HOURS)


def test_backfill_scores_match_real_actuals_at_target_timestamp(db_session, test_region, patched_min_training_hours):
    total_hours = TEST_MIN_TRAINING_HOURS + 24
    _seed_real_history(db_session, test_region, total_hours)
    _seed_attribution_model_versions(db_session)

    backtest_service.run_evaluation_history_backfill(
        db_session, test_region, max_days=45, block_hours=24, horizon_hours=24, min_backtest_days=1,
    )

    scores = db_session.execute(
        select(ForecastScore, Forecast).join(Forecast).where(Forecast.region_id == test_region.id)
    ).all()
    assert scores
    for score, forecast in scores:
        actual = db_session.execute(
            select(LoadObservation.load_mw).where(
                LoadObservation.region_id == test_region.id,
                LoadObservation.timestamp == forecast.target_timestamp,
            )
        ).scalar_one()
        assert score.actual_load_mw == actual
        assert score.absolute_error == pytest.approx(abs(actual - forecast.predicted_load_mw))


def test_backfill_is_idempotent(db_session, test_region, patched_min_training_hours):
    total_hours = TEST_MIN_TRAINING_HOURS + 24
    _seed_real_history(db_session, test_region, total_hours)
    _seed_attribution_model_versions(db_session)

    first = backtest_service.run_evaluation_history_backfill(
        db_session, test_region, max_days=45, block_hours=24, horizon_hours=24, min_backtest_days=1,
    )
    forecast_count_after_first = db_session.execute(
        select(Forecast).where(Forecast.region_id == test_region.id)
    ).scalars().all()
    score_count_after_first = db_session.execute(
        select(ForecastScore).join(Forecast).where(Forecast.region_id == test_region.id)
    ).scalars().all()

    second = backtest_service.run_evaluation_history_backfill(
        db_session, test_region, max_days=45, block_hours=24, horizon_hours=24, min_backtest_days=1,
    )
    forecast_count_after_second = db_session.execute(
        select(Forecast).where(Forecast.region_id == test_region.id)
    ).scalars().all()
    score_count_after_second = db_session.execute(
        select(ForecastScore).join(Forecast).where(Forecast.region_id == test_region.id)
    ).scalars().all()

    assert len(forecast_count_after_second) == len(forecast_count_after_first)
    assert len(score_count_after_second) == len(score_count_after_first)
    for m in second["per_model"]:
        assert m["forecasts_inserted"] == 0
    assert second["newly_scored"] == 0
    assert first["newly_scored"] > 0
