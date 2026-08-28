from datetime import date, datetime

from pydantic import BaseModel


class InstitutionalFlowAlertOut(BaseModel):
    id: int
    asset_id: int
    ticker: str
    as_of_date: date
    relative_volume: float
    volume_zscore: float
    price_change_pct: float
    direction: str
    foreign_net_value: float | None
    is_anomalous: bool
    created_at: datetime
