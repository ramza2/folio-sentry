"""MD-04C4 additive, unverified source-reference correction history.

Revision ID: 20261123_quality02
Revises: 20261123_quality01

Only use on an ephemeral CI database; operating MiniPC migration is NOT approved.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261123_quality02"
down_revision = "20261123_quality01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_reference_revision",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "quality_evidence_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("price_quality_evidence.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("reference_url", sa.String(512), nullable=False),
        sa.Column("document_version", sa.String(64), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_event_sha256", sa.String(64), nullable=True),
        sa.Column("event_sha256", sa.String(64), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("publication_allowed", sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            "quality_evidence_id", "revision_no",
            name="uq_evidence_reference_revision",
        ),
        sa.CheckConstraint("revision_no >= 1", name="ck_reference_positive_revision"),
        sa.CheckConstraint(
            "event_type IN ('RECORDED','CORRECTED','RETRACTED')",
            name="ck_reference_event_type",
        ),
        sa.CheckConstraint(
            "source_kind IN ('KIS_DOCUMENT','EXCHANGE_NOTICE')",
            name="ck_reference_source_kind",
        ),
        sa.CheckConstraint(
            "verification_status = 'UNVERIFIED_REFERENCE'",
            name="ck_reference_never_verified",
        ),
        sa.CheckConstraint(
            "publication_allowed = false", name="ck_reference_never_published",
        ),
        sa.CheckConstraint(
            "length(document_sha256) = 64 AND length(event_sha256) = 64",
            name="ck_reference_digest_length",
        ),
        sa.CheckConstraint(
            "(revision_no = 1 AND previous_event_sha256 IS NULL AND event_type = 'RECORDED') "
            "OR (revision_no > 1 AND previous_event_sha256 IS NOT NULL "
            "AND length(previous_event_sha256) = 64 AND event_type IN ('CORRECTED','RETRACTED'))",
            name="ck_reference_revision_link",
        ),
    )
    op.create_index(
        "ix_evidence_reference_quality",
        "evidence_reference_revision", ["quality_evidence_id"],
    )
    # Database-level append-only for ordinary INSERT/UPDATE/DELETE roles.
    # DB owner/superuser can alter triggers: not an external audit guarantee.
    op.execute("""
        CREATE FUNCTION folio_md04c4_block_reference_mutation()
        RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'EVIDENCE_REFERENCE_APPEND_ONLY';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER tr_evidence_reference_append_only
        BEFORE UPDATE OR DELETE ON evidence_reference_revision
        FOR EACH ROW
        EXECUTE FUNCTION folio_md04c4_block_reference_mutation()
    """)


def downgrade() -> None:
    raise RuntimeError("Evidence reference history downgrade forbidden; approved backup/restore required.")
