"""Grinold Rule and Fundamental Law of Active Management (spec Section 5.1)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def information_coefficient(scores: pd.Series, forward_returns: pd.Series) -> float:
    """Rank IC: Spearman correlation between the composite score and realized forward return."""
    aligned = pd.concat([scores, forward_returns], axis=1).dropna()
    if len(aligned) < 3:
        return 0.0
    ic, _ = stats.spearmanr(aligned.iloc[:, 0], aligned.iloc[:, 1])
    return float(ic) if not np.isnan(ic) else 0.0


def expected_active_return(ic: float, sigma_i: pd.Series, score_z: pd.Series) -> pd.Series:
    """Grinold Rule: mu_i = IC * sigma_i * S_i, with S_i the standardized (z-scored) score."""
    return ic * sigma_i * score_z


def fundamental_law_breadth(ic: float, n_independent_bets: int) -> float:
    """IR = IC * sqrt(breadth) -- the achievable information ratio given the strategy's breadth."""
    return ic * np.sqrt(max(n_independent_bets, 0))
