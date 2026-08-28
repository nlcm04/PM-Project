from datetime import date

from pydantic import BaseModel, ConfigDict


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    company_name: str
    exchange: str
    sector: str | None
    listing_date: date | None
    is_active: bool
    margin_eligible: bool
    warning_status: str
