"""Create single-owner authentication tables (no real portfolio or demo data).

Revision ID: 20261119_auth01
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "20261119_auth01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_owner",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_auth_one_owner"),
    )
    op.create_table(
        "auth_session",
        sa.Column("id_hash", sa.String(length=64), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("auth_owner.id", ondelete="CASCADE"), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("last_seen_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_auth_session_owner_expiry", "auth_session", ["owner_id", "expires_at"])


def downgrade() -> None:
    # This drops auth credentials/sessions. Not safe to run on a live deployment.
    raise RuntimeError("Auth schema downgrade is intentionally blocked; restore from a verified backup.")
