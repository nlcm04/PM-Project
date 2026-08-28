"""Institutional order-flow / "smart money" signal.

Idea: informed institutional investors tend to act on new information with
unusually large buy orders before it's broadly priced in. This module flags a
stock when today's traded volume is a statistical outlier relative to ITS OWN
trading history, and tags the direction (accumulation vs distribution) using
the same day's price move. It only ever reads publicly reported OHLCV/foreign-
flow data (via vnstock) -- there is no access to any broker-level or
non-public order book.

This is a supplementary signal surfaced alongside the value/quality screen; it
does not by itself add or remove a stock from `daily_stock_picks`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class FlowSignal:
    as_of: pd.Timestamp
    relative_volume: float          # today's volume / trailing rolling average
    volume_zscore: float            # today's volume vs trailing mean/std
    price_change_pct: float
    is_anomalous: bool
    direction: str                  # ACCUMULATION | DISTRIBUTION | NEUTRAL
    foreign_net_value: float | None = None


def relative_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    """Each day's volume divided by its own trailing rolling average (today excluded)."""
    trailing_avg = volume.shift(1).rolling(window=window, min_periods=max(window // 2, 3)).mean()
    return volume / trailing_avg


def volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series:
    trailing_mean = volume.shift(1).rolling(window=window, min_periods=max(window // 2, 3)).mean()
    trailing_std = volume.shift(1).rolling(window=window, min_periods=max(window // 2, 3)).std(ddof=0)
    return (volume - trailing_mean) / trailing_std.replace(0, np.nan)


def detect_flow_signal(
    ts: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    foreign_net_value: pd.Series | None = None,
    window: int = 20,
    z_threshold: float = 2.5,
) -> FlowSignal | None:
    """Evaluate the most recent bar only (the daily pipeline calls this once per asset per day)."""
    if len(volume.dropna()) < max(window // 2, 3) + 1:
        return None

    rel_vol = relative_volume(volume, window)
    z = volume_zscore(volume, window)
    price_change = close.pct_change()

    latest_z = z.iloc[-1]
    latest_rel = rel_vol.iloc[-1]
    latest_price_chg = price_change.iloc[-1]
    if np.isnan(latest_z) or np.isnan(latest_rel):
        return None

    is_anomalous = bool(latest_z >= z_threshold)
    if is_anomalous and latest_price_chg > 0:
        direction = "ACCUMULATION"
    elif is_anomalous and latest_price_chg < 0:
        direction = "DISTRIBUTION"
    else:
        direction = "NEUTRAL"

    foreign_val = (
        float(foreign_net_value.iloc[-1])
        if foreign_net_value is not None and len(foreign_net_value.dropna())
        else None
    )

    return FlowSignal(
        as_of=ts.iloc[-1],
        relative_volume=float(latest_rel),
        volume_zscore=float(latest_z),
        price_change_pct=float(latest_price_chg) if not np.isnan(latest_price_chg) else 0.0,
        is_anomalous=is_anomalous,
        direction=direction,
        foreign_net_value=foreign_val,
    )


def scan_universe_for_flow_signals(
    price_history_by_asset: dict[int, pd.DataFrame],
    window: int = 20,
    z_threshold: float = 2.5,
) -> dict[int, FlowSignal]:
    """`price_history_by_asset[asset_id]` must have columns: ts, close, volume, and
    optionally foreign_net_value, sorted ascending by ts. Returns only assets with a signal.
    """
    signals: dict[int, FlowSignal] = {}
    for asset_id, df in price_history_by_asset.items():
        sig = detect_flow_signal(
            ts=df["ts"],
            close=df["close"],
            volume=df["volume"],
            foreign_net_value=df.get("foreign_net_value"),
            window=window,
            z_threshold=z_threshold,
        )
        if sig is not None and (sig.is_anomalous or sig.foreign_net_value):
            signals[asset_id] = sig
    return signals
