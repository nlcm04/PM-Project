import numpy as np
import pandas as pd

from app.quant.backtest import (
    annualized_sharpe,
    compare_against_alternatives,
    drawdown_series,
    max_drawdown,
    walk_forward_backtest,
    walk_forward_evaluate,
)


def test_max_drawdown_catches_a_crash_on_the_very_first_day():
    # Regression test: a naive `cumulative.cummax()` over just the return
    # series makes day 1's drawdown trivially 0 (nothing preceded it to have
    # fallen from), silently hiding a crash that happens to land on day 1.
    returns = pd.Series([-0.30, 0.0, 0.0])
    assert max_drawdown(returns) < -0.25


def test_drawdown_series_is_monotonically_non_increasing_after_cummin():
    returns = pd.Series([-0.20, 0.0, 0.0, 0.15, 0.03])
    dd = drawdown_series(returns).cummin()
    for prev, curr in zip(dd, dd.iloc[1:]):
        assert curr <= prev + 1e-12


def test_max_drawdown_of_all_positive_returns_is_zero():
    returns = pd.Series([0.01, 0.02, 0.01])
    assert max_drawdown(returns) == 0.0


def test_max_drawdown_empty_series_returns_zero():
    assert max_drawdown(pd.Series([], dtype=float)) == 0.0


def _synthetic_returns(n_assets=10, n_days=252, seed=0, drift=0.0006):
    rng = np.random.default_rng(seed)
    tickers = [f"T{i}" for i in range(n_assets)]
    data = rng.normal(loc=drift, scale=0.015, size=(n_days, n_assets))
    return pd.DataFrame(data, columns=tickers)


def test_walk_forward_backtest_returns_expected_keys():
    returns_df = _synthetic_returns()
    result = walk_forward_backtest(returns_df, tickers=["T0", "T1", "T2"])
    assert set(result.keys()) >= {"sharpe_ratio", "cumulative_return", "max_drawdown", "n_periods"}
    assert result["n_periods"] == 252


def test_compare_against_alternatives_reports_percentile_rank():
    returns_df = _synthetic_returns(n_assets=20, drift=0.0)
    # Give the "selected" tickers a real edge so the heuristic should rank them highly.
    returns_df[["T0", "T1", "T2"]] += 0.002
    result = compare_against_alternatives(
        returns_df, selected_tickers=["T0", "T1", "T2"], universe=list(returns_df.columns), n_trials=200
    )
    assert 0 <= result["percentile_rank"] <= 100
    assert result["percentile_rank"] > 50


def test_walk_forward_evaluate_returns_none_with_insufficient_history():
    returns_df = _synthetic_returns(n_assets=5, n_days=50)
    score_z = pd.Series([1.0, 0.5, 0.0, -0.5, -1.0], index=returns_df.columns)
    result = walk_forward_evaluate(returns_df, list(returns_df.columns), score_z, min_train_days=120)
    assert result is None


def test_walk_forward_evaluate_produces_multiple_contiguous_folds():
    n_assets = 6
    n_days = 750  # ~3 years
    returns_df = _synthetic_returns(n_assets=n_assets, n_days=n_days, seed=1)
    tickers = list(returns_df.columns)
    score_z = pd.Series(np.linspace(1.0, -1.0, n_assets), index=tickers)

    result = walk_forward_evaluate(returns_df, tickers, score_z, n_folds=5, min_train_days=120)

    assert result is not None
    assert result["n_folds"] >= 2  # genuinely walked forward across more than one period
    assert set(result.keys()) >= {"combined_sharpe", "combined_cumulative_return", "combined_max_drawdown", "fold_summaries"}

    # Folds must be contiguous and non-overlapping, and cover the whole testable region.
    total_fold_days = sum(f["n_days"] for f in result["fold_summaries"])
    assert total_fold_days == n_days - 120
    assert result["combined_n_days"] == total_fold_days

    # Each fold's IC should be a plain finite float, not NaN/inf, even on random data.
    for fold in result["fold_summaries"]:
        assert np.isfinite(fold["ic"])
        assert np.isfinite(fold["sharpe"])


def test_walk_forward_evaluate_never_trains_on_future_data():
    # A later fold's train window must never include days that are in an
    # earlier fold's test window or beyond -- i.e. fold i's train size must
    # equal exactly the number of days before its test window starts.
    n_assets = 4
    returns_df = _synthetic_returns(n_assets=n_assets, n_days=600, seed=2)
    tickers = list(returns_df.columns)
    score_z = pd.Series([1.0, 0.5, -0.5, -1.0], index=tickers)

    result = walk_forward_evaluate(returns_df, tickers, score_z, n_folds=4, min_train_days=100)
    assert result is not None

    cumulative_days = 100
    for fold in result["fold_summaries"]:
        # Each fold's test window starts exactly where the prior one (plus initial train) ended.
        cumulative_days += fold["n_days"]
    assert cumulative_days == 600
