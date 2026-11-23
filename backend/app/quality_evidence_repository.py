"""Explicit opt-in, caller-owned writes for UNVERIFIED metadata ONLY.

Never fetches KIS data, opens transactions/engines, commits, publishes a quote,
updates a price bar, or asserts provider observation/finality.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.md04_finality import FinalityGapReport, UNVERIFIED_REASONS
from app.price_models import PriceBar
from app.quality_evidence_models import PriceQualityEvidence

POLICY = "MD04C3_V1"


class QualityEvidenceStorageError(ValueError):
    """Fixed non-sensitive error code."""


@dataclass(frozen=True, slots=True)
class EvidenceWriteResult:
    inserted: int
    unchanged: int


def insert_unverified_evidence(
    session: Session,
    price_bar_id: UUID,
    report: FinalityGapReport,
    *,
    reviewed_at: datetime,
    allow_write: bool = False,
) -> EvidenceWriteResult:
    """Store a price-free per-bar audit at most once per policy revision.

    Caller supplies a transaction, an already stored PARTIAL bar, and a
    one-bar MD04B report. Conflicting records fail closed; no overwrite.
    """
    if not allow_write:
        raise QualityEvidenceStorageError("QUALITY_EVIDENCE_WRITE_DISABLED")
    if (
        not isinstance(session, Session)
        or not isinstance(price_bar_id, UUID)
        or not isinstance(report, FinalityGapReport)
        or not isinstance(reviewed_at, datetime)
        or reviewed_at.tzinfo is None
        or reviewed_at.utcoffset() is None
    ):
        raise QualityEvidenceStorageError("QUALITY_EVIDENCE_INPUT_INVALID")
    if (
        report.availability != "UNFINALIZED"
        or type(report.reviewed_rows) is not int
        or report.reviewed_rows != 1
        or report.quality_status != "PARTIAL"
        or tuple(report.blockers) != UNVERIFIED_REASONS
        or report.source_observed_at is not None
        or report.is_final is not False
        or report.promotion_allowed is not False
        or report.publication_allowed is not False
        or report.analysis_allowed is not False
        or report.automatic_storage_allowed is not False
    ):
        raise QualityEvidenceStorageError("QUALITY_EVIDENCE_FINALITY_NOT_ATTESTED")

    checked_at = reviewed_at.astimezone(timezone.utc)
    bar = session.get(PriceBar, price_bar_id)
    if bar is None:
        raise QualityEvidenceStorageError("QUALITY_EVIDENCE_BAR_NOT_FOUND")
    if (
        bar.timeframe != "1d"
        or bar.source != "KIS"
        or bar.price_basis not in ("RAW", "ADJUSTED")
        or bar.quality_status != "PARTIAL"
        or bar.is_final is not False
        or bar.source_observed_at is not None
    ):
        raise QualityEvidenceStorageError("QUALITY_EVIDENCE_BAR_UNVERIFIED")
    # A row cannot be audited before the system fetched it. The acquisition
    # time remains separate from the UNAVAILABLE provider observation time.
    fetched = bar.fetched_at
    if fetched is None or fetched.tzinfo is None or fetched.utcoffset() is None:
        raise QualityEvidenceStorageError("QUALITY_EVIDENCE_FETCH_TIME_INVALID")
    if checked_at < fetched.astimezone(timezone.utc):
        raise QualityEvidenceStorageError("QUALITY_EVIDENCE_REVIEW_PRECEDES_FETCH")

    expected = list(UNVERIFIED_REASONS)
    with session.begin_nested():
        statement = insert(PriceQualityEvidence).values(
            price_bar_id=price_bar_id,
            policy_version=POLICY,
            reviewed_at=checked_at,
            reviewed_rows=1,
            evidence_status="UNVERIFIED",
            provider_finality="UNATTESTED",
            source_observed_at=None,
            basis_attested=False,
            correction_attested=False,
            corporate_action_attested=False,
            is_final=False,
            publication_allowed=False,
            analysis_allowed=False,
            blocker_codes=expected,
        ).on_conflict_do_nothing(
            constraint="uq_price_quality_bar_policy",
        ).returning(PriceQualityEvidence.id)
        created = session.execute(statement).scalar_one_or_none()
        if created is not None:
            return EvidenceWriteResult(inserted=1, unchanged=0)
        existing = session.scalars(
            select(PriceQualityEvidence).where(
                PriceQualityEvidence.price_bar_id == price_bar_id,
                PriceQualityEvidence.policy_version == POLICY,
            )
        ).one_or_none()
        if (
            existing is None
            or existing.evidence_status != "UNVERIFIED"
            or existing.provider_finality != "UNATTESTED"
            or existing.source_observed_at is not None
            or existing.reviewed_rows != 1
            or existing.basis_attested is not False
            or existing.correction_attested is not False
            or existing.corporate_action_attested is not False
            or existing.is_final is not False
            or existing.publication_allowed is not False
            or existing.analysis_allowed is not False
            or existing.blocker_codes != expected
        ):
            raise QualityEvidenceStorageError("QUALITY_EVIDENCE_CONFLICT_NEEDS_REVIEW")
        # Original reviewed_at is preserved for genuinely identical reviews.
        return EvidenceWriteResult(inserted=0, unchanged=1)
