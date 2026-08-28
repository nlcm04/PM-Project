"""Scan the tracked universe for institutional order-flow anomalies (large volume
relative to a stock's own history) and write results to `institutional_flow_alerts`.

Decoupled from the value/quality screener by design -- runs against every asset
with recent price history, not just today's picks, so it can flag "smart money"
activity in stocks not currently in the discovery queue.

Usage: python -m scripts.detect_flow_alerts
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import SessionLocal
from app.models.flow_alert import InstitutionalFlowAlert
from app.quant.order_flow import scan_universe_for_flow_signals

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("detect_flow_alerts")

LOOKBACK_BARS = 40


def load_recent_history(db) -> dict[int, pd.DataFrame]:
    query = """
        SELECT asset_id, ts, close, volume
        FROM market_data_daily
        WHERE ts >= now() - interval '90 days'
        ORDER BY asset_id, ts
    """
    df = pd.read_sql(query, db.bind)
    return {asset_id: g.tail(LOOKBACK_BARS).reset_index(drop=True) for asset_id, g in df.groupby("asset_id")}


def run() -> int:
    db = SessionLocal()
    try:
        history = load_recent_history(db)
        if not history:
            log.warning("No market_data_daily history yet -- has scripts.ingest_market_data run?")
            return 0

        signals = scan_universe_for_flow_signals(history)
        today = date.today()
        now = datetime.now(timezone.utc)

        for asset_id, sig in signals.items():
            stmt = pg_insert(InstitutionalFlowAlert).values(
                asset_id=asset_id,
                as_of_date=today,
                relative_volume=sig.relative_volume,
                volume_zscore=sig.volume_zscore,
                price_change_pct=sig.price_change_pct,
                direction=sig.direction,
                foreign_net_value=sig.foreign_net_value,
                is_anomalous=sig.is_anomalous,
                created_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["asset_id", "as_of_date"],
                set_={
                    "relative_volume": stmt.excluded.relative_volume,
                    "volume_zscore": stmt.excluded.volume_zscore,
                    "price_change_pct": stmt.excluded.price_change_pct,
                    "direction": stmt.excluded.direction,
                    "foreign_net_value": stmt.excluded.foreign_net_value,
                    "is_anomalous": stmt.excluded.is_anomalous,
                },
            )
            db.execute(stmt)
        db.commit()
        log.info("Wrote %d flow alerts for %s (%d anomalous)", len(signals), today, sum(s.is_anomalous for s in signals.values()))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(run())
