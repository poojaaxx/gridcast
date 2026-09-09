"""Historical forecast/evaluation backfill using ONLY real, already-ingested
observations - no synthetic data, no demo-data generator, no fabricated
values.

Why this can't just reuse the already-deployed model artifacts
----------------------------------------------------------------
``training_service.train_model`` fits its *final* persisted model on ALL
available clean history before saving it. Using that artifact to "backtest"
historical days it was already fit on would be exactly the leakage this
project's walk-forward methodology exists to prevent (train data must
strictly precede forecast origin, which must strictly precede the target
actual - see README "Forecasting Models"). So every historical forecast here
is produced by a *freshly instantiated* model of the same type, trained only
on real observations strictly before that forecast's origin. Nothing is
saved to disk for these transient models; the ``Forecast.model_version_id``
FK still points at the real, currently-deployed ``ModelVersion`` for that
model type purely as the type/architecture label the dashboards group by
(``get_model_performance_summary`` groups by ``ModelVersion.model_type``,
not by exact version) - this also deliberately avoids creating a newer
``ModelVersion`` row that ``get_latest_model_version`` (used by the live
hourly pipeline) could mistakenly pick up in place of the real deployed
model.

Disclosed methodology simplification (weather, never load)
------------------------------------------------------------
Live forecasting calls Open-Meteo's *forecast* endpoint for future weather.
There is no way to retrieve "what a weather forecast issued on that past
date would have said" for historical dates - only the real observed
(archival) weather, which is already sitting in ``weather_observations``.
This backfill uses those real recorded values as the weather input for each
target hour, which is a standard, disclosed backtesting simplification
(effectively assuming perfect weather information) - it never touches the
load/target variable, so it does not leak what is being predicted.

Walk-forward methodology
--------------------------
The available real history is split into fixed-size, chronologically
ordered blocks (``block_hours``, default 24h = one calendar day). For each
block: train fresh on all real data strictly before the block start, then
recursively predict ``horizon_hours`` ahead (reusing
``forecasting_service.recursive_predict``, the exact same recursive
step-and-feed-back logic live forecasting uses). This is the same expanding
window shape as ``app.ml.evaluation.walk_forward``, just repurposed to also
persist real per-hour ``Forecast``/``ForecastScore`` rows instead of only
aggregate CV metrics.
"""
from __future__ import annotations

import datetime as dt
from typing import NamedTuple

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ml.features.pipeline import build_feature_frame
from app.models.forecast import Forecast
from app.models.load_observation import LoadObservation
from app.models.model_version import ModelVersion
from app.models.region import Region
from app.models.weather_observation import WeatherObservation
from app.services import evaluation_service
from app.services.data_service import load_history_frame
from app.services.forecasting_service import get_latest_model_version, recursive_predict
from app.services.training_service import MIN_TRAINING_HOURS, MODEL_FACTORIES

logger = get_logger(__name__)

REAL_LOAD_SOURCES = {"eia"}

DEFAULT_BLOCK_HOURS = 24
DEFAULT_HORIZON_HOURS = 24
DEFAULT_MAX_BACKTEST_DAYS = 45
MIN_BACKTEST_DAYS = 7


class NonRealDataError(Exception):
    """Raised when the region's load history contains anything other than
    real provider data (e.g. synthetic rows) - this backfill refuses to run
    against anything but genuinely real observations."""


class BacktestInfeasibleError(Exception):
    """Raised when there is not enough real history to run even one
    minimally-sized walk-forward block. Never caught-and-faked; callers must
    surface this and stop."""


class WeatherPoint(NamedTuple):
    temperature_c: float
    humidity_percent: float


