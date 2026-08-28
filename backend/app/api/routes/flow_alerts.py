from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.asset import Asset
from app.models.flow_alert import InstitutionalFlowAlert
from app.schemas.flow_alert import InstitutionalFlowAlertOut

router = APIRouter(prefix="/api/flow-alerts", tags=["flow-alerts"])


@router.get("", response_model=list[InstitutionalFlowAlertOut])
def list_flow_alerts(
    days: int = 7,
    only_anomalous: bool = True,
    db: Session = Depends(get_db),
) -> list[InstitutionalFlowAlertOut]:
    """Recent volume-anomaly signals, most extreme first -- the "follow the big money" feed."""
    since = date.today() - timedelta(days=days)
    query = (
        select(InstitutionalFlowAlert, Asset.ticker)
        .join(Asset, Asset.id == InstitutionalFlowAlert.asset_id)
        .where(InstitutionalFlowAlert.as_of_date >= since)
    )
    if only_anomalous:
        query = query.where(InstitutionalFlowAlert.is_anomalous.is_(True))
    query = query.order_by(InstitutionalFlowAlert.volume_zscore.desc())

    return [
        InstitutionalFlowAlertOut(
            id=a.id,
            asset_id=a.asset_id,
            ticker=ticker,
            as_of_date=a.as_of_date,
            relative_volume=a.relative_volume,
            volume_zscore=a.volume_zscore,
            price_change_pct=a.price_change_pct,
            direction=a.direction,
            foreign_net_value=a.foreign_net_value,
            is_anomalous=a.is_anomalous,
            created_at=a.created_at,
        )
        for a, ticker in db.execute(query).all()
    ]
