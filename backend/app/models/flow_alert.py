from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class InstitutionalFlowAlert(Base):
    """Volume-anomaly signal used as a proxy for large institutional buying/selling.

    Supplementary to the value/quality screen -- surfaced alongside picks in the
    Daily Discovery UI, but never itself adds or removes a stock from
    `daily_stock_picks`.
    """

    __tablename__ = "institutional_flow_alerts"
    __table_args__ = (UniqueConstraint("asset_id", "as_of_date", name="uq_flow_alert_asset_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    relative_volume: Mapped[float] = mapped_column(Float)
    volume_zscore: Mapped[float] = mapped_column(Float)
    price_change_pct: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(15))  # ACCUMULATION | DISTRIBUTION | NEUTRAL
    foreign_net_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_anomalous: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
