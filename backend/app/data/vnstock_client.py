"""Thin wrapper around the `vnstock` package (verified live against vnstock 4.0.7).

Uses the current `vnstock.api.*` class-based interface -- the older
`Vnstock().stock(...)` facade is deprecated by the upstream project (see its own
runtime deprecation notice) and is not used here. Everything that touches the
package is isolated in this module so a future vnstock upgrade only requires
changes here, not throughout the quant engine.

Known bug in the upstream package (verified live, not assumed): `Finance.ratio()`
on the VCI source returns stale, mislabeled period columns -- every quarter
came back headed "2018" regardless of what was requested. The KBS source
returns correct, current-quarter data with stable English `item_id` keys
instead, so `get_fundamentals` / `get_raw_ratio_table` use KBS unconditionally
(see `_FUNDAMENTALS_SOURCE`), independent of `settings.vnstock_source`.

Known gap (documented, not silently guessed around): neither `Finance.ratio()`
nor `Company.overview()` expose auditor opinion, on-time filing status, or the
HOSE warning/special-control list. Those governance fields in
`fundamentals_quarterly` are NOT auto-populated from vnstock -- they need a
manual or separately-sourced feed (e.g. HOSE's own disclosure portal) until a
reliable free API for them is identified. `screen_universe()` will simply treat
unset governance fields as disqualifying (fail closed) rather than assume clean.
"""

from __future__ import annotations

import re

import pandas as pd

from app.core.config import get_settings

settings = get_settings()

# `Finance.ratio()` on the configured `settings.vnstock_source` (VCI) returns
# stale/mislabeled period columns as of vnstock 4.0.7 -- verified live: every
# quarter's column header came back "2018", regardless of the actual period
# requested. `KBS` was verified live to return correctly-labeled, current-quarter
# data instead, with stable English snake_case `item_id` keys (VCI's item_en
# column is unpopulated). Fundamentals are hard-coded to KBS for that reason,
# independent of the OHLCV/listing/trading source configured elsewhere.
_FUNDAMENTALS_SOURCE = "KBS"

# item_id -> friendly name, verified live against a real Finance(source="KBS").ratio() pull.
_RATIO_ITEM_MAP = {
    "pe_ratio": "pe_ratio",
    "pb_ratio": "pb_ratio",
    "ev_ebitda": "ev_ebitda",
    "return_on_capital_employed_roce": "roce",  # closest available proxy for ROIC
    "interest_coverage": "interest_coverage",
    "cash_return_to_assets": "cfo_to_assets",
}


def _latest_period_column(columns: list[str]) -> str | None:
    """Pick the most recent quarter column.

    vnstock's KBS `ratio()` output can contain duplicate columns for the same
    quarter (pandas suffixes repeats as `_1`, `_2`, ... on read) -- verified
    live. We match the `YYYY-Qn` base label, ignore any numeric suffix, and
    take the chronologically latest one.
    """
    candidates = []
    for col in columns:
        m = re.match(r"^(\d{4})-Q([1-4])(?:_\d+)?$", col)
        if m:
            candidates.append((int(m.group(1)), int(m.group(2)), col))
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], t[1]))
    return candidates[-1][2]


def extract_latest_ratios(raw: pd.DataFrame) -> dict:
    """Pure mapping from a raw `Finance.ratio()` dataframe to the value/quality
    fields used by `fundamentals_quarterly`. Split out from `get_fundamentals`
    so it's unit-testable without a network call.
    """
    latest_col = _latest_period_column(list(raw.columns))
    if latest_col is None:
        raise ValueError(f"No parsable 'YYYY-Qn' period column in ratio() output: {list(raw.columns)}")

    by_item_id = raw.set_index("item_id")[latest_col]
    values = {name: by_item_id.get(item_id) for item_id, name in _RATIO_ITEM_MAP.items()}

    pe, pb = values.get("pe_ratio"), values.get("pb_ratio")
    return {
        "period_label": latest_col,
        "earnings_yield": (1 / pe) if pe else None,
        "book_to_market": (1 / pb) if pb else None,
        "ev_to_ebitda": values.get("ev_ebitda"),
        "roic": values.get("roce"),
        "cfo_to_assets": values.get("cfo_to_assets"),
        "interest_coverage": values.get("interest_coverage"),
    }


