from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.performance import PerformanceAnalytics
from app.schemas.performance import PerformanceAnalyticsOut

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/health", response_model=list[PerformanceAnalyticsOut])
def portfolio_health(limit: int = 180, db: Session = Depends(get_db)) -> list[PerformanceAnalytics]:
    query = select(PerformanceAnalytics).order_by(PerformanceAnalytics.snapshot_date.desc()).limit(limit)
    return list(reversed(list(db.scalars(query))))
