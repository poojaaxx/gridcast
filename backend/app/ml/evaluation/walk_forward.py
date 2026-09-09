"""Walk-forward (expanding window) validation for time series.

Random train/test splits leak information: a model trained on data from
*after* a validation point (e.g. next month's actuals) would see patterns it
could never have known about in production. Instead, each fold trains on all
data strictly before the validation window and validates on the next
contiguous chronological block - exactly mirroring how the model will
actually be used (train on history, predict the near future).

Example with n_folds=3:
    Fold 1: TRAIN [0 .......... t1)   VAL [t1, t1+w)
    Fold 2: TRAIN [0 .......... t2)   VAL [t2, t2+w)
    Fold 3: TRAIN [0 .......... t3)   VAL [t3, t3+w)
where t2 = t1 + w, t3 = t2 + w (the training window expands each fold).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.ml.evaluation.metrics import compute_all_metrics
from app.ml.models.base import BaseForecastModel


@dataclass
class FoldResult:
    fold: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp
    metrics: dict[str, float]
    residuals: np.ndarray = field(default_factory=lambda: np.array([]))


@dataclass
class WalkForwardResult:
    folds: list[FoldResult] = field(default_factory=list)
    mean_metrics: dict[str, float] = field(default_factory=dict)
    std_metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "folds": [
                {
                    "fold": f.fold,
                    "train_start": f.train_start.isoformat(),
                    "train_end": f.train_end.isoformat(),
                    "val_start": f.val_start.isoformat(),
                    "val_end": f.val_end.isoformat(),
                    "metrics": f.metrics,
                }
                for f in self.folds
            ],
            "mean_metrics": self.mean_metrics,
            "std_metrics": self.std_metrics,
        }


def expanding_window_split(n_samples: int, n_folds: int, val_size: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return ``n_folds`` (train_idx, val_idx) pairs with an expanding training
    window and fixed-size, chronologically ordered, non-overlapping validation
    blocks.
    """
    min_train = n_samples - n_folds * val_size
    if min_train <= 0:
        raise ValueError(
            f"Not enough samples ({n_samples}) for {n_folds} folds of size {val_size}. "
            f"Need at least {n_folds * val_size + 1} samples."
        )

    splits = []
    for i in range(n_folds):
        train_end = min_train + i * val_size
        val_end = train_end + val_size
        splits.append((np.arange(0, train_end), np.arange(train_end, val_end)))
    return splits


def run_walk_forward_validation(
    df: pd.DataFrame,
    model_factory,
    feature_columns: list[str],
    target_col: str = "load_mw",
    timestamp_col: str = "timestamp",
    n_folds: int = 5,
    val_size_hours: int = 24 * 30,
) -> WalkForwardResult:
    """``df`` must already be feature-engineered, NaN-free in the required
    columns, and sorted ascending by ``timestamp_col`` with a fresh
    RangeIndex. ``model_factory`` is a zero-arg callable returning a fresh,
    untrained ``BaseForecastModel`` instance (a new one per fold - models must
    never be reused across folds).
    """
    df = df.reset_index(drop=True)
    splits = expanding_window_split(len(df), n_folds=n_folds, val_size=val_size_hours)

    result = WalkForwardResult()
    all_metrics: list[dict[str, float]] = []

    for fold_idx, (train_idx, val_idx) in enumerate(splits, start=1):
        train_df = df.iloc[train_idx]
        val_df = df.iloc[val_idx]

        model: BaseForecastModel = model_factory()
        model.fit(train_df[feature_columns], train_df[target_col])
        predictions = model.predict(val_df[feature_columns])

        actuals = val_df[target_col].to_numpy()
        metrics = compute_all_metrics(actuals, predictions)
        all_metrics.append(metrics)

        result.folds.append(
            FoldResult(
                fold=fold_idx,
                train_start=train_df[timestamp_col].iloc[0],
                train_end=train_df[timestamp_col].iloc[-1],
                val_start=val_df[timestamp_col].iloc[0],
                val_end=val_df[timestamp_col].iloc[-1],
                metrics=metrics,
                residuals=actuals - predictions,
            )
        )

    metric_keys = [k for k in all_metrics[0].keys() if k != "n"]
    result.mean_metrics = {k: float(np.mean([m[k] for m in all_metrics])) for k in metric_keys}
    result.std_metrics = {k: float(np.std([m[k] for m in all_metrics])) for k in metric_keys}
    return result


def pooled_residual_std(result: WalkForwardResult) -> float:
    """Standard deviation of residuals pooled across all validation folds -
    used to derive simple Gaussian prediction intervals for live forecasts.
    """
    residuals = np.concatenate([f.residuals for f in result.folds if len(f.residuals)])
    if residuals.size == 0:
        return 0.0
    return float(np.std(residuals))
