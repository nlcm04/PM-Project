from datetime import date, datetime

from pydantic import BaseModel

from app.models.scoring import PickStatus


class DailyStockPickOut(BaseModel):
    id: int
    asset_id: int
    ticker: str
    company_name: str
    pick_date: date
    rationale: str
    projected_sharpe: float
    suggested_weight: float
    backtest_summary: dict
    status: PickStatus
    decided_at: datetime | None
    decided_by: str | None


class PickDecisionIn(BaseModel):
    decided_by: str = "user"
