from datetime import date

from sqlalchemy import Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    exchange: Mapped[str] = mapped_column(String(10), default="HOSE")
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    listing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    margin_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    # NONE | WARNING | CONTROL | SUSPENDED -- HOSE warning/special-control list status
    warning_status: Mapped[str] = mapped_column(String(20), default="NONE")
