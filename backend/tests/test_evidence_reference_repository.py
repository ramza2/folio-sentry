"""MD-04C4 synthetic, price-free provenance validation tests."""
from datetime import datetime, timedelta, timezone
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.evidence_reference_models import EvidenceReferenceRevision
from app.evidence_reference_repository import (
    EvidenceReferenceError, _event_hash, _validate_url,
    append_unverified_reference, verify_reference_chain,
)

AUDIT = uuid4()
NOW = datetime(2026, 11, 23, 8, 0, tzinfo=timezone.utc)
DOC = hashlib.sha256(b"synthetic-reference-only").hexdigest()
KIS = "https://apiportal.koreainvestment.com/apiservice"
NYSE = "https://www.nyse.com/trade/hours-calendars"


def values(**updates):
    base = dict(
        revision_no=1, event_type="RECORDED", source_kind="KIS_DOCUMENT",
        reference_url=KIS, document_version="v1",
        document_sha256=DOC, recorded_at=NOW,
    )
    base.update(updates)
    return base


def test_default_write_refused_without_database():
    with pytest.raises(EvidenceReferenceError, match="REFERENCE_WRITE_DISABLED"):
        append_unverified_reference(None, AUDIT, **values())


@pytest.mark.parametrize("change", [
    {"revision_no": True}, {"revision_no": 0}, {"revision_no": "2"},
    {"event_type": "FINAL"}, {"event_type": True},
    {"document_version": "v1/corrected"},
    {"document_version": " "}, {"document_version": "X" * 65},
    {"document_sha256": "0" * 63}, {"document_sha256": "Z" * 64},
    {"recorded_at": datetime(2026, 11, 23, 8, 0)},
    {"recorded_at": "now"},
])
def test_untrusted_version_hash_and_clock_fail_before_db(change):
    with Session() as session:
        with pytest.raises(EvidenceReferenceError, match="REFERENCE_INPUT_INVALID"):
            append_unverified_reference(
                session, AUDIT, **values(**change), allow_write=True
            )


@pytest.mark.parametrize("url,kind", [
    ("http://apiportal.koreainvestment.com/apiservice", "KIS_DOCUMENT"),
    ("https://evil.example/path", "KIS_DOCUMENT"),
    ("https://apiportal.koreainvestment.com@evil.example/", "KIS_DOCUMENT"),
    ("https://apiportal.koreainvestment.com/?token=SECRET", "KIS_DOCUMENT"),
    ("https://apiportal.koreainvestment.com/#token", "KIS_DOCUMENT"),
    ("https://apiportal.koreainvestment.com:443/", "KIS_DOCUMENT"),
    ("https://github.com/random/other-repo/file", "KIS_DOCUMENT"),
    ("https://apiportal.koreainvestment.com/apiservice", "EXCHANGE_NOTICE"),
    ("https://www.nyse.com/trade/hours-calendars", "KIS_DOCUMENT"),
    ("https://kind.krx.co.kr/a%2Fsecret", "EXCHANGE_NOTICE"),
    ("https://www.nyse.com/a/../b", "EXCHANGE_NOTICE"),
    ("https://www.nyse.com/unsafe path", "EXCHANGE_NOTICE"),
])
def test_source_whitelist_and_sensitive_url_payloads_refused(url, kind):
    with pytest.raises(EvidenceReferenceError):
        _validate_url(kind, url)


def test_synthetic_official_domain_urls_are_only_format_checks():
    _validate_url("KIS_DOCUMENT", KIS)
    _validate_url("KIS_DOCUMENT", "https://github.com/koreainvestment/open-trading-api/tree/main")
    _validate_url("EXCHANGE_NOTICE", NYSE)
    _validate_url("EXCHANGE_NOTICE", "https://global.krx.co.kr/contents")
    with pytest.raises(EvidenceReferenceError, match="REFERENCE_SOURCE_INVALID"):
        _validate_url("UNKNOWN", NYSE)


def fake_event(index, kind, event_type, url, doc_version, doc_hash, at, previous):
    digest = _event_hash(
        AUDIT, index, event_type, kind, url, doc_version, doc_hash, at, previous,
    )
    return EvidenceReferenceRevision(
        quality_evidence_id=AUDIT, revision_no=index,
        event_type=event_type, source_kind=kind, reference_url=url,
        document_version=doc_version, document_sha256=doc_hash,
        recorded_at=at, previous_event_sha256=previous, event_sha256=digest,
        verification_status="UNVERIFIED_REFERENCE", publication_allowed=False,
    )


def test_three_reference_versions_and_retraction_are_not_finality_proof():
    first = fake_event(1, "KIS_DOCUMENT", "RECORDED", KIS, "v1", DOC, NOW, None)
    next_at = NOW + timedelta(minutes=1)
    corrected = fake_event(
        2, "EXCHANGE_NOTICE", "CORRECTED", NYSE, "v2", DOC, next_at, first.event_sha256
    )
    last_at = next_at + timedelta(minutes=1)
    retracted = fake_event(
        3, "EXCHANGE_NOTICE", "RETRACTED", NYSE, "v3", DOC, last_at, corrected.event_sha256
    )
    assert verify_reference_chain([first, corrected, retracted])
    assert not verify_reference_chain([corrected, first])
    assert not verify_reference_chain([first, retracted])
    first.document_version = "tampered"
    assert not verify_reference_chain([first, corrected, retracted])


def test_forged_promotion_and_retraction_continuation_denied():
    first = fake_event(1, "KIS_DOCUMENT", "RECORDED", KIS, "v1", DOC, NOW, None)
    first.publication_allowed = True
    assert not verify_reference_chain([first])
    first.publication_allowed = False
    first.verification_status = "VERIFIED"
    assert not verify_reference_chain([first])
    first.verification_status = "UNVERIFIED_REFERENCE"
    second = fake_event(
        2, "KIS_DOCUMENT", "RETRACTED", KIS, "v2", DOC,
        NOW + timedelta(minutes=1), first.event_sha256,
    )
    third = fake_event(
        3, "KIS_DOCUMENT", "CORRECTED", KIS, "v3", DOC,
        NOW + timedelta(minutes=2), second.event_sha256,
    )
    assert verify_reference_chain([first, second])
    assert not verify_reference_chain([first, second, third])
