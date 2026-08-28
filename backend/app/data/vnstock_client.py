"""Thin wrapper around the `vnstock` package (verified live against vnstock 4.0.7).

Uses the current `vnstock.api.*` class-based interface -- the older
`Vnstock().stock(...)` facade is deprecated by the upstream project (see its own
runtime deprecation notice) and is not used here. Everything that touches the
package is isolated in this module so a future vnstock upgrade only requires
changes here, not throughout the quant engine.

Known gap (documented, not silently guessed around): vnstock's `Finance.ratio()`
returns a long-format table keyed by a free-text `item_en` label, and neither it
nor `Company.overview()` expose auditor opinion, on-time filing status, or the
HOSE warning/special-control list. Those governance fields in
`fundamentals_quarterly` are NOT auto-populated from vnstock -- they need a
manual or separately-sourced feed (e.g. HOSE's own disclosure portal) until a
reliable free API for them is identified. `screen_universe()` will simply treat
unset governance fields as disqualifying (fail closed) rather than assume clean.
"""

from __future__ import annotations

import pandas as pd

from app.core.config import get_settings

settings = get_settings()


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
    """Raw long-format financial-ratio table (columns: item, item_en, item_id, <period columns>).

    Callers must look up specific rows by `item_en` (e.g. "ROE (%)") -- the exact label set
    is source-dependent, so inspect a live pull before wiring a new ratio into the screener.
    """
    from vnstock.api.financial import Finance

    return Finance(symbol=ticker, source=settings.vnstock_source, period=period).ratio()


def get_company_overview(ticker: str) -> dict:
    """Company profile (sector, market cap, foreign ownership %, etc.). Does NOT include
    auditor opinion or filing status -- see module docstring.
    """
    from vnstock.api.company import Company

    return Company(symbol=ticker, source=settings.vnstock_source).overview().iloc[0].to_dict()
