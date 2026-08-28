from datetime import date

from pydantic import BaseModel, ConfigDict


class PerformanceAnalyticsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_date: date
    nav: float
    sharpe_ratio: float
    max_drawdown: float
    factor_exposures: dict
    diagnostics: dict
