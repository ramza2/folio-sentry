"""MD-04C5 source inspection is only a metadata review, NEVER price finality."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from app.md04_finality import UNVERIFIED_REASONS
from app.md04c5_source_review import (
    ManualSourceInspection, OfflineSourceReviewError,
    PUBLIC_SOURCES, assess_offline_documentation,
)
from app.quote_visibility import masked_quote_from_finality

NOW = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)
DIGEST = hashlib.sha256(b"synthetic-public-reference-only").hexdigest()


def note(source_id, **overrides):
    base = {
        "source_id": source_id,
        "document_version": "synthetic-v1",
        "document_sha256": DIGEST,
        "inspected_at": NOW - timedelta(minutes=1),
    }
    base.update(overrides)
    return ManualSourceInspection(**base)


@pytest.mark.parametrize("endpoint,param,count", [
    ("KR_ITEMCHART", "FID_ORG_ADJ_PRC", 3),
    ("US_DAILYPRICE", "MODP", 2),
])
def test_all_sources_missing_is_never_an_attestation(endpoint, param, count):
    result = assess_offline_documentation(endpoint, (), now=NOW)
    assert result.parameter_name == param
    assert result.mapping_note == "NOT_REVIEWED"
    assert len(result.missing_source_ids) == count
    assert result.inspected_source_ids == ()
    assert result.blocker_codes == UNVERIFIED_REASONS
    assert result.is_final is False
    assert result.publication_allowed is False
    assert result.promotion_allowed is False
    assert result.analysis_allowed is False
    assert result.automatic_storage_allowed is False
    assert result.provider_observed_at is None


def test_kr_exact_endpoint_documents_are_not_price_finality():
    records = tuple(note(s.source_id) for s in PUBLIC_SOURCES
                    if s.endpoint == "KR_ITEMCHART")
    result = assess_offline_documentation("KR_ITEMCHART", records, now=NOW)
    assert result.mapping_note == "KR_DOCUMENTED_EXAMPLE_ONLY"
    assert result.missing_source_ids == ()
    assert result.provider_finality_attested is False
    assert result.price_basis_attested is False
    assert result.correction_policy_attested is False
    assert result.corporate_action_attested is False
    assert result.publication_allowed is False
    assert "105" not in repr(result) and "70000" not in repr(result)
    assert not hasattr(result, "close")
    assert not hasattr(result, "source_observed_at")


def test_cross_endpoint_parameter_name_is_not_transferred():
    # The other KR daily endpoint config has a conflicting mapping.
    # It cannot change the target itemchart policy or unlock a price.
    contextual = note("KR_OTHER_DAILY_PRICE_CONFIG")
    result = assess_offline_documentation(
        "KR_ITEMCHART", (contextual,), now=NOW
    )
    assert result.mapping_note == "NOT_REVIEWED"
    assert result.publication_allowed is False
    assert "KR_ITEMCHART_EXAMPLE" in result.missing_source_ids


@pytest.mark.parametrize("sources,mapping", [
    (("US_DAILYPRICE_EXAMPLE",), "US_PARAMETER_ONLY"),
    (("US_DAILYPRICE_EXAMPLE", "US_BACKTESTER_USAGE"),
     "US_EXAMPLE_WITHOUT_PROVIDER_ATTESTATION"),
])
def test_us_modp_has_no_supplier_verified_value_mapping(sources, mapping):
    result = assess_offline_documentation(
        "US_DAILYPRICE", tuple(note(s) for s in sources), now=NOW
    )
    assert result.mapping_note == mapping
    assert result.price_basis_attested is False
    assert result.provider_finality_attested is False
    assert result.provider_observed_at is None
    assert result.blocker_codes == UNVERIFIED_REASONS


@pytest.mark.parametrize("endpoint,sources", [
    ("KR_ITEMCHART", ("US_DAILYPRICE_EXAMPLE",)),
    ("US_DAILYPRICE", ("KR_ITEMCHART_EXAMPLE",)),
    ("US_DAILYPRICE", ("US_DAILYPRICE_EXAMPLE", "US_DAILYPRICE_EXAMPLE")),
])
def test_foreign_endpoint_and_duplicate_references_rejected(endpoint, sources):
    with pytest.raises(OfflineSourceReviewError, match="MD04C5_SOURCE_SCOPE_OR_DUPLICATE"):
        assess_offline_documentation(endpoint, tuple(note(s) for s in sources), now=NOW)


@pytest.mark.parametrize("endpoint", ["", "KR_DAILY_PRICE", "US_INQUIRE", None, True])
def test_noncontract_endpoint_rejected(endpoint):
    with pytest.raises(OfflineSourceReviewError, match="MD04C5_ENDPOINT_INVALID"):
        assess_offline_documentation(endpoint, (), now=NOW)


@pytest.mark.parametrize("bad_inspections", [
    [note("KR_ITEMCHART_EXAMPLE")],
    (None,),
    ("KR_ITEMCHART_EXAMPLE",),
    tuple(note("KR_ITEMCHART_EXAMPLE") for _ in range(6)),
])
def test_malformed_notes_rejected(bad_inspections):
    with pytest.raises(OfflineSourceReviewError):
        assess_offline_documentation("KR_ITEMCHART", bad_inspections, now=NOW)


@pytest.mark.parametrize("changed", [
    {"document_version": ""},
    {"document_version": "note with space"},
    {"document_version": "v1/secret"},
    {"document_version": "x" * 65},
    {"document_sha256": "0" * 63},
    {"document_sha256": "G" * 64},
    {"document_sha256": None},
    {"inspected_at": NOW + timedelta(seconds=1)},
    {"inspected_at": datetime(2026, 11, 23, 8, 0)},
    {"inspected_at": None},
])
def test_untrusted_source_version_digest_and_clock_rejected(changed):
    with pytest.raises(OfflineSourceReviewError, match="MD04C5_SOURCE_METADATA_INVALID"):
        assess_offline_documentation(
            "KR_ITEMCHART",
            (note("KR_ITEMCHART_EXAMPLE", **changed),), now=NOW,
        )


@pytest.mark.parametrize("now", [None, "2026-11-23", datetime(2026, 11, 23, 9)])
def test_review_clock_must_be_aware(now):
    with pytest.raises(OfflineSourceReviewError, match="MD04C5_CLOCK_INVALID"):
        assess_offline_documentation("KR_ITEMCHART", (), now=now)


def test_source_catalog_is_bounded_and_data_only():
    assert {s.endpoint for s in PUBLIC_SOURCES} == {"KR_ITEMCHART", "US_DAILYPRICE"}
    assert len({s.source_id for s in PUBLIC_SOURCES}) == len(PUBLIC_SOURCES)
    for source in PUBLIC_SOURCES:
        assert source.url.startswith("https://github.com/koreainvestment/open-trading-api/")
        assert "?" not in source.url and "#" not in source.url
        assert "74b0a082fa67a0be5bf53f561719c853890ed2df" in source.url
        assert len(source.pinned_blob_sha) == 40
        assert all(char in "0123456789abcdef" for char in source.pinned_blob_sha)
        assert source.documented_fact_code and source.evidence_scope in (
            "TARGET_ENDPOINT", "CROSS_ENDPOINT_CONTEXT",
        )


def test_source_inspection_cannot_forge_a_publication_permission():
    initial = note("KR_ITEMCHART_EXAMPLE")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        initial.document_version = "verified"
    result = assess_offline_documentation("KR_ITEMCHART", (initial,), now=NOW)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.publication_allowed = True
    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.provider_finality_attested = True
    assert all(getattr(result, k) is False for k in (
        "provider_finality_attested", "price_basis_attested",
        "correction_policy_attested", "corporate_action_attested",
        "promotion_allowed", "publication_allowed", "analysis_allowed",
        "automatic_storage_allowed", "is_final",
    ))


def test_existing_status_api_stays_hidden_even_with_documentation_review():
    result = assess_offline_documentation(
        "KR_ITEMCHART", tuple(note(s.source_id) for s in PUBLIC_SOURCES
                              if s.endpoint == "KR_ITEMCHART"), now=NOW
    )
    assert result.publication_allowed is False
    # MD-04C5 does not feed a KIS bar into the quote masking contract.
    assert masked_quote_from_finality(None) == {
        "status": "UNAVAILABLE", "close": None, "change_pct": None,
        "as_of": None, "source": None,
    }
