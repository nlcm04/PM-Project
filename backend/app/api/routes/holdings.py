from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.asset import Asset
from app.models.portfolio import Holding
from app.schemas.holding import HoldingOut

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


@router.get("", response_model=list[HoldingOut])
def list_holdings(db: Session = Depends(get_db)) -> list[HoldingOut]:
    query = (
        select(Holding, Asset.ticker)
        .join(Asset, Asset.id == Holding.asset_id)
        .order_by(Holding.opened_at.desc())
    )
    return [
        HoldingOut(
            id=h.id,
            asset_id=h.asset_id,
            ticker=ticker,
            quantity=h.quantity,
            avg_cost=h.avg_cost,
            opened_at=h.opened_at,
            closed_at=h.closed_at,
            peak_price_since_open=h.peak_price_since_open,
            stop_loss_price=h.stop_loss_price,
            status=h.status,
            sell_signal_reason=h.sell_signal_reason,
        )
        for h, ticker in db.execute(query).all()
    ]
