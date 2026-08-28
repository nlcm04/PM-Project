from datetime import date

from pydantic import BaseModel

from app.models.portfolio import HoldingStatus


class HoldingOut(BaseModel):
    id: int
    asset_id: int
    ticker: str
    quantity: int
    avg_cost: float
    opened_at: date
    closed_at: date | None
    peak_price_since_open: float
    stop_loss_price: float | None
    status: HoldingStatus
    sell_signal_reason: str | None
