"""Model training orchestration: feature build -> walk-forward validation ->
final fit on all available history -> artifact + ModelVersion persistence.
"""
from __future__ import annotations

import os
from typing import Callable

import joblib
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.evaluation.walk_forward import pooled_residual_std, run_walk_forward_validation
from app.ml.features.pipeline import build_feature_frame
from app.ml.models.base import BaseForecastModel
from app.ml.models.lightgbm_model import LightGBMModel
from app.ml.models.linear_model import LinearRegressionModel
from app.ml.models.seasonal_naive import SeasonalNaiveModel
from app.models.model_version import ModelVersion
from app.models.region import Region
from app.services.data_service import load_history_frame
from app.utils.time import utcnow

logger = get_logger(__name__)

MODEL_FACTORIES: dict[str, Callable[[], BaseForecastModel]] = {
    "seasonal_naive": SeasonalNaiveModel,
    "linear_regression": LinearRegressionModel,
    "lightgbm": LightGBMModel,
}

MIN_TRAINING_HOURS = 24 * 60  # ~2 months minimum to allow a few validation folds


class InsufficientDataError(Exception):
    pass


def _pick_fold_config(n_rows: int) -> tuple[int, int]:
    """Choose (n_folds, val_size_hours) that fit within available data."""
    val_size_hours = max(24, min(24 * 14, n_rows // 8))
    n_folds = max(2, min(5, (n_rows // val_size_hours) - 1))
    if n_folds * val_size_hours >= n_rows:
        raise InsufficientDataError(
            f"Not enough clean training rows ({n_rows}) to run walk-forward validation."
        )
    return n_folds, val_size_hours


def train_model(db: Session, region: Region, model_type: str) -> ModelVersion:
    if model_type not in MODEL_FACTORIES:
        raise ValueError(f"Unknown model_type '{model_type}'. Options: {list(MODEL_FACTORIES)}")

    raw_df = load_history_frame(db, region.id)
    if len(raw_df) < MIN_TRAINING_HOURS:
        raise InsufficientDataError(
            f"Region '{region.name}' has only {len(raw_df)} joined load/weather rows; "
            f"need at least {MIN_TRAINING_HOURS} to train."
        )

    features_df = build_feature_frame(raw_df, country=region.country)

    factory = MODEL_FACTORIES[model_type]
    probe_model = factory()
    feature_columns = probe_model.feature_columns

    clean_df = features_df.dropna(subset=feature_columns + ["load_mw"]).reset_index(drop=True)
    if len(clean_df) < MIN_TRAINING_HOURS // 2:
        raise InsufficientDataError(
            f"Only {len(clean_df)} rows remain after dropping NaN feature rows (need history for "
            "168h lags); ingest more data before training."
        )

    n_folds, val_size_hours = _pick_fold_config(len(clean_df))
    logger.info(
        "Running walk-forward validation for %s: %d folds x %dh validation windows on %d rows",
        model_type, n_folds, val_size_hours, len(clean_df),
    )
    wf_result = run_walk_forward_validation(
        clean_df, factory, feature_columns, n_folds=n_folds, val_size_hours=val_size_hours
    )
    residual_std = pooled_residual_std(wf_result)

    logger.info(
        "%s walk-forward mean metrics: %s", model_type,
        {k: round(v, 3) for k, v in wf_result.mean_metrics.items()},
    )

    # Final production model is fit on ALL available clean history.
    final_model = factory()
    final_model.fit(clean_df[feature_columns], clean_df["load_mw"])

    version = f"{model_type}_{utcnow():%Y%m%d_%H%M%S}"
    os.makedirs(settings.model_artifact_dir, exist_ok=True)
    artifact_path = os.path.join(settings.model_artifact_dir, f"{version}.joblib")
    joblib.dump(final_model, artifact_path)

    metrics_json = {
        "walk_forward": wf_result.to_dict(),
        "mean_metrics": wf_result.mean_metrics,
        "std_metrics": wf_result.std_metrics,
        "residual_std": residual_std,
        "n_folds": n_folds,
        "val_size_hours": val_size_hours,
        "training_rows": len(clean_df),
    }

    model_version = ModelVersion(
        model_name=model_type,
        version=version,
        model_type=model_type,
        training_start=clean_df["timestamp"].iloc[0].to_pydatetime(),
        training_end=clean_df["timestamp"].iloc[-1].to_pydatetime(),
        metrics_json=metrics_json,
        artifact_path=artifact_path,
        feature_columns=feature_columns,
    )
    db.add(model_version)
    db.commit()
    db.refresh(model_version)

    logger.info("Saved model version '%s' (id=%s) -> %s", version, model_version.id, artifact_path)
    return model_version


def load_model_artifact(model_version: ModelVersion) -> BaseForecastModel:
    if not model_version.artifact_path or not os.path.exists(model_version.artifact_path):
        raise FileNotFoundError(f"Artifact not found for model version '{model_version.version}'.")
    return joblib.load(model_version.artifact_path)
