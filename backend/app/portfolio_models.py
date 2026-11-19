"""Phase 1 persistent user-entered instrument catalog and single-owner tracking.

No demo stocks, quotes or market prices are populated by this module.
Tables are installed only via an explicitly approved Alembic migration.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String,
    Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.auth_models import AuthBase


class Instrument(AuthBase):
    __tablename__ = "instrument"
    __table_args__ = (
        UniqueConstraint("exchange_mic", "normalized_symbol", name="uq_instrument_exchange_symbol"),
        CheckConstraint("market IN ('KR','US')", name="ck_instrument_market"),
        CheckConstraint("asset_type IN ('STOCK','ETF')", name="ck_instrument_asset_type"),
        Index("ix_instrument_market_name", "market", "name"),
        Index("ix_instrument_market_symbol", "market", "normalized_symbol"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    exchange_mic: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class TrackedInstrument(AuthBase):
    __tablename__ = "tracked_instrument"
    __table_args__ = (
        UniqueConstraint("instrument_id", name="uq_tracked_instrument_one_per_symbol"),
        CheckConstraint("kind IN ('HOLDING','WATCH')", name="ck_tracked_kind"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_tracked_quantity_positive"),
        CheckConstraint("average_cost IS NULL OR average_cost >= 0", name="ck_tracked_cost_nonnegative"),
        CheckConstraint("average_cost IS NULL OR quantity IS NOT NULL", name="ck_tracked_cost_requires_quantity"),
        CheckConstraint(
            "kind <> 'WATCH' OR (quantity IS NULL AND average_cost IS NULL)",
            name="ck_tracked_watch_without_holdings",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("instrument.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    average_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
