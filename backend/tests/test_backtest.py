import numpy as np
import pandas as pd

from app.quant.backtest import annualized_sharpe, compare_against_alternatives, walk_forward_backtest


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
