"""Forecast accuracy metrics with safe handling of near-zero actuals."""
from __future__ import annotations

import numpy as np

EPSILON = 1.0  # MW - avoids exploding percentage errors near-zero load


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def mape(actual: np.ndarray, predicted: np.ndarray, epsilon: float = EPSILON) -> float:
    """Mean Absolute Percentage Error, protected against divide-by-zero via
    ``max(abs(actual), epsilon)`` in the denominator. Returned as a percentage.
    """
    denom = np.maximum(np.abs(actual), epsilon)
    return float(np.mean(np.abs(actual - predicted) / denom) * 100)


def smape(actual: np.ndarray, predicted: np.ndarray, epsilon: float = EPSILON) -> float:
    """Symmetric MAPE, also epsilon-protected. Returned as a percentage."""
    denom = np.maximum((np.abs(actual) + np.abs(predicted)) / 2, epsilon)
    return float(np.mean(np.abs(actual - predicted) / denom) * 100)


def compute_all_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    return {
        "mae": mae(actual, predicted),
        "rmse": rmse(actual, predicted),
        "mape": mape(actual, predicted),
        "smape": smape(actual, predicted),
        "n": int(len(actual)),
    }
