from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.evaluation.walk_forward import expanding_window_split
from app.ml.models.seasonal_naive import SeasonalNaiveModel


def test_seasonal_naive_returns_previous_week_value():
    lag_168_values = np.array([100.0, 200.0, 300.0, 400.0])
    X = pd.DataFrame({"load_lag_168": lag_168_values})
    model = SeasonalNaiveModel().fit(X, pd.Series([0, 0, 0, 0]))

    predictions = model.predict(X)

    assert np.array_equal(predictions, lag_168_values)


def test_expanding_window_splits_preserve_chronological_ordering():
    n_samples, n_folds, val_size = 1000, 4, 100
    splits = expanding_window_split(n_samples, n_folds=n_folds, val_size=val_size)

    assert len(splits) == n_folds

    previous_val_end = None
    for train_idx, val_idx in splits:
        # Training window always starts at the beginning and expands.
        assert train_idx[0] == 0
        # Every training sample must chronologically precede every validation sample.
        assert train_idx.max() < val_idx.min()
        # Validation blocks are contiguous and fixed-size.
        assert len(val_idx) == val_size
        if previous_val_end is not None:
            assert val_idx.min() == previous_val_end
        previous_val_end = val_idx.max() + 1

    # Training window strictly expands fold over fold.
    train_sizes = [len(train_idx) for train_idx, _ in splits]
    assert train_sizes == sorted(train_sizes)
    assert len(set(train_sizes)) == n_folds
