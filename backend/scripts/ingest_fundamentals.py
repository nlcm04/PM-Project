"""Populate `fundamentals_quarterly` value/quality ratios via vnstock (spec Section 4.2).

Does NOT set auditor_opinion / filing_on_time -- vnstock exposes neither (see
app/data/vnstock_client.py docstring). Those columns keep their schema defaults
(UNQUALIFIED / on-time) until a separate governance feed is wired in, which
means `screen_universe()`'s governance gate is only PARTIALLY enforced until
then -- it will still fail closed on missing/zero interest coverage, but not
catch a real audit or filing problem. Treat that as an open gap, not solved.

Usage: python -m scripts.ingest_fundamentals [--tickers VNM,VIC,...]
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

from app.core.db import SessionLocal
from app.data import vnstock_client
from app.models.asset import Asset
from app.models.fundamentals import FundamentalsQuarterly

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest_fundamentals")


def _period_end_from_label(label: str) -> date:
    year_str, q_str = label.split("-Q")
    year, quarter = int(year_str), int(q_str)
    month = quarter * 3
    day = 31 if month in (3, 12) else 30
    return date(year, month, day)


def run(tickers: list[str] | None) -> int:
    db = SessionLocal()
    try:
        query = db.query(Asset)
        if tickers:
            query = query.filter(Asset.ticker.in_(tickers))
        assets = query.all()
        if not assets:
            log.warning("No matching assets found -- has `assets` been seeded?")
            return 0

        for asset in assets:
            try:
                ratios = vnstock_client.get_fundamentals(asset.ticker)
            except Exception:
                log.exception("Failed to fetch fundamentals for %s", asset.ticker)
                continue

            period_end = _period_end_from_label(ratios["period_label"])
            row = (
                db.query(FundamentalsQuarterly)
                .filter_by(asset_id=asset.id, period_end=period_end)
                .one_or_none()
            )
            is_new = row is None
            row = row or FundamentalsQuarterly(asset_id=asset.id, period_end=period_end)
            row.earnings_yield = ratios["earnings_yield"]
            row.book_to_market = ratios["book_to_market"]
            row.ev_to_ebitda = ratios["ev_to_ebitda"]
            row.roic = ratios["roic"]
            row.cfo_to_assets = ratios["cfo_to_assets"]
            row.interest_coverage = ratios["interest_coverage"]
            if is_new:
                db.add(row)
            log.info("Upserted fundamentals for %s (%s)", asset.ticker, period_end)

        db.commit()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated tickers; default is every registered asset")
    args = parser.parse_args()
    raise SystemExit(run(args.tickers.split(",") if args.tickers else None))
