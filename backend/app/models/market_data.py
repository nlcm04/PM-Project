from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MarketDataDaily(Base):
    """Mirrors the `market_data_daily` hypertable defined in db/schema.sql."""

    __tablename__ = "market_data_daily"

    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    ref_price: Mapped[float] = mapped_column(Float)
    ceiling: Mapped[float] = mapped_column(Float)
    floor: Mapped[float] = mapped_column(Float)
