"""MD-04C4 reference revision log, not provider-finality evidence.

Only source-reference metadata and content fingerprints, no market prices,
raw documents, credentials, claims of authenticity, or public API.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    String, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.auth_models import AuthBase


class EvidenceReferenceRevision(AuthBase):
    __tablename__ = "evidence_reference_revision"
    __table_args__ = (
        UniqueConstraint(
            "quality_evidence_id", "revision_no", name="uq_evidence_reference_revision"
        ),
        Index("ix_evidence_reference_quality", "quality_evidence_id"),
        CheckConstraint("revision_no >= 1", name="ck_reference_positive_revision"),
        CheckConstraint(
            "event_type IN ('RECORDED','CORRECTED','RETRACTED')",
            name="ck_reference_event_type",
        ),
        CheckConstraint(
            "source_kind IN ('KIS_DOCUMENT','EXCHANGE_NOTICE')",
            name="ck_reference_source_kind",
        ),
        CheckConstraint(
            "verification_status = 'UNVERIFIED_REFERENCE'",
            name="ck_reference_never_verified",
        ),
        CheckConstraint(
            "publication_allowed = false", name="ck_reference_never_published",
        ),
        CheckConstraint(
            "length(document_sha256) = 64 AND length(event_sha256) = 64",
            name="ck_reference_digest_length",
        ),
        CheckConstraint(
            "(revision_no = 1 AND previous_event_sha256 IS NULL AND event_type = 'RECORDED') "
            "OR (revision_no > 1 AND previous_event_sha256 IS NOT NULL "
            "AND length(previous_event_sha256) = 64 AND event_type IN ('CORRECTED','RETRACTED'))",
            name="ck_reference_revision_link",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    quality_evidence_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("price_quality_evidence.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_url: Mapped[str] = mapped_column(String(512), nullable=False)
    document_version: Mapped[str] = mapped_column(String(64), nullable=False)
    document_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_event_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    publication_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
