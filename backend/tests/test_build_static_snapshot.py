import numpy as np
import pandas as pd

from scripts.build_static_snapshot import build_performance_series


def test_build_performance_series_max_drawdown_is_running_worst_not_current():
    # Returns: down 20%, flat, then recover most of the way back up. The
    # LAST day's current drawdown-from-peak is small, but the worst point
    # (day 1) was a real ~20% drawdown -- max_drawdown must reflect that
    # worst point throughout, not reset to "today's" drawdown once price
    # recovers.
    returns = pd.Series([-0.20, 0.0, 0.0, 0.15, 0.03])
    snapshots = build_performance_series(returns, {}, {})

    assert len(snapshots) == 5
    # Day 1 (the crash) should show roughly -20% drawdown.
    assert snapshots[0]["max_drawdown"] < -0.15
    # By the last day, price has partly recovered (current drawdown from
    # peak is smaller than -20%), but max_drawdown must still report the
    # worst point seen so far, not the smaller current one.
    assert snapshots[-1]["max_drawdown"] <= snapshots[0]["max_drawdown"] + 1e-9
    assert snapshots[-1]["max_drawdown"] < -0.15


def test_build_performance_series_max_drawdown_never_improves_over_time():
    rng = np.random.default_rng(0)
    returns = pd.Series(rng.normal(0.0002, 0.02, size=60))
    snapshots = build_performance_series(returns, {}, {})
    drawdowns = [s["max_drawdown"] for s in snapshots]
    # A running "worst so far" series must be monotonically non-increasing.
    for prev, curr in zip(drawdowns, drawdowns[1:]):
        assert curr <= prev + 1e-9


def test_build_performance_series_returns_empty_for_none_input():
    assert build_performance_series(None, {}, {}) == []


def test_build_performance_series_last_day_carries_factor_exposures_and_diagnostics():
    returns = pd.Series([0.01, -0.02, 0.03])
    exposures = {"momentum": 0.5}
    diagnostics = {"note": "insufficient observations"}
    snapshots = build_performance_series(returns, exposures, diagnostics)

    assert snapshots[0]["factor_exposures"] == {}
    assert snapshots[-1]["factor_exposures"] == exposures
    assert snapshots[-1]["diagnostics"] == diagnostics
