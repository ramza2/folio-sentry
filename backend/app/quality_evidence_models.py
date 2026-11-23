"""MD-04C3: price-free, strictly unverified quality-evidence snapshots.

An additive, independently versioned table: a quality audit is NOT a source
observation, provider-finality assertion, verified adjustment or price itself.
No HTTP endpoint, price output, KIS network, scheduler, or production install.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON,
    String, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.auth_models import AuthBase


class PriceQualityEvidence(AuthBase):
    __tablename__ = "price_quality_evidence"
    __table_args__ = (
        UniqueConstraint(
            "price_bar_id", "policy_version",
            name="uq_price_quality_bar_policy",
        ),
        Index("ix_price_quality_bar", "price_bar_id"),
        CheckConstraint(
            "policy_version = 'MD04C3_V1'",
            name="ck_price_quality_version_v1",
        ),
        CheckConstraint(
            "evidence_status = 'UNVERIFIED'",
            name="ck_price_quality_unverified",
        ),
        CheckConstraint(
            "provider_finality = 'UNATTESTED'",
            name="ck_price_quality_finality_unattested",
        ),
        CheckConstraint(
            "source_observed_at IS NULL",
            name="ck_price_quality_no_observed_at",
        ),
        CheckConstraint(
            "basis_attested = false AND correction_attested = false "
            "AND corporate_action_attested = false",
            name="ck_price_quality_missing_proofs",
        ),
        CheckConstraint(
            "is_final = false AND publication_allowed = false "
            "AND analysis_allowed = false",
            name="ck_price_quality_never_published",
        ),
        CheckConstraint(
            "reviewed_rows = 1",
            name="ck_price_quality_one_bar_review",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    price_bar_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("price_bar.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_finality: Mapped[str] = mapped_column(String(32), nullable=False)
    source_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    basis_attested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    correction_attested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    corporate_action_attested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    analysis_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    blocker_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
