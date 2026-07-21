import pandas as pd

import backtest_engine


def test_run_backtest_returns_none_for_empty_data(monkeypatch):
    monkeypatch.setattr(backtest_engine.yf, "download", lambda *a, **k: pd.DataFrame())
    assert backtest_engine.run_backtest("0000") is None


def test_run_backtest_returns_none_for_short_history(monkeypatch):
    short_df = pd.DataFrame({
        "Open": [100.0] * 10, "High": [101.0] * 10, "Low": [99.0] * 10,
        "Close": [100.0] * 10, "Volume": [1000] * 10,
    }, index=pd.date_range("2026-01-01", periods=10))
    monkeypatch.setattr(backtest_engine.yf, "download", lambda *a, **k: short_df)
    assert backtest_engine.run_backtest("0000") is None
