from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FundamentalsQuarterly(Base):
    __tablename__ = "fundamentals_quarterly"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    period_end: Mapped[date] = mapped_column(Date)

    # Cheapness
    earnings_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    book_to_market: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev_to_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Quality
    roic: Mapped[float | None] = mapped_column(Float, nullable=True)
    cfo_to_assets: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Governance / "no-scandal" flags
    auditor_opinion: Mapped[str] = mapped_column(String(20), default="UNQUALIFIED")
    filing_on_time: Mapped[bool] = mapped_column(Boolean, default=True)
