from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from app.ml.features.lag_features import add_lag_features, add_rolling_features


def _make_series(n_hours: int) -> pd.DataFrame:
    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    timestamps = [start + dt.timedelta(hours=i) for i in range(n_hours)]
    load = np.arange(n_hours, dtype=float)
    return pd.DataFrame({"timestamp": timestamps, "load_mw": load})


def test_lag_features_use_only_past_data():
    df = _make_series(200)
    result = add_lag_features(df)

    assert pd.isna(result["load_lag_1"].iloc[0])
    for i in range(1, len(result)):
        assert result["load_lag_1"].iloc[i] == df["load_mw"].iloc[i - 1]
    for i in range(168, len(result)):
        assert result["load_lag_168"].iloc[i] == df["load_mw"].iloc[i - 168]


def test_rolling_features_do_not_leak_future_information():
    df = _make_series(300)
    result = add_rolling_features(df)

    # rolling_mean_24 at row i must equal the mean of load[i-24:i-1], never load[i] itself.
    row = 250
    expected = df["load_mw"].iloc[row - 24 : row].mean()
    assert np.isclose(result["rolling_mean_24"].iloc[row], expected)

    # Prove no leakage: mutating the "current" value must not change the
    # rolling statistic computed for that same row.
    mutated = df.copy()
    mutated.loc[row, "load_mw"] = 10_000_000.0
    result_mutated = add_rolling_features(mutated)
    assert np.isclose(result_mutated["rolling_mean_24"].iloc[row], result["rolling_mean_24"].iloc[row])
