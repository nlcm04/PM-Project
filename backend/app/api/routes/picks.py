from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.asset import Asset
from app.models.scoring import DailyStockPick, PickStatus
from app.schemas.pick import DailyStockPickOut, PickDecisionIn

router = APIRouter(prefix="/api/picks", tags=["picks"])


def _to_out(pick: DailyStockPick, asset: Asset) -> DailyStockPickOut:
    return DailyStockPickOut(
        id=pick.id,
        asset_id=pick.asset_id,
        ticker=asset.ticker,
        company_name=asset.company_name,
        pick_date=pick.pick_date,
        rationale=pick.rationale,
        projected_sharpe=pick.projected_sharpe,
        suggested_weight=pick.suggested_weight,
        backtest_summary=pick.backtest_summary,
        status=pick.status,
        decided_at=pick.decided_at,
        decided_by=pick.decided_by,
    )


@router.get("", response_model=list[DailyStockPickOut])
def list_picks(status: PickStatus | None = None, db: Session = Depends(get_db)) -> list[DailyStockPickOut]:
    query = (
        select(DailyStockPick, Asset)
        .join(Asset, Asset.id == DailyStockPick.asset_id)
        .order_by(DailyStockPick.pick_date.desc())
    )
    if status is not None:
        query = query.where(DailyStockPick.status == status)
    return [_to_out(pick, asset) for pick, asset in db.execute(query).all()]


def _decide(pick_id: int, new_status: PickStatus, payload: PickDecisionIn, db: Session) -> DailyStockPickOut:
    pick = db.get(DailyStockPick, pick_id)
    if pick is None:
        raise HTTPException(status_code=404, detail=f"Pick {pick_id} not found")
    if pick.status != PickStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Pick {pick_id} already {pick.status.value}")
    pick.status = new_status
    pick.decided_at = datetime.now(timezone.utc)
    pick.decided_by = payload.decided_by
    db.commit()
    db.refresh(pick)
    asset = db.get(Asset, pick.asset_id)
    return _to_out(pick, asset)


@router.post("/{pick_id}/approve", response_model=DailyStockPickOut)
def approve_pick(pick_id: int, payload: PickDecisionIn = PickDecisionIn(), db: Session = Depends(get_db)) -> DailyStockPickOut:
    """Manual approval only -- this is the sole path by which a pick becomes a holding candidate."""
    return _decide(pick_id, PickStatus.APPROVED, payload, db)


@router.post("/{pick_id}/reject", response_model=DailyStockPickOut)
def reject_pick(pick_id: int, payload: PickDecisionIn = PickDecisionIn(), db: Session = Depends(get_db)) -> DailyStockPickOut:
    return _decide(pick_id, PickStatus.REJECTED, payload, db)
