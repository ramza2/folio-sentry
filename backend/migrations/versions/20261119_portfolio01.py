"""Phase 1 manual instruments and tracked portfolio; no seed or demo rows.

Revision ID: 20261119_portfolio01
Revises: 20261119_auth01

IMPORTANT: Never auto-run against the user's operating database.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_portfolio01"
down_revision = "20261119_auth01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instrument",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("market", sa.String(8), nullable=False),
        sa.Column("exchange_mic", sa.String(8), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("normalized_symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("asset_type", sa.String(16), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("market IN ('KR','US')", name="ck_instrument_market"),
        sa.CheckConstraint("asset_type IN ('STOCK','ETF')", name="ck_instrument_asset_type"),
        sa.UniqueConstraint("exchange_mic", "normalized_symbol", name="uq_instrument_exchange_symbol"),
    )
    op.create_index("ix_instrument_market_name", "instrument", ["market", "name"])
    op.create_index("ix_instrument_market_symbol", "instrument", ["market", "normalized_symbol"])
    op.create_table(
        "tracked_instrument",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("instrument_id", sa.Uuid(as_uuid=True), sa.ForeignKey("instrument.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=True),
        sa.Column("average_cost", sa.Numeric(24, 8), nullable=True),
        sa.Column("alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("instrument_id", name="uq_tracked_instrument_one_per_symbol"),
        sa.CheckConstraint("kind IN ('HOLDING','WATCH')", name="ck_tracked_kind"),
        sa.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_tracked_quantity_positive"),
        sa.CheckConstraint("average_cost IS NULL OR average_cost >= 0", name="ck_tracked_cost_nonnegative"),
        sa.CheckConstraint("average_cost IS NULL OR quantity IS NOT NULL", name="ck_tracked_cost_requires_quantity"),
        sa.CheckConstraint("kind <> 'WATCH' OR (quantity IS NULL AND average_cost IS NULL)", name="ck_tracked_watch_without_holdings"),
    )


def downgrade() -> None:
    # A downgrade would delete real private holdings. Explicitly forbidden.
    raise RuntimeError("Portfolio downgrade forbidden. Restore via user-approved recovery procedure.")
