"""Value and quality factor calculations (spec Section 4.2)."""

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
