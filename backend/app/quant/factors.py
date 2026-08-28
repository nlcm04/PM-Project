"""Value/quality factor calculations (spec Section 4.2), plus momentum and
sector-neutral composite scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd


def earnings_yield(net_income: float, market_cap: float) -> float:
    """Cyclically-adjusted E/P -- caller passes in a multi-year-smoothed net_income."""
    return net_income / market_cap if market_cap else np.nan


def book_to_market(book_value: float, market_cap: float) -> float:
    return book_value / market_cap if market_cap else np.nan


def ev_to_ebitda(enterprise_value: float, ebitda: float) -> float:
    return enterprise_value / ebitda if ebitda else np.nan


def roic(nopat: float, invested_capital: float) -> float:
    return nopat / invested_capital if invested_capital else np.nan


def cfo_to_assets(cfo: float, total_assets: float) -> float:
    return cfo / total_assets if total_assets else np.nan


def interest_coverage(ebit: float, interest_expense: float) -> float:
    if not interest_expense:
        return np.inf  # no debt service burden
    return ebit / interest_expense


def zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if std == 0 or np.isnan(std):
        # Preserve the original NaN mask -- a naive `pd.Series(0.0, ...)` here would
        # silently turn a missing value (e.g. a bank lacking EV/EBITDA) into a fake
        # "average" 0.0 z-score instead of propagating the missingness.
        return pd.Series(0.0, index=series.index).mask(series.isna())
    return (series - series.mean()) / std


def composite_score(factor_df: pd.DataFrame, higher_is_better: dict[str, bool]) -> pd.Series:
    """Cross-sectional composite: average z-score across factors, sign-flipped for
    "lower is better" factors (e.g. EV/EBITDA), equal-weighted.
    """
    z_components = []
    for col, higher_better in higher_is_better.items():
        z = zscore(factor_df[col])
        z_components.append(z if higher_better else -z)
    return pd.concat(z_components, axis=1).mean(axis=1)


def sector_neutral_zscore(
    factor_df: pd.DataFrame, col: str, sector_col: str = "sector", min_group_size: int = 4
) -> pd.Series:
    """Z-scores `col` within each sector rather than across the whole universe --
    a bank's EV/EBITDA isn't comparable to a real-estate developer's; valuation
    multiples differ structurally by sector, and pooling them biases the ranking
    toward whichever sector happens to be cheap right now rather than the
    cheapest name within its own sector.

    Sectors with fewer than `min_group_size` non-null values for this factor
    fall back to the global (cross-sector) z-score instead: a 2-name sector's
    within-group z-scores are just +1/-1 and not statistically meaningful.
    """
    global_z = zscore(factor_df[col])
    counts = factor_df.groupby(sector_col)[col].transform("count")
    within_sector_z = factor_df.groupby(sector_col)[col].transform(zscore)
    return within_sector_z.where(counts >= min_group_size, global_z)


def sector_neutral_composite_score(
    factor_df: pd.DataFrame,
    higher_is_better: dict[str, bool],
    sector_col: str = "sector",
    min_group_size: int = 4,
) -> pd.Series:
    z_components = []
    for col, higher_better in higher_is_better.items():
        z = sector_neutral_zscore(factor_df, col, sector_col, min_group_size)
        z_components.append(z if higher_better else -z)
    return pd.concat(z_components, axis=1).mean(axis=1)


def momentum_12_1(returns_df: pd.DataFrame, lookback_days: int = 252, skip_days: int = 21) -> pd.Series:
    """12-1 month momentum (Jegadeesh-Titman construction): cumulative return from
    t-lookback_days to t-skip_days, skipping the most recent ~month to avoid the
    well-documented short-term reversal effect. One of the best-replicated
    factors in equity markets, emerging markets included -- absent from the
    original 5-factor value/quality set. Returns NaN for tickers without enough
    price history rather than a misleadingly short-window estimate.
    """
    n = len(returns_df)
    if n <= skip_days:
        return pd.Series(np.nan, index=returns_df.columns)
    start = max(n - lookback_days, 0)
    end = n - skip_days
    window = returns_df.iloc[start:end]
    if window.empty:
        return pd.Series(np.nan, index=returns_df.columns)
    return (1 + window).prod() - 1