def inspect_region_history(db: Session, region: Region) -> dict:
    """Real-data-only inspection: counts, date range, and distinct load
    sources for a region. Raises ``NonRealDataError`` if any load
    observation's source is not a known real-provider source.
    """
    load_stats = db.execute(
        select(func.count(), func.min(LoadObservation.timestamp), func.max(LoadObservation.timestamp)).where(
            LoadObservation.region_id == region.id
        )
    ).one()
    load_count, load_earliest, load_latest = load_stats

    weather_stats = db.execute(
        select(func.count(), func.min(WeatherObservation.timestamp), func.max(WeatherObservation.timestamp)).where(
            WeatherObservation.region_id == region.id
        )
    ).one()
    weather_count, weather_earliest, weather_latest = weather_stats

    sources = set(
        db.execute(
            select(LoadObservation.source).where(LoadObservation.region_id == region.id).distinct()
        ).scalars()
    )
    non_real = sources - REAL_LOAD_SOURCES
    if non_real:
        raise NonRealDataError(
            f"Region '{region.name}' load history contains non-real source(s) {sorted(non_real)} "
            f"(expected only {sorted(REAL_LOAD_SOURCES)}). Refusing to run a 'real data only' "
            "evaluation backfill against a region that isn't exclusively real data."
        )

    return {
        "region": region.name,
        "load_count": load_count,
        "load_sources": sorted(sources),
        "load_earliest": load_earliest,
        "load_latest": load_latest,
        "weather_count": weather_count,
        "weather_earliest": weather_earliest,
        "weather_latest": weather_latest,
    }


