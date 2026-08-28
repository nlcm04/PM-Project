"""Entrypoint invoked by .github/workflows/daily_pipeline.yml after HOSE market close.

Pulls fresh data via vnstock, runs the screening engine, and writes PENDING rows to
`daily_stock_picks`. Never touches `holdings` -- approval is a manual, human action
taken through the Daily Discovery UI, never from this script.

Usage: python -m scripts.run_daily_pipeline
"""

from __future__ import annotations

import logging
import sys
from datetime import date, timedelta

import pandas as pd

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.data import vnstock_client
from app.models.asset import Asset
from app.models.fundamentals import FundamentalsQuarterly
from app.quant import backtest, screener

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("daily_pipeline")


def load_fundamentals_snapshot(db) -> pd.DataFrame:
    """Join the latest FundamentalsQuarterly row per asset with its Asset-level flags."""
    query = """
        SELECT DISTINCT ON (f.asset_id)
            f.asset_id, a.sector, a.warning_status, a.margin_eligible,
            f.earnings_yield, f.book_to_market, f.ev_to_ebitda,
            f.roic, f.cfo_to_assets, f.interest_coverage,
            f.auditor_opinion, f.filing_on_time
        FROM fundamentals_quarterly f
        JOIN assets a ON a.id = f.asset_id
        ORDER BY f.asset_id, f.period_end DESC
    """
    return pd.read_sql(query, db.bind)


def run() -> int:
    settings = get_settings()
    db = SessionLocal()
    try:
        fundamentals_df = load_fundamentals_snapshot(db)
        if fundamentals_df.empty:
            log.warning("No fundamentals data available yet -- has the ingestion job run?")
            return 0

        scored = screener.screen_universe(fundamentals_df, settings)
        if scored.empty:
            log.info("No assets passed the governance/value/quality screen today.")
            return 0

        # Placeholder IC and volatility until enough live history accumulates in market_data_daily.
        ic = 0.05
        volatility = pd.Series(0.02, index=scored["asset_id"])

        picks = screener.build_daily_picks(scored, ic=ic, return_volatility=volatility, forward_return_std_by_asset=volatility)
        bt_by_asset = {p["asset_id"]: {"sharpe_ratio": 0.0, "information_coefficient": ic, "note": "insufficient history for a live backtest"} for p in picks}

        rows = screener.persist_daily_picks(db, picks, pick_date=date.today(), backtest_results_by_asset=bt_by_asset)
        log.info("Wrote %d PENDING picks for %s", len(rows), date.today())
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(run())
