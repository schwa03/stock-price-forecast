import numpy as np
import pandas as pd

from features import FEATURE_NAMES, compute_feature_frame, latest_feature_vector


def _make_price_series(n: int) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(42)
    prices = 1000 + np.cumsum(rng.normal(0, 5, n))
    close = pd.Series(prices, index=pd.date_range("2024-01-01", periods=n, freq="B"))
    volume = pd.Series(rng.integers(1000, 5000, n), index=close.index)
    return close, volume


def test_compute_feature_frame_has_expected_columns():
    close, volume = _make_price_series(150)
    frame = compute_feature_frame(close, volume)
    assert list(frame.columns) == FEATURE_NAMES
    assert len(frame) == len(close)


def test_latest_feature_vector_none_when_insufficient_history():
    close, volume = _make_price_series(30)
    assert latest_feature_vector(close, volume) is None


def test_latest_feature_vector_returns_all_features_with_enough_history():
    close, volume = _make_price_series(150)
    vec = latest_feature_vector(close, volume)
    assert vec is not None
    assert set(vec.keys()) == set(FEATURE_NAMES)
    assert all(isinstance(v, float) for v in vec.values())
