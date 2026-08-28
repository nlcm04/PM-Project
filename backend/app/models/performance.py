from datetime import date

from sqlalchemy import JSON, Date, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PerformanceAnalytics(Base):
    """Daily/periodic portfolio-level snapshot, including the diagnostics pipeline output."""

    __tablename__ = "performance_analytics"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True, unique=True)
    nav: Mapped[float] = mapped_column(Float)
    sharpe_ratio: Mapped[float] = mapped_column(Float)
    max_drawdown: Mapped[float] = mapped_column(Float)
    factor_exposures: Mapped[dict] = mapped_column(JSON, default=dict)
    # ADF / Breusch-Pagan / Breusch-Godfrey / VIF results for this cycle
    diagnostics: Mapped[dict] = mapped_column(JSON, default=dict)
