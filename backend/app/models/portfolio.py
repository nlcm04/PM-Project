import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class HoldingStatus(str, enum.Enum):
    OPEN = "OPEN"
    SELL_SIGNAL = "SELL_SIGNAL"  # exit criteria met, awaiting manual close-out
    CLOSED = "CLOSED"


class SettlementStatus(str, enum.Enum):
    PENDING = "PENDING"
    SETTLED = "SETTLED"


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)  # always a multiple of lot_size (100)
    avg_cost: Mapped[float] = mapped_column(Float)
    opened_at: Mapped[date] = mapped_column(Date)
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    peak_price_since_open: Mapped[float] = mapped_column(Float)
    stop_loss_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # peak - 2.5*ATR
    status: Mapped[HoldingStatus] = mapped_column(Enum(HoldingStatus), default=HoldingStatus.OPEN, index=True)
    sell_signal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class CashSettlement(Base):
    """T+2 / T+1.5 settlement bucket tracking for cash and security availability."""

    __tablename__ = "cash_settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    side: Mapped[str] = mapped_column(String(4))  # BUY | SELL
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    trade_date: Mapped[date] = mapped_column(Date)
    settlement_date: Mapped[date] = mapped_column(Date)
    status: Mapped[SettlementStatus] = mapped_column(Enum(SettlementStatus), default=SettlementStatus.PENDING)
