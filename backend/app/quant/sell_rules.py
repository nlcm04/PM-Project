"""Strict, low-churn exit criteria (spec Section 4.3). A holding is sold ONLY on:
  1. composite score below the 30th percentile for 2 consecutive quarters, or
  2. a governance violation / accounting scandal, or
  3. price breaching peak - 2.5*ATR (trailing stop).
No profit-taking or minor mean-reversion exits exist anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def average_true_range(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return true_range.rolling(window=window).mean()


def trailing_stop_price(peak_price: float, atr: float, multiple: float = 2.5) -> float:
    return peak_price - multiple * atr


@dataclass
class SellSignal:
    triggered: bool
    reasons: list[str] = field(default_factory=list)


def evaluate_sell_signal(
    percentile_rank_last_2_quarters: list[float],
    governance_disqualified: bool,
    governance_reasons: list[str],
    current_price: float,
    peak_price_since_open: float,
    atr: float,
    percentile_floor: float = 30.0,
    atr_multiple: float = 2.5,
) -> SellSignal:
    reasons = []

    if governance_disqualified:
        reasons.extend(f"governance: {r}" for r in governance_reasons)

    if len(percentile_rank_last_2_quarters) >= 2 and all(
        p < percentile_floor for p in percentile_rank_last_2_quarters[-2:]
    ):
        reasons.append(
            f"composite score below {percentile_floor:.0f}th percentile for 2 consecutive quarters"
        )

    if not np.isnan(atr) and atr > 0:
        stop = trailing_stop_price(peak_price_since_open, atr, atr_multiple)
        if current_price < stop:
            reasons.append(
                f"trailing stop breached: price {current_price:.0f} < {atr_multiple}x-ATR stop {stop:.0f}"
            )

    return SellSignal(triggered=len(reasons) > 0, reasons=reasons)
