import numpy as np
import pandas as pd

from app.quant.order_flow import detect_flow_signal


def _base_series(n=40, seed=0, base_volume=100_000):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2026-01-01", periods=n, freq="B")
    volume = pd.Series(base_volume + rng.normal(0, 5_000, size=n), index=ts).clip(lower=1_000)
    close = pd.Series(100_000 + np.cumsum(rng.normal(0, 500, size=n)), index=ts)
    return ts.to_series().reset_index(drop=True), close.reset_index(drop=True), volume.reset_index(drop=True)


def test_normal_volume_day_is_not_anomalous():
    ts, close, volume = _base_series()
    signal = detect_flow_signal(ts, close, volume)
    assert signal is not None
    assert signal.is_anomalous is False
    assert signal.direction == "NEUTRAL"


def test_large_buy_volume_spike_flags_accumulation():
    ts, close, volume = _base_series()
    volume.iloc[-1] = volume.iloc[:-1].mean() * 6  # ~6x historical average
    close.iloc[-1] = close.iloc[-2] * 1.03  # up day
    signal = detect_flow_signal(ts, close, volume)
    assert signal is not None
    assert signal.is_anomalous is True
    assert signal.direction == "ACCUMULATION"
    assert signal.relative_volume > 3


def test_large_sell_volume_spike_flags_distribution():
    ts, close, volume = _base_series()
    volume.iloc[-1] = volume.iloc[:-1].mean() * 6
    close.iloc[-1] = close.iloc[-2] * 0.97  # down day
    signal = detect_flow_signal(ts, close, volume)
    assert signal is not None
    assert signal.direction == "DISTRIBUTION"


def test_insufficient_history_returns_none():
    ts, close, volume = _base_series(n=3)
    assert detect_flow_signal(ts, close, volume) is None
