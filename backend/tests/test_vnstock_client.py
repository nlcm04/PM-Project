import pandas as pd

from app.data.vnstock_client import _latest_period_column, extract_latest_ratios


def test_latest_period_column_picks_most_recent_and_ignores_duplicate_suffix():
    # Mirrors the real shape returned live by Finance(source="KBS").ratio():
    # out-of-order columns, plus a pandas-suffixed duplicate for one quarter.
    columns = ["item", "item_id", "2026-Q2", "2025-Q4", "2026-Q1", "2025-Q4_1"]
    assert _latest_period_column(columns) == "2026-Q2"


def test_latest_period_column_returns_none_when_no_period_columns():
    assert _latest_period_column(["item", "item_id"]) is None


def _synthetic_ratio_table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "item": ["P/E", "P/B", "EV/EBITDA", "ROCE", "Interest coverage", "CFO/Assets", "Beta"],
            "item_id": [
                "pe_ratio",
                "pb_ratio",
                "ev_ebitda",
                "return_on_capital_employed_roce",
                "interest_coverage",
                "cash_return_to_assets",
                "beta",
            ],
            "2025-Q4": [10.0, 5.0, 100.0, 200.0, 300.0, 400.0, 500.0],  # stale duplicate, must be ignored
            "2026-Q1": [12.5, 2.0, 8.0, 0.15, 6.0, 0.10, 1.1],
        }
    )


def test_extract_latest_ratios_maps_and_inverts_pe_pb():
    result = extract_latest_ratios(_synthetic_ratio_table())
    assert result["period_label"] == "2026-Q1"
    assert result["earnings_yield"] == 1 / 12.5
    assert result["book_to_market"] == 1 / 2.0
    assert result["ev_to_ebitda"] == 8.0
    assert result["roic"] == 0.15
    assert result["cfo_to_assets"] == 0.10
    assert result["interest_coverage"] == 6.0


def test_extract_latest_ratios_raises_without_period_columns():
    df = pd.DataFrame({"item": ["P/E"], "item_id": ["pe_ratio"]})
    try:
        extract_latest_ratios(df)
        assert False, "expected ValueError"
    except ValueError:
        pass
