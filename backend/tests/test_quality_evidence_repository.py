"""MD-04C3 evidence repository fail-closed synthetic unit tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.md04_finality import FinalityGapReport, UNVERIFIED_REASONS
from app.quality_evidence_repository import (
    QualityEvidenceStorageError, insert_unverified_evidence,
)

REVIEWED = datetime(2026, 11, 20, 2, 5, tzinfo=timezone.utc)


def report():
    return FinalityGapReport(
        availability="UNFINALIZED", reviewed_rows=1,
        blockers=UNVERIFIED_REASONS, quality_status="PARTIAL",
    )


def test_default_write_is_denied_before_even_session_usage():
    with pytest.raises(QualityEvidenceStorageError, match="QUALITY_EVIDENCE_WRITE_DISABLED"):
        insert_unverified_evidence(None, uuid4(), report(), reviewed_at=REVIEWED)


@pytest.mark.parametrize("field,value", [
    ("availability", "UNAVAILABLE"),
    ("reviewed_rows", 0),
    ("reviewed_rows", 2),
    ("quality_status", "VALID"),
    ("blockers", ()),
    ("blockers", ("CUSTOM",)),
    ("is_final", True),
    ("source_observed_at", REVIEWED),
    ("promotion_allowed", True),
    ("publication_allowed", True),
    ("analysis_allowed", True),
    ("automatic_storage_allowed", True),
])
def test_forged_metadata_refused_without_writes(field, value):
    with Session() as db:
        with pytest.raises(QualityEvidenceStorageError, match="QUALITY_EVIDENCE_FINALITY_NOT_ATTESTED"):
            insert_unverified_evidence(
                db, uuid4(), replace(report(), **{field: value}),
                reviewed_at=REVIEWED, allow_write=True,
            )


@pytest.mark.parametrize("bad_time", [
    datetime(2026, 11, 20, 2, 5),
    None, "2026-11-20", True,
])
def test_bad_review_clock_is_rejected(bad_time):
    with Session() as db:
        with pytest.raises(QualityEvidenceStorageError, match="QUALITY_EVIDENCE_INPUT_INVALID"):
            insert_unverified_evidence(
                db, uuid4(), report(), reviewed_at=bad_time, allow_write=True,
            )


def test_wrong_types_are_rejected_before_sql():
    with Session() as db:
        for identifier, bad_report in [
            ("synthetic", report()), (uuid4(), object()),
        ]:
            with pytest.raises(QualityEvidenceStorageError, match="QUALITY_EVIDENCE_INPUT_INVALID"):
                insert_unverified_evidence(
                    db, identifier, bad_report, reviewed_at=REVIEWED, allow_write=True,
                )


def test_only_missing_bar_reached_with_explicit_write_and_valid_evidence():
    # No engine is bound; this proves validation stops before any publication
    # gate and the dedicated integration test covers real isolated PostgreSQL.
    with Session() as db:
        with pytest.raises(Exception):
            insert_unverified_evidence(
                db, uuid4(), report(), reviewed_at=REVIEWED, allow_write=True,
            )
