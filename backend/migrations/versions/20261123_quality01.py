"""MD-04C3 additive unverified quality evidence, never live/valid.

Revision ID: 20261123_quality01
Revises: 20261120_pricebar01

Do NOT run on the MiniPC operating DB without a separate explicit approval.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261123_quality01"
down_revision = "20261120_pricebar01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_quality_evidence",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "price_bar_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("price_bar.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_rows", sa.Integer(), nullable=False),
        sa.Column("evidence_status", sa.String(32), nullable=False),
        sa.Column("provider_finality", sa.String(32), nullable=False),
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("basis_attested", sa.Boolean(), nullable=False),
        sa.Column("correction_attested", sa.Boolean(), nullable=False),
        sa.Column("corporate_action_attested", sa.Boolean(), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("publication_allowed", sa.Boolean(), nullable=False),
        sa.Column("analysis_allowed", sa.Boolean(), nullable=False),
        sa.Column("blocker_codes", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "price_bar_id", "policy_version", name="uq_price_quality_bar_policy",
        ),
        sa.CheckConstraint(
            "policy_version = 'MD04C3_V1'",
            name="ck_price_quality_version_v1",
        ),
        sa.CheckConstraint(
            "evidence_status = 'UNVERIFIED'",
            name="ck_price_quality_unverified",
        ),
        sa.CheckConstraint(
            "provider_finality = 'UNATTESTED'",
            name="ck_price_quality_finality_unattested",
        ),
        sa.CheckConstraint(
            "source_observed_at IS NULL", name="ck_price_quality_no_observed_at",
        ),
        sa.CheckConstraint(
            "basis_attested = false AND correction_attested = false "
            "AND corporate_action_attested = false",
            name="ck_price_quality_missing_proofs",
        ),
        sa.CheckConstraint(
            "is_final = false AND publication_allowed = false "
            "AND analysis_allowed = false",
            name="ck_price_quality_never_published",
        ),
        sa.CheckConstraint(
            "reviewed_rows = 1",
            name="ck_price_quality_one_bar_review",
        ),
    )
    op.create_index(
        "ix_price_quality_bar", "price_quality_evidence", ["price_bar_id"],
    )


def downgrade() -> None:
    # Historical quality audits must not be silently dropped. Explicit
    # backup/restore review is required for schema reversal.
    raise RuntimeError("Quality evidence downgrade forbidden; use approved backup/restore.")
