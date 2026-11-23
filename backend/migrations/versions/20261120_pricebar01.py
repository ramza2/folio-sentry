"""MD-03 additive price_bar, only unfinalized KIS daily candidates.

Revision ID: 20261120_pricebar01
Revises: 20261119_portfolio01

NEVER run against the MiniPC operating DB without a separate user approval.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261120_pricebar01"
down_revision = "20261119_portfolio01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_bar",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("instrument_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("instrument.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("price_basis", sa.String(16), nullable=False),
        sa.Column("open", sa.Numeric(24, 8), nullable=False),
        sa.Column("high", sa.Numeric(24, 8), nullable=False),
        sa.Column("low", sa.Numeric(24, 8), nullable=False),
        sa.Column("close", sa.Numeric(24, 8), nullable=False),
        sa.Column("volume", sa.Numeric(28, 0), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quality_status", sa.String(16), nullable=False, server_default="PARTIAL"),
        sa.UniqueConstraint(
            "instrument_id", "timeframe", "session_date", "price_basis", "source",
            name="uq_price_bar_identity_session_source",
        ),
        sa.CheckConstraint("timeframe = '1d'", name="ck_price_bar_timeframe"),
        sa.CheckConstraint("price_basis IN ('RAW','ADJUSTED')", name="ck_price_bar_basis"),
        sa.CheckConstraint("source = 'KIS'", name="ck_price_bar_source"),
        sa.CheckConstraint("quality_status = 'PARTIAL'", name="ck_price_bar_quality"),
        sa.CheckConstraint("is_final = false", name="ck_price_bar_never_final_md03"),
        sa.CheckConstraint("source_observed_at IS NULL", name="ck_price_bar_no_source_observation_md03"),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0 "
            "AND low <= open AND low <= close AND low <= high "
            "AND high >= open AND high >= close",
            name="ck_price_bar_ohlc",
        ),
        sa.CheckConstraint("volume >= 0", name="ck_price_bar_volume"),
    )
    op.create_index(
        "ix_price_bar_instrument_session", "price_bar",
        ["instrument_id", "session_date"],
    )


def downgrade() -> None:
    # Dropping price history would permanently erase financial records.
    raise RuntimeError("Price bar downgrade forbidden; use approved backup/restore.")
