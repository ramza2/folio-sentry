"""MD-04C6: offline supplier-proof collection checklist, NEVER finality approval.

Only opaque, manually supplied reference metadata is accepted. This module
does not read documents or prices, validate provenance, call KIS, create DB
sessions, or grant storage/publication/analysis/promotion permissions.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Literal

from app.md04_finality import UNVERIFIED_REASONS
from app.md04c5_source_review import DocumentationGapReview, Endpoint

EvidenceKind = Literal[
    "PROVIDER_OBSERVATION_RULE",
    "PROVIDER_FINAL_CLOSE_RULE",
    "ENDPOINT_BASIS_CONTRACT",
    "PROVIDER_CORRECTION_POLICY",
    "CORPORATE_ACTION_POLICY",
    "PROVIDER_SESSION_SCOPE",
    "EXCHANGE_CALENDAR_EXCEPTION_POLICY",
]
ReferenceClass = Literal["PROVIDER_POLICY_POINTER", "EXCHANGE_NOTICE_POINTER"]
Lifecycle = Literal["CANDIDATE", "RETRACTED"]

# A candidate pointer is never a verified supplier claim. The last two
# categories are separate: an exchange calendar cannot attest what KIS
# includes in a daily bar (regular / pre / after hours).
EVIDENCE_REQUIREMENTS: tuple[tuple[EvidenceKind, ReferenceClass], ...] = (
    ("PROVIDER_OBSERVATION_RULE", "PROVIDER_POLICY_POINTER"),
    ("PROVIDER_FINAL_CLOSE_RULE", "PROVIDER_POLICY_POINTER"),
    ("ENDPOINT_BASIS_CONTRACT", "PROVIDER_POLICY_POINTER"),
    ("PROVIDER_CORRECTION_POLICY", "PROVIDER_POLICY_POINTER"),
    ("CORPORATE_ACTION_POLICY", "PROVIDER_POLICY_POINTER"),
    ("PROVIDER_SESSION_SCOPE", "PROVIDER_POLICY_POINTER"),
    ("EXCHANGE_CALENDAR_EXCEPTION_POLICY", "EXCHANGE_NOTICE_POINTER"),
)

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,63}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceHandoffError(ValueError):
    """Fixed error code only; no identifiers, prices or private data."""


@dataclass(frozen=True, slots=True)
class CandidatePointer:
    """Unverified offline metadata, not a verified document/price observation."""

    endpoint: Endpoint
    requirement: EvidenceKind
    reference_class: ReferenceClass
    reference_code: str
    version_code: str
    document_sha256: str
    recorded_at: datetime
    lifecycle: Lifecycle = "CANDIDATE"


@dataclass(frozen=True, slots=True)
class EvidenceHandoffReview:
    """Human review may START after collecting references, not approve prices."""

    endpoint: Endpoint
    readiness: Literal["MISSING_CANDIDATE_REFERENCES", "METADATA_COMPLETE_HUMAN_REVIEW_REQUIRED"]
    candidate_requirements: tuple[EvidenceKind, ...]
    missing_requirements: tuple[EvidenceKind, ...]
    retracted_requirements: tuple[EvidenceKind, ...]
    blocker_codes: tuple[str, ...]
    review_status: Literal["HOLD_UNVERIFIED"] = "HOLD_UNVERIFIED"
    source_authenticity_verified: Literal[False] = False
    endpoint_mapping_verified: Literal[False] = False
    source_observed_at: None = None
    provider_finality_verified: Literal[False] = False
    human_approval_verified: Literal[False] = False
    policy_approval_verified: Literal[False] = False
    is_final: Literal[False] = False
    promotion_allowed: Literal[False] = False
    publication_allowed: Literal[False] = False
    analysis_allowed: Literal[False] = False
    automatic_storage_allowed: Literal[False] = False


def _validate_c5(endpoint: Endpoint, doc: DocumentationGapReview) -> None:
    if not isinstance(doc, DocumentationGapReview) or doc.endpoint != endpoint:
        raise EvidenceHandoffError("MD04C6_DOCUMENT_REVIEW_SCOPE_INVALID")
    if (
        doc.review_status != "EVIDENCE_INSUFFICIENT"
        or type(doc.blocker_codes) is not tuple
        or doc.blocker_codes != UNVERIFIED_REASONS
        or doc.provider_observed_at is not None
        or doc.provider_finality_attested is not False
        or doc.price_basis_attested is not False
        or doc.correction_policy_attested is not False
        or doc.corporate_action_attested is not False
        or doc.is_final is not False
        or doc.promotion_allowed is not False
        or doc.publication_allowed is not False
        or doc.analysis_allowed is not False
        or doc.automatic_storage_allowed is not False
    ):
        raise EvidenceHandoffError("MD04C6_DOCUMENT_REVIEW_PROMOTION_FORBIDDEN")
    if endpoint == "KR_ITEMCHART":
        if doc.parameter_name != "FID_ORG_ADJ_PRC" or doc.mapping_note not in (
            "NOT_REVIEWED", "KR_DOCUMENTED_EXAMPLE_ONLY"
        ):
            raise EvidenceHandoffError("MD04C6_DOCUMENT_REVIEW_SCOPE_INVALID")
    elif doc.parameter_name != "MODP" or doc.mapping_note not in (
        "NOT_REVIEWED", "US_PARAMETER_ONLY", "US_EXAMPLE_WITHOUT_PROVIDER_ATTESTATION"
    ):
        raise EvidenceHandoffError("MD04C6_DOCUMENT_REVIEW_SCOPE_INVALID")


def inspect_supplier_evidence_handoff(
    endpoint: Endpoint,
    documentation_review: DocumentationGapReview,
    pointers: tuple[CandidatePointer, ...],
    *,
    now: datetime,
) -> EvidenceHandoffReview:
    """Assess only whether every distinct *candidate* reference is recorded.

    Even a complete candidate inventory is HOLD_UNVERIFIED. A separate,
    independently authenticated supplier evidence review, human approval,
    finality-policy design/PR and production safety approvals are required.
    """
    if type(endpoint) is not str or endpoint not in ("KR_ITEMCHART", "US_DAILYPRICE"):
        raise EvidenceHandoffError("MD04C6_ENDPOINT_INVALID")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise EvidenceHandoffError("MD04C6_CLOCK_INVALID")
    _validate_c5(endpoint, documentation_review)
    if type(pointers) is not tuple or len(pointers) > len(EVIDENCE_REQUIREMENTS):
        raise EvidenceHandoffError("MD04C6_POINTER_COLLECTION_INVALID")

    expected = dict(EVIDENCE_REQUIREMENTS)
    states: dict[str, str] = {}
    for candidate in pointers:
        if not isinstance(candidate, CandidatePointer):
            raise EvidenceHandoffError("MD04C6_POINTER_INVALID")
        if (
            type(candidate.endpoint) is not str
            or candidate.endpoint != endpoint
            or type(candidate.requirement) is not str
            or candidate.requirement not in expected
            or candidate.requirement in states
            or type(candidate.reference_class) is not str
            or candidate.reference_class != expected[candidate.requirement]
        ):
            raise EvidenceHandoffError("MD04C6_POINTER_SCOPE_OR_DUPLICATE")
        if (
            type(candidate.reference_code) is not str
            or _CODE.fullmatch(candidate.reference_code) is None
            or type(candidate.version_code) is not str
            or _VERSION.fullmatch(candidate.version_code) is None
            or type(candidate.document_sha256) is not str
            or _SHA256.fullmatch(candidate.document_sha256) is None
            or type(candidate.lifecycle) is not str
            or candidate.lifecycle not in ("CANDIDATE", "RETRACTED")
            or not isinstance(candidate.recorded_at, datetime)
            or candidate.recorded_at.tzinfo is None
            or candidate.recorded_at.utcoffset() is None
            or candidate.recorded_at.astimezone(timezone.utc) > now.astimezone(timezone.utc)
        ):
            raise EvidenceHandoffError("MD04C6_POINTER_METADATA_INVALID")
        states[candidate.requirement] = candidate.lifecycle
    recorded = tuple(kind for kind, _ in EVIDENCE_REQUIREMENTS
                     if states.get(kind) == "CANDIDATE")
    retracted = tuple(kind for kind, _ in EVIDENCE_REQUIREMENTS
                      if states.get(kind) == "RETRACTED")
    missing = tuple(kind for kind, _ in EVIDENCE_REQUIREMENTS
                    if states.get(kind) != "CANDIDATE")
    return EvidenceHandoffReview(
        endpoint=endpoint,
        readiness="MISSING_CANDIDATE_REFERENCES" if missing
                  else "METADATA_COMPLETE_HUMAN_REVIEW_REQUIRED",
        candidate_requirements=recorded,
        missing_requirements=missing,
        retracted_requirements=retracted,
        blocker_codes=UNVERIFIED_REASONS,
    )
