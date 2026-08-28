"""Daily screening orchestrator (spec Section 3). Fully decoupled from execution:
this module only ever writes PENDING rows to `daily_stock_picks` -- nothing here
ever creates or modifies a `Holding`. That transition happens exclusively through
the human-approval API endpoint in app/api/routes/picks.py.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.asset import Asset
from app.models.fundamentals import FundamentalsQuarterly
from app.models.scoring import DailyStockPick, FactorScore
from app.quant import backtest, diagnostics, factors, governance, grinold, optimizer
from app.quant.governance import GovernanceCheckInput
from app.utils import ordinal

HIGHER_IS_BETTER = {
    "earnings_yield": True,
    "book_to_market": True,
    "roic": True,
    "cfo_to_assets": True,
    "ev_to_ebitda": False,
}
MIN_COMPLETE_ROWS_FOR_VIF = 10  # below this, a VIF-based factor-pruning decision is unreliable


def screen_universe(fundamentals_df: pd.DataFrame, settings=None) -> pd.DataFrame:
    """Apply the governance disqualification filter, then compute the composite value/quality score.

    `fundamentals_df` is one row per asset with columns matching FundamentalsQuarterly plus
    `sector`, `warning_status`, and `margin_eligible` joined in from Asset.

    Known gap vs. the GitHub Pages static snapshot (backend/scripts/build_static_snapshot.py),
    which this DB-backed path does NOT yet replicate: momentum and foreign-flow factors (need
    price-history / a persisted foreign-flow series this path doesn't have wired up), and the
    walk-forward backtest (build_daily_picks still uses a single-window Sharpe estimate). This
    path has also never been run against a live database -- see README "What's real".
    """
    settings = settings or get_settings()

    disqualified_mask = []
    reasons_col = []
    for _, row in fundamentals_df.iterrows():
        check = GovernanceCheckInput(
            auditor_opinion=row["auditor_opinion"],
            filing_on_time=bool(row["filing_on_time"]),
            warning_status=row["warning_status"],
            margin_eligible=bool(row["margin_eligible"]),
            # A missing interest_coverage is NOT the same as a failing one -- verified live
            # (see app.data.vnstock_client / build_static_snapshot.py), KBS simply doesn't
            # report this ratio for banks. Missing -> not evaluated, not failed.
            min_interest_coverage_ok=(
                pd.isna(row["interest_coverage"]) or row["interest_coverage"] >= settings.min_interest_coverage
            ),
        )
        disq, reasons = governance.is_disqualified(check)
        disqualified_mask.append(disq)
        reasons_col.append(reasons)

    df = fundamentals_df.copy()
    df["disqualified"] = disqualified_mask
    df["disqualification_reasons"] = reasons_col
    if "sector" not in df.columns:
        df["sector"] = "Other"
    df["sector"] = df["sector"].fillna("Other")

    eligible = df[~df["disqualified"]].copy()
    if eligible.empty:
        return eligible

    factor_cols = list(HIGHER_IS_BETTER.keys())
    # VIF needs enough COMPLETE rows to be well-defined -- verified live: an
    # all-banks universe (missing ev_to_ebitda/roic/cfo_to_assets for every
    # row) made `.dropna()` inside prune_by_vif empty out entirely and crash
    # with a LinAlgError, instead of gracefully falling back to using every
    # factor unpruned.
    complete = eligible[factor_cols].dropna()
    if len(complete) >= MIN_COMPLETE_ROWS_FOR_VIF:
        pruned_factors, dropped = diagnostics.prune_by_vif(complete)
        surviving_weights = {k: v for k, v in HIGHER_IS_BETTER.items() if k in pruned_factors.columns}
    else:
        dropped = []
        surviving_weights = dict(HIGHER_IS_BETTER)
    # Sector-neutral: a bank's ratios are compared to other financials, not to real estate or
    # industrials -- pooling them cross-sector biases the ranking toward whichever sector
    # happens to be cheap right now (see app.quant.factors.sector_neutral_composite_score).
    eligible["composite_score"] = factors.sector_neutral_composite_score(eligible, surviving_weights, sector_col="sector")
    eligible["percentile_rank"] = eligible["composite_score"].rank(pct=True) * 100
    eligible["vif_dropped_factors"] = [dropped] * len(eligible)
    return eligible


def build_daily_picks(
    scored_df: pd.DataFrame,
    ic: float,
    return_volatility: pd.Series,
    forward_return_std_by_asset: pd.Series,
    top_n: int = 15,
) -> list[dict]:
    """Rank by Grinold expected active return, keep the top N, size with the max-Sharpe optimizer."""
    scored_df = scored_df.sort_values("composite_score", ascending=False).head(top_n).copy()
    score_z = factors.zscore(scored_df["composite_score"])
    sigma = return_volatility.reindex(scored_df["asset_id"]).fillna(return_volatility.mean())
    scored_df["expected_active_return"] = grinold.expected_active_return(ic, sigma.values, score_z.values)

    mu = scored_df["expected_active_return"].values
    n = len(scored_df)
    if n == 0:
        return []
    # Diagonal covariance approximation from per-asset volatility when a full covariance
    # matrix isn't available at screen time; the optimizer still enforces long-only + budget.
    cov = np.diag(sigma.values**2) if n > 1 else np.array([[max(sigma.values[0], 1e-6) ** 2]])
    weights = optimizer.max_sharpe_weights(mu, cov)

    picks = []
    for i, (_, row) in enumerate(scored_df.iterrows()):
        picks.append(
            {
                "asset_id": int(row["asset_id"]),
                "composite_score": float(row["composite_score"]),
                "percentile_rank": float(row["percentile_rank"]),
                "expected_active_return": float(row["expected_active_return"]),
                "suggested_weight": float(weights[i]),
            }
        )
    return picks


def persist_daily_picks(
    db: Session,
    picks: list[dict],
    pick_date: date,
    backtest_results_by_asset: dict[int, dict],
) -> list[DailyStockPick]:
    rows = []
    for p in picks:
        asset = db.get(Asset, p["asset_id"])
        bt = backtest_results_by_asset.get(p["asset_id"], {})
        rationale = (
            f"Composite score at {ordinal(round(p['percentile_rank']))} percentile; "
            f"Grinold expected active return {p['expected_active_return']:.4f}."
        )
        row = DailyStockPick(
            asset_id=p["asset_id"],
            pick_date=pick_date,
            rationale=rationale,
            projected_sharpe=bt.get("sharpe_ratio", 0.0),
            suggested_weight=p["suggested_weight"],
            backtest_summary=bt,
        )
        db.add(row)
        db.add(
            FactorScore(
                asset_id=p["asset_id"],
                as_of_date=pick_date,
                composite_score=p["composite_score"],
                percentile_rank=p["percentile_rank"],
                information_coefficient=bt.get("information_coefficient", 0.0),
                expected_active_return=p["expected_active_return"],
            )
        )
        rows.append(row)
    db.commit()
    return rows
