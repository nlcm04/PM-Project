import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PickStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class FactorScore(Base):
    __tablename__ = "factor_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    composite_score: Mapped[float] = mapped_column(Float)
    percentile_rank: Mapped[float] = mapped_column(Float)
    information_coefficient: Mapped[float] = mapped_column(Float)
    expected_active_return: Mapped[float] = mapped_column(Float)  # Grinold: IC * sigma_i * S_i


class DailyStockPick(Base):
    __tablename__ = "daily_stock_picks"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    pick_date: Mapped[date] = mapped_column(Date, index=True)
    rationale: Mapped[str] = mapped_column(Text)
    projected_sharpe: Mapped[float] = mapped_column(Float)
    suggested_weight: Mapped[float] = mapped_column(Float)
    backtest_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[PickStatus] = mapped_column(Enum(PickStatus), default=PickStatus.PENDING, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
