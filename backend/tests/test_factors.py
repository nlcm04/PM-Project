import numpy as np
import pandas as pd

from app.quant.factors import composite_score, momentum_12_1, sector_neutral_composite_score, sector_neutral_zscore, zscore


def test_zscore_normal_case():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    z = zscore(s)
    assert np.isclose(z.mean(), 0.0)
    assert np.isclose(z.iloc[0], -z.iloc[-1])


def test_zscore_preserves_nan():
    s = pd.Series([1.0, 2.0, np.nan, 4.0])
    z = zscore(s)
    assert np.isnan(z.iloc[2])
    assert not z.iloc[0:2].isna().any()


def test_zscore_constant_series_preserves_nan():
    # std == 0 branch -- a naive fallback could turn the NaN into a fake 0.0
    s = pd.Series([5.0, 5.0, np.nan, 5.0])
    z = zscore(s)
    assert np.isnan(z.iloc[2])
    assert (z.dropna() == 0.0).all()


def test_composite_score_skips_missing_factors_per_row():
    # Mimics a bank: has earnings_yield/book_to_market but not ev_to_ebitda.
    df = pd.DataFrame(
        {
            "earnings_yield": [0.05, 0.08, 0.10, 0.12],
            "ev_to_ebitda": [10.0, 8.0, np.nan, 6.0],
        }
    )
    score = composite_score(df, {"earnings_yield": True, "ev_to_ebitda": False})
    assert not score.isna().any()  # every row has at least one usable factor
    # Row 2 (index 2) is scored from earnings_yield alone, not NaN-poisoned by ev_to_ebitda.
    assert np.isfinite(score.iloc[2])


def test_sector_neutral_zscore_ranks_within_sector_not_across():
    # Bank A is the cheapest bank; RE A is the cheapest real-estate name, but
    # real estate as a whole trades much cheaper than banks here. A global
    # z-score would rank all real-estate names above all banks; sector-neutral
    # should instead rank each name against its own sector peers.
    df = pd.DataFrame(
        {
            "sector": ["Bank", "Bank", "Bank", "Bank", "RE", "RE", "RE", "RE"],
            "earnings_yield": [0.20, 0.15, 0.10, 0.05, 0.02, 0.015, 0.01, 0.005],
        }
    )
    z = sector_neutral_zscore(df, "earnings_yield", min_group_size=4)
    # Best bank (row 0) should score as well within its sector as the best RE name (row 4).
    assert np.isclose(z.iloc[0], z.iloc[4], atol=1e-9)
    # Global z-score would NOT put these two on equal footing.
    global_z = zscore(df["earnings_yield"])
    assert not np.isclose(global_z.iloc[0], global_z.iloc[4], atol=1e-9)


def test_sector_neutral_zscore_falls_back_to_global_for_tiny_sectors():
    df = pd.DataFrame(
        {
            "sector": ["A", "A", "A", "A", "A", "Tiny", "Tiny"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 20.0],
        }
    )
    z = sector_neutral_zscore(df, "value", min_group_size=4)
    global_z = zscore(df["value"])
    # "Tiny" sector has only 2 members (< min_group_size) -- falls back to global.
    assert np.isclose(z.iloc[5], global_z.iloc[5])
    assert np.isclose(z.iloc[6], global_z.iloc[6])


def test_sector_neutral_composite_score_runs_end_to_end():
    df = pd.DataFrame(
        {
            "sector": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "earnings_yield": [0.2, 0.15, 0.1, 0.05, 0.02, 0.015, 0.01, 0.005],
            "ev_to_ebitda": [5.0, 6.0, 7.0, 8.0, 20.0, 21.0, 22.0, 23.0],
        }
    )
    score = sector_neutral_composite_score(df, {"earnings_yield": True, "ev_to_ebitda": False}, min_group_size=4)
    assert not score.isna().any()
    assert len(score) == 8


def test_momentum_12_1_skips_most_recent_month():
    # 300 trading days: first 279 days flat (0% return), last 21 days a sharp
    # -50% drop. 12-1 momentum should be ~0 (it skips the last 21 days), while
    # a naive "trailing 12 month including this month" calc would show the crash.
    n = 300
    returns = pd.DataFrame({"A": [0.0] * (n - 21) + [-0.032] * 21})  # ~-50% over 21 days
    mom = momentum_12_1(returns, lookback_days=252, skip_days=21)
    assert abs(mom["A"]) < 0.01


def test_momentum_12_1_returns_nan_with_insufficient_history():
    returns = pd.DataFrame({"A": [0.01, 0.02]})
    mom = momentum_12_1(returns, lookback_days=252, skip_days=21)
    assert np.isnan(mom["A"])
