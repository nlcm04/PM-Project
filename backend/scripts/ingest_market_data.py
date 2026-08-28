"""Pull OHLCV + fundamentals for the HOSE universe via vnstock and upsert into TimescaleDB.

Usage: python -m scripts.ingest_market_data [--tickers VNM,VIC,...] [--lookback-days 400]
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import SessionLocal
from app.data import vnstock_client
from app.models.asset import Asset
from app.models.market_data import MarketDataDaily

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingest_market_data")


def upsert_ohlcv(db, asset_id: int, df) -> None:
    if df.empty:
        return
    rows = [
        {
            "asset_id": asset_id,
            "ts": r["time"],
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume": int(r["volume"]),
            "ref_price": r.get("ref_price", r["close"]),
            "ceiling": r.get("ceiling", r["close"] * 1.07),
            "floor": r.get("floor", r["close"] * 0.93),
        }
        for _, r in df.iterrows()
    ]
    stmt = pg_insert(MarketDataDaily).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["asset_id", "ts"],
        set_={c: stmt.excluded[c] for c in ("open", "high", "low", "close", "volume", "ref_price", "ceiling", "floor")},
    )
    db.execute(stmt)
    db.commit()


def run(tickers: list[str] | None, lookback_days: int) -> int:
    db = SessionLocal()
    try:
        tickers = tickers or vnstock_client.get_hose_universe()
        start = (date.today() - timedelta(days=lookback_days)).isoformat()
        end = date.today().isoformat()

        for ticker in tickers:
            asset = db.query(Asset).filter(Asset.ticker == ticker).one_or_none()
            if asset is None:
                log.info("Skipping %s -- not registered in `assets` yet", ticker)
                continue
            try:
                df = vnstock_client.get_ohlcv(ticker, start=start, end=end)
                upsert_ohlcv(db, asset.id, df)
                log.info("Ingested %d rows for %s", len(df), ticker)
            except Exception:
                log.exception("Failed to ingest %s", ticker)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated tickers; default is the full HOSE universe")
    parser.add_argument("--lookback-days", type=int, default=400)
    args = parser.parse_args()
    tickers = args.tickers.split(",") if args.tickers else None
    raise SystemExit(run(tickers, args.lookback_days))
