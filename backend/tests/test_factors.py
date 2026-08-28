import numpy as np
import pandas as pd

from app.quant.factors import composite_score, zscore


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