def get_hose_universe() -> list[str]:
    """Return all tickers listed on HOSE.

    vnstock's `exchange` column uses the exchange's own ticker code "HSX" for
    HOSE (verified live against vnstock 4.0.7), not the literal string "HOSE".
    """
    from vnstock.api.listing import Listing

    df = Listing(source=settings.vnstock_source).symbols_by_exchange()
    hose = df[df["exchange"] == "HSX"]
    return sorted(hose["symbol"].unique().tolist())


def get_ohlcv(ticker: str, start: str, end: str, interval: str = "1D") -> pd.DataFrame:
    """Historical OHLCV. Returns columns: time, open, high, low, close, volume."""
    from vnstock.api.quote import Quote

    df = Quote(symbol=ticker, source=settings.vnstock_source).history(start=start, end=end, interval=interval)
    return df.rename(columns=str.lower)


def get_reference_price_band(ticker: str) -> dict[str, float]:
    """Live reference/ceiling/floor price from the trading board, for the ±7% price-band check.
    Also returns same-day foreign buy/sell value as a best-effort institutional-flow input --
    this is a live snapshot, not a historical series.
    """
    from vnstock.api.trading import Trading

    board = Trading(symbol=ticker, source=settings.vnstock_source).price_board([ticker])
    row = board.iloc[0]
    return {
        "ref_price": float(row[("listing", "ref_price")]),
        "ceiling": float(row[("listing", "ceiling")]),
        "floor": float(row[("listing", "floor")]),
        "foreign_buy_value": float(row[("match", "foreign_buy_value")]) if ("match", "foreign_buy_value") in row else None,
        "foreign_sell_value": float(row[("match", "foreign_sell_value")]) if ("match", "foreign_sell_value") in row else None,
    }


def get_raw_ratio_table(ticker: str, period: str = "quarter") -> pd.DataFrame:
    """Raw long-format financial-ratio table (columns: item, item_id, <period columns>),
    pulled from the KBS source -- see `_FUNDAMENTALS_SOURCE` docstring above.
    """
    from vnstock.api.financial import Finance

    return Finance(symbol=ticker, source=_FUNDAMENTALS_SOURCE, period=period, get_all=True).ratio()


def get_fundamentals(ticker: str, period: str = "quarter") -> dict:
    """Value/quality ratios for the most recent available period.

    Returns: period_label, earnings_yield, book_to_market, ev_to_ebitda, roic
    (ROCE proxy), cfo_to_assets, interest_coverage. Does NOT include
    auditor_opinion / filing_on_time -- see module docstring.

    Caveat observed live (not fully resolved): `cfo_to_assets` for the most
    recent quarter came back as exactly 0.0 for both VNM and VIC, while an
    earlier quarter for the same item/ticker was a real, non-zero, negative
    number. Zero CFO/Assets is implausible for a real operating company two
    quarters running, so this likely means "not yet reported for this interim
    period" rather than a true zero -- but that's inferred, not confirmed
    against vnstock's own docs. Treat a 0.0 here with suspicion, especially
    since the spec's CFO/Assets > 0 governance check would wrongly disqualify
    a healthy company on an unreported-not-actually-zero value.
    """
    return extract_latest_ratios(get_raw_ratio_table(ticker, period))


def get_company_overview(ticker: str) -> dict:
    """Company profile (sector, market cap, foreign ownership %, etc.). Does NOT include
    auditor opinion or filing status -- see module docstring.
    """
    from vnstock.api.company import Company

    return Company(symbol=ticker, source=settings.vnstock_source).overview().iloc[0].to_dict()
