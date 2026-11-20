"""MD-03 isolated price_bar model. Does not create tables or expose prices.

Only the separately approved Alembic migration may install this schema.
Until verified exchange calendars and provider finality are implemented,
the database enforces UNFINALIZED/PARTIAL KIS daily bars only.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index,
    Numeric, String, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.auth_models import AuthBase


class PriceBar(AuthBase):
    __tablename__ = "price_bar"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timeframe", "session_date", "price_basis", "source",
            name="uq_price_bar_identity_session_source",
        ),
        Index("ix_price_bar_instrument_session", "instrument_id", "session_date"),
        CheckConstraint("timeframe = '1d'", name="ck_price_bar_timeframe"),
        CheckConstraint("price_basis IN ('RAW','ADJUSTED')", name="ck_price_bar_basis"),
        CheckConstraint("source = 'KIS'", name="ck_price_bar_source"),
        CheckConstraint("quality_status = 'PARTIAL'", name="ck_price_bar_quality"),
        CheckConstraint("is_final = false", name="ck_price_bar_never_final_md03"),
        CheckConstraint("source_observed_at IS NULL", name="ck_price_bar_no_source_observation_md03"),
        CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0 "
            "AND low <= open AND low <= close AND low <= high "
            "AND high >= open AND high >= close",
            name="ck_price_bar_ohlc",
        ),
        CheckConstraint("volume >= 0", name="ck_price_bar_volume"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("instrument.id", ondelete="RESTRICT"),
        nullable=False,
    )
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    price_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 0), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quality_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PARTIAL")
