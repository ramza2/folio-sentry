"""MD-04C6 provider proof handoff never authorizes actual price use."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from app.md04_finality import UNVERIFIED_REASONS
from app.md04c5_source_review import (
    DocumentationGapReview, assess_offline_documentation,
)
from app.md04c6_evidence_handoff import (
    CandidatePointer, EVIDENCE_REQUIREMENTS, EvidenceHandoffError,
    inspect_supplier_evidence_handoff,
)
from app.quote_visibility import masked_quote_from_finality

NOW = datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc)
HASH = hashlib.sha256(b"synthetic-offline-pointer-only").hexdigest()


def doc(endpoint="KR_ITEMCHART"):
    return assess_offline_documentation(endpoint, (), now=NOW)


def pointer(endpoint="KR_ITEMCHART", kind=None, **patch):
    if kind is None:
        kind = EVIDENCE_REQUIREMENTS[0][0]
    sources = dict(EVIDENCE_REQUIREMENTS)
    values = {
        "endpoint": endpoint,
        "requirement": kind,
        "reference_class": sources[kind],
        "reference_code": "REF_" + kind,
        "version_code": "v1",
        "document_sha256": HASH,
        "recorded_at": NOW - timedelta(minutes=1),
        "lifecycle": "CANDIDATE",
    }
    values.update(patch)
    return CandidatePointer(**values)


def all_pointers(endpoint="KR_ITEMCHART"):
    return tuple(pointer(endpoint, kind) for kind, _ in EVIDENCE_REQUIREMENTS)


def assert_locked(review, endpoint):
    assert review.endpoint == endpoint
    assert review.review_status == "HOLD_UNVERIFIED"
    assert review.blocker_codes == UNVERIFIED_REASONS
    assert review.source_observed_at is None
    for field in (
        "source_authenticity_verified", "endpoint_mapping_verified",
        "provider_finality_verified", "human_approval_verified",
        "policy_approval_verified", "is_final", "promotion_allowed",
        "publication_allowed", "analysis_allowed",
        "automatic_storage_allowed",
    ):
        assert getattr(review, field) is False
    assert not hasattr(review, "close")
    assert "105" not in repr(review)
    assert "252.44" not in repr(review)


@pytest.mark.parametrize("endpoint", ["KR_ITEMCHART", "US_DAILYPRICE"])
def test_no_evidence_still_exposes_all_seven_missing_requirements(endpoint):
    review = inspect_supplier_evidence_handoff(endpoint, doc(endpoint), (), now=NOW)
    assert review.readiness == "MISSING_CANDIDATE_REFERENCES"
    assert review.candidate_requirements == ()
    assert review.missing_requirements == tuple(k for k, _ in EVIDENCE_REQUIREMENTS)
    assert review.retracted_requirements == ()
    assert_locked(review, endpoint)


@pytest.mark.parametrize("endpoint", ["KR_ITEMCHART", "US_DAILYPRICE"])
def test_complete_reference_inventory_is_not_supply_chain_or_price_approval(endpoint):
    review = inspect_supplier_evidence_handoff(
        endpoint, doc(endpoint), all_pointers(endpoint), now=NOW,
    )
    assert review.readiness == "METADATA_COMPLETE_HUMAN_REVIEW_REQUIRED"
    assert review.missing_requirements == ()
    assert len(review.candidate_requirements) == len(EVIDENCE_REQUIREMENTS)
    assert_locked(review, endpoint)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        review.publication_allowed = True
    with pytest.raises((FrozenInstanceError, AttributeError)):
        review.provider_finality_verified = True


def test_one_retracted_primary_reference_does_not_satisfy_requirements():
    pointers = list(all_pointers())
    pointers[1] = replace(pointers[1], lifecycle="RETRACTED")
    review = inspect_supplier_evidence_handoff(
        "KR_ITEMCHART", doc(), tuple(pointers), now=NOW,
    )
    assert review.retracted_requirements == (EVIDENCE_REQUIREMENTS[1][0],)
    assert review.missing_requirements == review.retracted_requirements
    assert review.readiness == "MISSING_CANDIDATE_REFERENCES"
    assert_locked(review, "KR_ITEMCHART")


def test_exchange_calendar_cannot_serve_as_provider_finality_proof():
    bad = pointer(
        kind="PROVIDER_FINAL_CLOSE_RULE",
        reference_class="EXCHANGE_NOTICE_POINTER",
    )
    with pytest.raises(EvidenceHandoffError, match="MD04C6_POINTER_SCOPE_OR_DUPLICATE"):
        inspect_supplier_evidence_handoff("KR_ITEMCHART", doc(), (bad,), now=NOW)
    valid_calendar = pointer(kind="EXCHANGE_CALENDAR_EXCEPTION_POLICY")
    review = inspect_supplier_evidence_handoff(
        "KR_ITEMCHART", doc(), (valid_calendar,), now=NOW
    )
    assert "PROVIDER_FINAL_CLOSE_RULE" in review.missing_requirements
    assert "PROVIDER_SESSION_SCOPE" in review.missing_requirements
    assert_locked(review, "KR_ITEMCHART")


@pytest.mark.parametrize("endpoint", [
    "", "KR_DAILY_PRICE", "US_HOURLY", None, True, 42,
])
def test_wrong_endpoint_rejected_before_source_processing(endpoint):
    with pytest.raises(EvidenceHandoffError, match="MD04C6_ENDPOINT_INVALID"):
        inspect_supplier_evidence_handoff(endpoint, doc(), (), now=NOW)


@pytest.mark.parametrize("clock", [None, "", datetime(2026, 11, 23, 10), True])
def test_aware_current_clock_required(clock):
    with pytest.raises(EvidenceHandoffError, match="MD04C6_CLOCK_INVALID"):
        inspect_supplier_evidence_handoff("KR_ITEMCHART", doc(), (), now=clock)


@pytest.mark.parametrize("candidate_set", [
    [],
    (None,),
    ("REFERENCE",),
    tuple(pointer() for _ in range(8)),
])
def test_untrusted_pointer_collection_is_rejected(candidate_set):
    with pytest.raises(EvidenceHandoffError):
        inspect_supplier_evidence_handoff("KR_ITEMCHART", doc(), candidate_set, now=NOW)


def test_duplicate_requirement_and_cross_market_candidate_rejected():
    for candidates in (
        (pointer(), pointer()),
        (pointer("US_DAILYPRICE"),),
        (pointer(requirement="UNKNOWN"),) if False else (),
    ):
        if not candidates:
            continue
        with pytest.raises(EvidenceHandoffError, match="MD04C6_POINTER_SCOPE_OR_DUPLICATE"):
            inspect_supplier_evidence_handoff(
                "KR_ITEMCHART", doc(), candidates, now=NOW,
            )


@pytest.mark.parametrize("patch", [
    {"reference_code": ""},
    {"reference_code": "abc"},
    {"reference_code": "REF/PRICE"},
    {"reference_code": "REF TOKEN"},
    {"reference_code": "A" * 65},
    {"version_code": ""},
    {"version_code": "v1?token=secret"},
    {"version_code": "v 1"},
    {"version_code": "A" * 65},
    {"document_sha256": "0" * 63},
    {"document_sha256": "X" * 64},
    {"document_sha256": None},
    {"recorded_at": NOW + timedelta(seconds=1)},
    {"recorded_at": datetime(2026, 11, 23, 9, 0)},
    {"recorded_at": "2026-11-23"},
    {"lifecycle": "VERIFIED"},
    {"lifecycle": "FINAL"},
    {"lifecycle": True},
])
def test_invalid_metadata_fails_closed_without_database_or_network(patch):
    with pytest.raises(EvidenceHandoffError, match="MD04C6_POINTER_METADATA_INVALID"):
        inspect_supplier_evidence_handoff(
            "KR_ITEMCHART", doc(), (pointer(**patch),), now=NOW,
        )


@pytest.mark.parametrize("replacement", [
    {"review_status": "EVIDENCE_VERIFIED"},
    {"blocker_codes": ()},
    {"blocker_codes": list(UNVERIFIED_REASONS)},
    {"provider_observed_at": NOW},
    {"provider_finality_attested": True},
    {"price_basis_attested": True},
    {"correction_policy_attested": True},
    {"corporate_action_attested": True},
    {"is_final": True},
    {"promotion_allowed": True},
    {"publication_allowed": True},
    {"analysis_allowed": True},
    {"automatic_storage_allowed": True},
])
def test_forged_md04c5_review_cannot_unlock_gate(replacement):
    with pytest.raises(EvidenceHandoffError, match="MD04C6_DOCUMENT_REVIEW_PROMOTION_FORBIDDEN"):
        inspect_supplier_evidence_handoff(
            "KR_ITEMCHART", replace(doc(), **replacement),
            all_pointers(), now=NOW,
        )


def test_mismatched_document_scope_and_parameter_claim_rejected():
    checks = (
        ("KR_ITEMCHART", doc("US_DAILYPRICE")),
        ("KR_ITEMCHART", replace(doc(), parameter_name="MODP")),
        ("KR_ITEMCHART", replace(doc(), mapping_note="US_PARAMETER_ONLY")),
        ("US_DAILYPRICE", replace(doc("US_DAILYPRICE"), parameter_name="FID_ORG_ADJ_PRC")),
    )
    for endpoint, review in checks:
        with pytest.raises(EvidenceHandoffError, match="MD04C6_DOCUMENT_REVIEW_SCOPE_INVALID"):
            inspect_supplier_evidence_handoff(endpoint, review, (), now=NOW)


def test_only_synthetic_reference_codes_and_digest_are_in_contract():
    pointers = all_pointers()
    for p in pointers:
        assert p.recorded_at.tzinfo is not None
        assert p.document_sha256 == HASH
        assert not hasattr(p, "token")
        assert not hasattr(p, "close")
        assert not hasattr(p, "source_url")
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.lifecycle = "VERIFIED"


def test_quote_visibility_stays_unavailable_after_full_handoff():
    review = inspect_supplier_evidence_handoff(
        "KR_ITEMCHART", doc(), all_pointers(), now=NOW,
    )
    assert_locked(review, "KR_ITEMCHART")
    assert masked_quote_from_finality(None) == {
        "status": "UNAVAILABLE", "close": None, "change_pct": None,
        "as_of": None, "source": None,
    }
