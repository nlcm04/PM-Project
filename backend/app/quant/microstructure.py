"""HOSE market-microstructure constraints: long-only, 100-share lots, ±7% price bands,
and T+2 / T+1.5 settlement bucketing."""

from __future__ import annotations

import math
from datetime import date, timedelta

LOT_SIZE = 100
PRICE_BAND_PCT = 0.07


def round_to_lot(quantity: float, lot_size: int = LOT_SIZE) -> int:
    """Floor to the nearest valid board lot. Never rounds up (would overspend)."""
    return int(math.floor(quantity / lot_size) * lot_size)


def shares_affordable(cash: float, price: float, lot_size: int = LOT_SIZE) -> int:
    if price <= 0:
        return 0
    return round_to_lot(cash / price, lot_size)


def price_band(ref_price: float, pct: float = PRICE_BAND_PCT) -> tuple[float, float]:
    """Return (floor, ceiling) for the daily ±7% limit-order band around the reference price."""
    return round(ref_price * (1 - pct), 0), round(ref_price * (1 + pct), 0)


def is_within_price_band(order_price: float, ref_price: float, pct: float = PRICE_BAND_PCT) -> bool:
    floor, ceiling = price_band(ref_price, pct)
    return floor <= order_price <= ceiling


def _add_business_days(start: date, n_days: float) -> date:
    """Add a (possibly fractional, e.g. T+1.5) number of business days."""
    whole_days = int(n_days)
    remainder = n_days - whole_days
    d = start
    added = 0
    while added < whole_days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    if remainder:
        # A ".5" settlement bucket lands within the same session's afternoon cut-off;
        # modeled here as the next business day for cash-availability purposes.
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
    return d


def settlement_date(trade_date: date, t_plus: float = 2.0) -> date:
    """T+2 (securities) or T+1.5 (cash, per HOSE's intraday settlement cut-off) bucketing."""
    return _add_business_days(trade_date, t_plus)
