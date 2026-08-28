import numpy as np
import pandas as pd

from app.quant.screener import screen_universe


def _fundamentals_row(asset_id, sector, **overrides):
    row = {
        "asset_id": asset_id,
        "sector": sector,
        "warning_status": "NONE",
        "margin_eligible": True,
        "earnings_yield": 0.1,
        "book_to_market": 0.5,
        "ev_to_ebitda": 8.0,
        "roic": 0.15,
        "cfo_to_assets": 0.05,
        "interest_coverage": 5.0,
        "auditor_opinion": "UNQUALIFIED",
        "filing_on_time": True,
    }
    row.update(overrides)
    return row


def test_missing_interest_coverage_is_not_disqualifying():
    # Regression test: a bank with no reported interest_coverage (vnstock
    # doesn't provide this ratio for banks) must NOT be disqualified purely
    # for missing data -- an earlier version of this check treated a missing
    # value as "0, therefore fails the >=3x threshold".
    df = pd.DataFrame(
        [
            _fundamentals_row(1, "Financials", interest_coverage=np.nan, ev_to_ebitda=np.nan, roic=np.nan, cfo_to_assets=np.nan),
            _fundamentals_row(2, "Financials", interest_coverage=np.nan, ev_to_ebitda=np.nan, roic=np.nan, cfo_to_assets=np.nan),
            _fundamentals_row(3, "Financials", interest_coverage=np.nan, ev_to_ebitda=np.nan, roic=np.nan, cfo_to_assets=np.nan),
            _fundamentals_row(4, "Financials", interest_coverage=np.nan, ev_to_ebitda=np.nan, roic=np.nan, cfo_to_assets=np.nan),
        ]
    )
    scored = screen_universe(df)
    assert len(scored) == 4
    assert not scored["composite_score"].isna().any()


def test_low_interest_coverage_is_still_disqualifying():
    df = pd.DataFrame([_fundamentals_row(1, "Industrials", interest_coverage=1.0)])
    scored = screen_universe(df)
    assert scored.empty


def test_scoring_is_sector_neutral():
    # A cheap bank should rank alongside a cheap real-estate name, not below
    # it just because real estate as a whole trades at lower multiples here.
    rows = []
    for i, ey in enumerate([0.20, 0.15, 0.10, 0.05]):
        rows.append(_fundamentals_row(i, "Bank", earnings_yield=ey))
    for i, ey in enumerate([0.02, 0.015, 0.01, 0.005]):
        rows.append(_fundamentals_row(10 + i, "RE", earnings_yield=ey))
    df = pd.DataFrame(rows)

    scored = screen_universe(df)
    best_bank = scored[scored["asset_id"] == 0]["composite_score"].iloc[0]
    best_re = scored[scored["asset_id"] == 10]["composite_score"].iloc[0]
    assert np.isclose(best_bank, best_re, atol=1e-6)


def test_missing_sector_column_falls_back_to_other():
    df = pd.DataFrame([_fundamentals_row(1, "Industrials")]).drop(columns=["sector"])
    scored = screen_universe(df)
    assert list(scored["sector"]) == ["Other"]
