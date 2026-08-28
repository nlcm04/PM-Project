"""Automated econometric diagnostics (spec Section 5.1): ADF stationarity, Breusch-Pagan
heteroskedasticity, Breusch-Godfrey serial correlation, and VIF-based multicollinearity pruning.

Run once per screening cycle over the factor-return regression; results are persisted to
`performance_analytics.diagnostics` for audit trail.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import adfuller


def run_adf(series: pd.Series) -> dict:
    series = series.dropna()
    if len(series) < 10:
        return {"statistic": None, "p_value": None, "is_stationary": None, "note": "insufficient observations"}
    stat, p_value, *_ = adfuller(series, autolag="AIC", result_object=False)
    return {"statistic": float(stat), "p_value": float(p_value), "is_stationary": bool(p_value < 0.05)}


def run_breusch_pagan(residuals: np.ndarray, exog: np.ndarray) -> dict:
    lm_stat, lm_p, f_stat, f_p = het_breuschpagan(residuals, exog)
    return {
        "lm_statistic": float(lm_stat),
        "lm_p_value": float(lm_p),
        "heteroskedastic": bool(lm_p < 0.05),
    }


def run_breusch_godfrey(fitted_ols_results, nlags: int = 4) -> dict:
    lm_stat, lm_p, f_stat, f_p = acorr_breusch_godfrey(fitted_ols_results, nlags=nlags)
    return {
        "lm_statistic": float(lm_stat),
        "lm_p_value": float(lm_p),
        "serially_correlated": bool(lm_p < 0.05),
    }


def compute_vif(factor_df: pd.DataFrame) -> pd.Series:
    X = sm.add_constant(factor_df.dropna())
    vifs = pd.Series(
        [variance_inflation_factor(X.values, i) for i in range(X.shape[1])],
        index=X.columns,
    )
    return vifs.drop("const", errors="ignore")


def prune_by_vif(factor_df: pd.DataFrame, threshold: float = 5.0) -> tuple[pd.DataFrame, list[str]]:
    """Iteratively drop the highest-VIF factor until all remaining factors are below `threshold`."""
    df = factor_df.copy()
    dropped: list[str] = []
    while df.shape[1] > 1:
        vifs = compute_vif(df)
        worst = vifs.idxmax()
        if vifs[worst] <= threshold:
            break
        df = df.drop(columns=[worst])
        dropped.append(worst)
    return df, dropped


def run_factor_regression_diagnostics(factor_df: pd.DataFrame, forward_returns: pd.Series) -> dict:
    """End-to-end pipeline: VIF-prune the factor set, fit OLS of forward returns on the
    surviving factors, then run BP and BG on the fitted model. Returns a JSON-serializable dict.
    """
    pruned, dropped = prune_by_vif(factor_df)
    aligned = pd.concat([pruned, forward_returns.rename("fwd_ret")], axis=1).dropna()
    # Breusch-Godfrey's auxiliary regression needs real headroom beyond the
    # bare minimum for OLS to be identified at all -- verified live: a
    # regression with 8 observations and 3 surviving factors passed a
    # `len(aligned) < len(pruned.columns) + 2` check but still raised inside
    # statsmodels ("dimensions that are asymptotically non-normal"). Require
    # a larger margin, and fall back gracefully if the fit still fails.
    if len(aligned) < 2 * (len(pruned.columns) + 2):
        return {
            "note": "insufficient observations for reliable regression diagnostics",
            "vif_dropped_factors": dropped,
            "n_obs": len(aligned),
        }

    X = sm.add_constant(aligned[pruned.columns])
    y = aligned["fwd_ret"]
    try:
        model = sm.OLS(y, X).fit()
        return {
            "vif_dropped_factors": dropped,
            "adf_forward_returns": run_adf(forward_returns),
            "breusch_pagan": run_breusch_pagan(model.resid.values, X.values),
            "breusch_godfrey": run_breusch_godfrey(model),
        }
    except (ValueError, np.linalg.LinAlgError) as exc:
        return {
            "note": f"regression diagnostics failed on this sample: {exc}",
            "vif_dropped_factors": dropped,
            "n_obs": len(aligned),
        }
