"""MD-04C4 opt-in source-reference revision writer; price-free/offline only.

URL allowlisting is a formatting/provenance hygiene check, NOT supplier
authentication, finality proof, or permission to fetch a remote resource.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evidence_reference_models import EvidenceReferenceRevision
from app.quality_evidence_models import PriceQualityEvidence

_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_OFFICIAL_HOSTS = {
    "KIS_DOCUMENT": frozenset({
        "apiportal.koreainvestment.com",
        "github.com",
    }),
    "EXCHANGE_NOTICE": frozenset({
        "global.krx.co.kr", "kind.krx.co.kr",
        "www.nyse.com", "www.nasdaq.com",
    }),
}


class EvidenceReferenceError(ValueError):
    """Static code only: no source identifiers, URLs, hashes or prices."""


@dataclass(frozen=True, slots=True)
class ReferenceWriteResult:
    inserted: int
    unchanged: int
    event_sha256: str


def _validate_url(kind: str, url: str) -> None:
    if type(kind) is not str or kind not in _OFFICIAL_HOSTS or type(url) is not str or len(url) > 512:
        raise EvidenceReferenceError("REFERENCE_SOURCE_INVALID")
    if not url or any(c.isspace() or ord(c) < 32 for c in url):
        raise EvidenceReferenceError("REFERENCE_URL_INVALID")
    try:
        parsed = urlsplit(url)
        safe = (
            parsed.scheme == "https"
            and parsed.hostname in _OFFICIAL_HOSTS[kind]
            and parsed.username is None
            and parsed.password is None
            and parsed.port is None
            and not parsed.query
            and not parsed.fragment
            and ".." not in parsed.path
            and "%" not in parsed.path
            and "//" not in parsed.path
            and parsed.geturl() == url
        )
    except ValueError:
        safe = False
    if not safe:
        raise EvidenceReferenceError("REFERENCE_URL_INVALID")
    if parsed.hostname == "github.com" and not parsed.path.startswith(
        "/koreainvestment/open-trading-api/"
    ):
        raise EvidenceReferenceError("REFERENCE_URL_INVALID")


def _event_hash(
    quality_evidence_id: UUID, revision_no: int, event_type: str,
    source_kind: str, reference_url: str, document_version: str,
    document_sha256: str, recorded_at: datetime, previous: str | None,
) -> str:
    canonical = json.dumps({
        "schema": "MD04C4_V1",
        "quality_evidence_id": str(quality_evidence_id),
        "revision_no": revision_no,
        "event_type": event_type,
        "source_kind": source_kind,
        "reference_url": reference_url,
        "document_version": document_version,
        "document_sha256": document_sha256,
        "recorded_at_utc": recorded_at.astimezone(timezone.utc).isoformat(timespec="microseconds"),
        "previous_event_sha256": previous,
        "verification_status": "UNVERIFIED_REFERENCE",
        "publication_allowed": False,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def append_unverified_reference(
    session: Session,
    quality_evidence_id: UUID,
    *,
    revision_no: int,
    event_type: str,
    source_kind: str,
    reference_url: str,
    document_version: str,
    document_sha256: str,
    recorded_at: datetime,
    allow_write: bool = False,
) -> ReferenceWriteResult:
    """Append exactly one unverified revision under a caller-owned transaction.

    Replays of identical latest events are idempotent. The audit row is locked
    to serialize concurrent appends by this repository. Direct SQL admins
    remain outside this application's trust boundary.
    """
    if allow_write is not True:
        raise EvidenceReferenceError("REFERENCE_WRITE_DISABLED")
    if (
        not isinstance(session, Session)
        or not isinstance(quality_evidence_id, UUID)
        or type(revision_no) is not int or revision_no < 1
        or type(event_type) is not str
        or event_type not in ("RECORDED", "CORRECTED", "RETRACTED")
        or type(document_version) is not str
        or _VERSION.fullmatch(document_version) is None
        or type(document_sha256) is not str
        or _SHA256.fullmatch(document_sha256) is None
        or not isinstance(recorded_at, datetime)
        or recorded_at.tzinfo is None or recorded_at.utcoffset() is None
    ):
        raise EvidenceReferenceError("REFERENCE_INPUT_INVALID")
    _validate_url(source_kind, reference_url)
    timestamp = recorded_at.astimezone(timezone.utc)

    with session.begin_nested():
        evidence = session.scalars(
            select(PriceQualityEvidence)
            .where(PriceQualityEvidence.id == quality_evidence_id)
            .with_for_update()
        ).one_or_none()
        if evidence is None:
            raise EvidenceReferenceError("REFERENCE_QUALITY_EVIDENCE_MISSING")
        if (
            evidence.policy_version != "MD04C3_V1"
            or evidence.evidence_status != "UNVERIFIED"
            or evidence.provider_finality != "UNATTESTED"
            or evidence.source_observed_at is not None
            or evidence.is_final is not False
            or evidence.publication_allowed is not False
            or evidence.analysis_allowed is not False
        ):
            raise EvidenceReferenceError("REFERENCE_FINALITY_UNVERIFIED_REQUIRED")
        if (
            evidence.reviewed_at is None
            or evidence.reviewed_at.tzinfo is None
            or timestamp < evidence.reviewed_at.astimezone(timezone.utc)
        ):
            raise EvidenceReferenceError("REFERENCE_RECORD_TIME_INVALID")
        latest = session.scalars(
            select(EvidenceReferenceRevision)
            .where(EvidenceReferenceRevision.quality_evidence_id == quality_evidence_id)
            .order_by(EvidenceReferenceRevision.revision_no.desc()).limit(1)
        ).one_or_none()
        if latest is None:
            if revision_no != 1 or event_type != "RECORDED":
                raise EvidenceReferenceError("REFERENCE_REVISION_SEQUENCE_INVALID")
            previous = None
        elif revision_no == latest.revision_no:
            previous = latest.previous_event_sha256
        elif revision_no == latest.revision_no + 1 and latest.event_type != "RETRACTED":
            if event_type not in ("CORRECTED", "RETRACTED"):
                raise EvidenceReferenceError("REFERENCE_REVISION_SEQUENCE_INVALID")
            if timestamp <= latest.recorded_at.astimezone(timezone.utc):
                raise EvidenceReferenceError("REFERENCE_EVENT_CLOCK_NOT_MONOTONIC")
            previous = latest.event_sha256
        else:
            raise EvidenceReferenceError("REFERENCE_REVISION_SEQUENCE_INVALID")

        event_hash = _event_hash(
            quality_evidence_id, revision_no, event_type, source_kind,
            reference_url, document_version, document_sha256,
            timestamp, previous,
        )
        if latest is not None and revision_no == latest.revision_no:
            if latest.event_sha256 != event_hash:
                raise EvidenceReferenceError("REFERENCE_REVISION_CONFLICT")
            return ReferenceWriteResult(inserted=0, unchanged=1, event_sha256=event_hash)

        session.add(EvidenceReferenceRevision(
            quality_evidence_id=quality_evidence_id,
            revision_no=revision_no, event_type=event_type,
            source_kind=source_kind, reference_url=reference_url,
            document_version=document_version,
            document_sha256=document_sha256, recorded_at=timestamp,
            previous_event_sha256=previous,
            event_sha256=event_hash,
            verification_status="UNVERIFIED_REFERENCE",
            publication_allowed=False,
        ))
        session.flush()
    return ReferenceWriteResult(inserted=1, unchanged=0, event_sha256=event_hash)


def verify_reference_chain(events: list[EvidenceReferenceRevision]) -> bool:
    """Read-only integrity check. A matching hash is not provenance attestation."""
    if type(events) is not list or not events:
        return False
    previous = None
    source_audit = None
    for index, event in enumerate(events, 1):
        if not isinstance(event, EvidenceReferenceRevision):
            return False
        if source_audit is None:
            source_audit = event.quality_evidence_id
        if (
            event.quality_evidence_id != source_audit
            or event.revision_no != index
            or event.previous_event_sha256 != previous
            or event.verification_status != "UNVERIFIED_REFERENCE"
            or event.publication_allowed is not False
            or (index == 1 and event.event_type != "RECORDED")
            or (index > 1 and event.event_type not in ("CORRECTED","RETRACTED"))
            or (index > 1 and events[index - 2].event_type == "RETRACTED")
        ):
            return False
        try:
            _validate_url(event.source_kind, event.reference_url)
            if _VERSION.fullmatch(event.document_version) is None                     or _SHA256.fullmatch(event.document_sha256) is None:
                return False
            expected = _event_hash(
                source_audit, event.revision_no, event.event_type,
                event.source_kind, event.reference_url,
                event.document_version, event.document_sha256,
                event.recorded_at, previous,
            )
        except (EvidenceReferenceError, TypeError, ValueError, AttributeError):
            return False
        if event.event_sha256 != expected:
            return False
        previous = event.event_sha256
    return True