def plan_backtest_window(
    history_df: pd.DataFrame,
    min_training_hours: int = MIN_TRAINING_HOURS,
    max_days: int = DEFAULT_MAX_BACKTEST_DAYS,
    block_hours: int = DEFAULT_BLOCK_HOURS,
) -> dict:
    """Pure planning step: given the joined real load+weather history
    (ascending by timestamp, already deduplicated by ``load_history_frame``),
    compute the largest feasible backtest window that still reserves
    ``min_training_hours`` of real history before it starts.

    Raises ``BacktestInfeasibleError`` if even one block's worth of backtest
    plus the minimum training reservation doesn't fit in the available data.
    """
    total_rows = len(history_df)
    if total_rows < min_training_hours + block_hours:
        raise BacktestInfeasibleError(
            f"Only {total_rows} real joined load/weather rows available; need at least "
            f"{min_training_hours} (minimum training window) + {block_hours} (one backtest block) = "
            f"{min_training_hours + block_hours} to run any historical backtest at all."
        )

    available_for_backtest_hours = total_rows - min_training_hours
    # Round down to a whole number of blocks so every block is full-sized.
    n_blocks = min(available_for_backtest_hours // block_hours, -(-max_days * 24 // block_hours))
    backtest_hours = n_blocks * block_hours

    backtest_start_idx = total_rows - backtest_hours
    backtest_start = history_df["timestamp"].iloc[backtest_start_idx].to_pydatetime()
    backtest_end = history_df["timestamp"].iloc[-1].to_pydatetime() + dt.timedelta(hours=1)

    return {
        "feasible": True,
        "total_available_rows": total_rows,
        "min_training_hours_reserved": min_training_hours,
        "backtest_start": backtest_start,
        "backtest_end": backtest_end,
        "n_blocks": int(n_blocks),
        "block_hours": block_hours,
        "backtest_days": round(backtest_hours / 24, 2),
    }


def _fit_fresh_model(model_type: str, train_df: pd.DataFrame, country: str):
    """Train a brand-new (never persisted) model instance of ``model_type``
    on ``train_df`` alone. Returns (model, feature_columns, in_sample_residual_std).
    """
    factory = MODEL_FACTORIES[model_type]
    probe = factory()
    feature_columns = probe.feature_columns

    features_df = build_feature_frame(train_df, country=country)
    clean_df = features_df.dropna(subset=feature_columns + ["load_mw"]).reset_index(drop=True)
    if len(clean_df) < MIN_TRAINING_HOURS // 2:
        raise BacktestInfeasibleError(
            f"Only {len(clean_df)} clean rows remain after dropping NaN feature rows for '{model_type}'; "
            "need history for 168h lags before this block's origin."
        )

    model = factory()
    model.fit(clean_df[feature_columns], clean_df["load_mw"])

    # In-sample residual std, used only for this block's prediction-interval
    # width (not for any accuracy metric) - a disclosed simplification vs.
    # production's cross-validated residual_std (see module docstring).
    in_sample_pred = model.predict(clean_df[feature_columns])
    residual_std = float((clean_df["load_mw"].to_numpy() - in_sample_pred).std())

    return model, feature_columns, residual_std


def _weather_lookup(history_df: pd.DataFrame, start: dt.datetime, end: dt.datetime) -> dict:
    window = history_df[(history_df["timestamp"] >= start) & (history_df["timestamp"] < end)]
    return {
        row.timestamp.to_pydatetime() if hasattr(row.timestamp, "to_pydatetime") else row.timestamp: WeatherPoint(
            temperature_c=row.temperature_c, humidity_percent=row.humidity_percent
        )
        for row in window.itertuples()
    }


def run_backtest_for_model(
    db: Session,
    region: Region,
    model_type: str,
    attribution_model_version: ModelVersion,
    full_history_df: pd.DataFrame,
    backtest_start: dt.datetime,
    backtest_end: dt.datetime,
    block_hours: int = DEFAULT_BLOCK_HOURS,
    horizon_hours: int = DEFAULT_HORIZON_HOURS,
) -> dict:
    """Walk forward in ``block_hours`` blocks from ``backtest_start`` to
    ``backtest_end``, training fresh on real data strictly before each block
    and persisting recursive ``horizon_hours``-ahead forecasts for it.
    Idempotent: reuses the same ``uq_forecast_identity`` (region, model
    version, generated_at, target_timestamp) upsert as live forecast
    generation, so re-running this is always safe.
    """
    blocks_run = 0
    blocks_failed: list[str] = []
    inserted_total = 0
    skipped_total = 0

    country = region.country
    cursor = backtest_start
    while cursor < backtest_end:
        block_end = min(cursor + dt.timedelta(hours=block_hours), backtest_end)
        this_horizon = min(horizon_hours, int((block_end - cursor).total_seconds() // 3600))

        train_df = full_history_df[full_history_df["timestamp"] < cursor].reset_index(drop=True)
        if len(train_df) < MIN_TRAINING_HOURS:
            blocks_failed.append(f"{cursor.isoformat()}: insufficient training rows ({len(train_df)})")
            cursor = block_end
            continue

        try:
            model, feature_columns, residual_std = _fit_fresh_model(model_type, train_df, country)
        except BacktestInfeasibleError as exc:
            blocks_failed.append(f"{cursor.isoformat()}: {exc}")
            cursor = block_end
            continue

        working = train_df.tail(24 * 24).reset_index(drop=True)
        weather_by_ts = _weather_lookup(full_history_df, cursor, block_end)

        raw_predictions = recursive_predict(
            model, feature_columns, working, country, cursor, this_horizon, weather_by_ts
        )
        generated_at = cursor

        if raw_predictions:
            target_timestamps = [ts for ts, _ in raw_predictions]
            existing = set(
                db.execute(
                    select(Forecast.target_timestamp).where(
                        Forecast.region_id == region.id,
                        Forecast.model_version_id == attribution_model_version.id,
                        Forecast.generated_at == generated_at,
                        Forecast.target_timestamp.in_(target_timestamps),
                    )
                ).scalars()
            )
            to_insert = [(ts, pred) for ts, pred in raw_predictions if ts not in existing]
            skipped_total += len(raw_predictions) - len(to_insert)

            if to_insert:
                stmt = pg_insert(Forecast).values(
                    [
                        {
                            "region_id": region.id,
                            "model_version_id": attribution_model_version.id,
                            "generated_at": generated_at,
                            "target_timestamp": ts,
                            "horizon_hours": i + 1,
                            "predicted_load_mw": pred,
                            "lower_bound": pred - 1.96 * residual_std,
                            "upper_bound": pred + 1.96 * residual_std,
                        }
                        for i, (ts, pred) in enumerate(raw_predictions)
                        if ts not in existing
                    ]
                )
                stmt = stmt.on_conflict_do_nothing(constraint="uq_forecast_identity")
                db.execute(stmt)
                db.commit()
                inserted_total += len(to_insert)

        blocks_run += 1
        cursor = block_end

    return {
        "model_type": model_type,
        "blocks_run": blocks_run,
        "blocks_failed": blocks_failed,
        "forecasts_inserted": inserted_total,
        "forecasts_skipped_existing": skipped_total,
    }


def run_evaluation_history_backfill(
    db: Session,
    region: Region,
    max_days: int = DEFAULT_MAX_BACKTEST_DAYS,
    block_hours: int = DEFAULT_BLOCK_HOURS,
    horizon_hours: int = DEFAULT_HORIZON_HOURS,
    min_backtest_days: int = MIN_BACKTEST_DAYS,
) -> dict:
    """Full orchestration: inspect -> plan -> backtest every trained model
    type -> score against real actuals -> summarize. Never fabricates data;
    raises (does not silently downgrade) if the region isn't real-data-only
    or there isn't enough history for a minimally meaningful window.
    """
    before = inspect_region_history(db, region)

    full_history_df = load_history_frame(db, region.id)
    plan = plan_backtest_window(
        full_history_df, min_training_hours=MIN_TRAINING_HOURS, max_days=max_days, block_hours=block_hours
    )
    if plan["backtest_days"] < min_backtest_days:
        raise BacktestInfeasibleError(
            f"Only {plan['backtest_days']} days of backtest are feasible after reserving "
            f"{MIN_TRAINING_HOURS} training hours out of {plan['total_available_rows']} available real rows; "
            f"need at least {min_backtest_days} days for a meaningful evaluation history. "
            "Not fabricating additional history to meet this - ingest more real data first."
        )

    model_types = list(MODEL_FACTORIES.keys())
    per_model_results = []
    for model_type in model_types:
        attribution_version = get_latest_model_version(db, model_type=model_type)
        if attribution_version is None:
            per_model_results.append(
                {"model_type": model_type, "skipped": True, "reason": "no trained ModelVersion exists for this type"}
            )
            continue
        result = run_backtest_for_model(
            db, region, model_type, attribution_version, full_history_df,
            plan["backtest_start"], plan["backtest_end"], block_hours=block_hours, horizon_hours=horizon_hours,
        )
        per_model_results.append(result)

    score_result = evaluation_service.score_forecasts(db, region_id=region.id)

    after = inspect_region_history(db, region)
    performance = evaluation_service.get_model_performance_summary(db, region_id=region.id)
    comparison = evaluation_service.get_model_comparison(db, region_id=region.id)
    drift = evaluation_service.get_drift_status(db, region_id=region.id)

    return {
        "region": region.name,
        "before": before,
        "after": after,
        "plan": plan,
        "per_model": per_model_results,
        "newly_scored": score_result["scored"],
        "performance": performance,
        "model_comparison": comparison,
        "drift": drift,
    }


def format_report(report: dict) -> list[str]:
    lines = [
        f"Region: {report['region']}",
        f"Real load observations used: {report['before']['load_count']} "
        f"(sources={report['before']['load_sources']}, {report['before']['load_earliest']} -> {report['before']['load_latest']})",
        f"Real weather observations used: {report['before']['weather_count']} "
        f"({report['before']['weather_earliest']} -> {report['before']['weather_latest']})",
        f"Backtest window: {report['plan']['backtest_start']} -> {report['plan']['backtest_end']} "
        f"({report['plan']['backtest_days']} days, {report['plan']['n_blocks']} blocks of {report['plan']['block_hours']}h)",
    ]
    for m in report["per_model"]:
        if m.get("skipped"):
            lines.append(f"  {m['model_type']}: SKIPPED - {m['reason']}")
        else:
            lines.append(
                f"  {m['model_type']}: {m['blocks_run']} blocks run, "
                f"{m['forecasts_inserted']} forecasts inserted, {m['forecasts_skipped_existing']} skipped (already existed), "
                f"{len(m['blocks_failed'])} blocks failed"
            )
    lines.append(f"Newly scored (this run): {report['newly_scored']}")
    for p in report["performance"]:
        lines.append(
            f"  {p['model_type']}: n={p['forecast_count']} mae={p['mae']} rmse={p['rmse']} "
            f"mape={p['mape']}% smape={p['smape']}%"
        )
    lines.append(f"Best model (lowest MAPE): {report['model_comparison']['best_model']}")
    lines.append(f"Drift status: {report['drift']}")
    return lines
