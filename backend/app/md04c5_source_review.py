"""MD-04C5 offline first-party documentation gap assessment.

Input is ONLY manually supplied source-reference metadata (no body/URL fetch,
KIS token, market values, database, network, scheduler, UI, or price promotion).
A document URL/hash is not proof of provider-close finality or actual price
basis. Every result is blocked from publication and analysis.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Literal

from app.md04_finality import UNVERIFIED_REASONS

Endpoint = Literal["KR_ITEMCHART", "US_DAILYPRICE"]
SourceId = Literal[
    "KR_ITEMCHART_EXAMPLE", "KR_ITEMCHART_CONFIG",
    "KR_OTHER_DAILY_PRICE_CONFIG", "US_DAILYPRICE_EXAMPLE",
    "US_BACKTESTER_USAGE",
]
PolicyMapping = Literal[
    "NOT_REVIEWED", "KR_DOCUMENTED_EXAMPLE_ONLY",
    "US_PARAMETER_ONLY", "US_EXAMPLE_WITHOUT_PROVIDER_ATTESTATION",
]

_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class OfflineSourceReviewError(ValueError):
    """Fixed error codes only, never echo source inputs or financial values."""


@dataclass(frozen=True, slots=True)
class PublicSource:
    source_id: SourceId
    endpoint: Endpoint
    url: str
    evidence_scope: Literal["TARGET_ENDPOINT", "CROSS_ENDPOINT_CONTEXT"]
    # These describe publicly documented code examples, NOT verified prices.
    documented_fact_code: str


PUBLIC_SOURCES: tuple[PublicSource, ...] = (
    PublicSource(
        "KR_ITEMCHART_EXAMPLE", "KR_ITEMCHART",
        "https://github.com/koreainvestment/open-trading-api/blob/main/"
        "examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py",
        "TARGET_ENDPOINT", "KR_FID_ORG_ADJ_PRC_0_ADJUSTED_1_RAW_EXAMPLE",
    ),
    PublicSource(
        "KR_ITEMCHART_CONFIG", "KR_ITEMCHART",
        "https://github.com/koreainvestment/open-trading-api/blob/main/"
        "MCP/Kis%20Trading%20MCP/configs/domestic_stock.json",
        "TARGET_ENDPOINT", "KR_ITEMCHART_CONFIG_0_ADJUSTED_1_RAW",
    ),
    PublicSource(
        "KR_OTHER_DAILY_PRICE_CONFIG", "KR_ITEMCHART",
        "https://github.com/koreainvestment/open-trading-api/blob/main/"
        "MCP/Kis%20Trading%20MCP/configs/domestic_stock.json",
        "CROSS_ENDPOINT_CONTEXT", "KR_OTHER_DAILY_PRICE_OPPOSITE_EXAMPLE_NOT_TRANSFERABLE",
    ),
    PublicSource(
        "US_DAILYPRICE_EXAMPLE", "US_DAILYPRICE",
        "https://github.com/koreainvestment/open-trading-api/blob/main/"
        "examples_llm/overseas_stock/dailyprice/dailyprice.py",
        "TARGET_ENDPOINT", "US_MODP_PARAMETER_DESCRIBED_VALUE_MAPPING_UNATTESTED",
    ),
    PublicSource(
        "US_BACKTESTER_USAGE", "US_DAILYPRICE",
        "https://github.com/koreainvestment/open-trading-api/blob/main/"
        "backtester/kis_backtest/providers/kis/data.py",
        "TARGET_ENDPOINT", "US_MODP_1_ADJUSTED_BACKTESTER_COMMENT_ONLY",
    ),
)


@dataclass(frozen=True, slots=True)
class ManualSourceInspection:
    """Locally noted source version/digest; no contents or URL/user claims.

    A SHA256 and version are provenance *bookkeeping*. They do not mean
    someone checked authenticity, provider finality, or corporate actions.
    """
    source_id: SourceId
    document_version: str
    document_sha256: str
    inspected_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentationGapReview:
    endpoint: Endpoint
    parameter_name: Literal["FID_ORG_ADJ_PRC", "MODP"]
    mapping_note: PolicyMapping
    inspected_source_ids: tuple[SourceId, ...]
    missing_source_ids: tuple[SourceId, ...]
    blocker_codes: tuple[str, ...]
    review_status: Literal["EVIDENCE_INSUFFICIENT"] = "EVIDENCE_INSUFFICIENT"
    provider_observed_at: None = None
    provider_finality_attested: Literal[False] = False
    price_basis_attested: Literal[False] = False
    correction_policy_attested: Literal[False] = False
    corporate_action_attested: Literal[False] = False
    is_final: Literal[False] = False
    promotion_allowed: Literal[False] = False
    publication_allowed: Literal[False] = False
    analysis_allowed: Literal[False] = False
    automatic_storage_allowed: Literal[False] = False


def assess_offline_documentation(
    endpoint: Endpoint,
    inspections: tuple[ManualSourceInspection, ...],
    *,
    now: datetime,
) -> DocumentationGapReview:
    """Reject unreliable metadata and enumerate gaps; never lift MD04B blocks.

    Only approved, endpoint-bound *reference identifiers* are accepted.
    No file, web, token, KIS, price_bar or quality-evidence DB is accessed.
    """
    if type(endpoint) is not str or endpoint not in ("KR_ITEMCHART", "US_DAILYPRICE"):
        raise OfflineSourceReviewError("MD04C5_ENDPOINT_INVALID")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise OfflineSourceReviewError("MD04C5_CLOCK_INVALID")
    if type(inspections) is not tuple or len(inspections) > len(PUBLIC_SOURCES):
        raise OfflineSourceReviewError("MD04C5_INSPECTIONS_INVALID")
    allowed = tuple(s for s in PUBLIC_SOURCES if s.endpoint == endpoint)
    by_id = {s.source_id: s for s in allowed}
    seen: set[str] = set()
    for item in inspections:
        if not isinstance(item, ManualSourceInspection) or type(item.source_id) is not str:
            raise OfflineSourceReviewError("MD04C5_INSPECTION_INVALID")
        if item.source_id not in by_id or item.source_id in seen:
            raise OfflineSourceReviewError("MD04C5_SOURCE_SCOPE_OR_DUPLICATE")
        if (
            type(item.document_version) is not str
            or _VERSION_RE.fullmatch(item.document_version) is None
            or type(item.document_sha256) is not str
            or _DIGEST_RE.fullmatch(item.document_sha256) is None
            or not isinstance(item.inspected_at, datetime)
            or item.inspected_at.tzinfo is None
            or item.inspected_at.utcoffset() is None
            or item.inspected_at.astimezone(timezone.utc) > now.astimezone(timezone.utc)
        ):
            raise OfflineSourceReviewError("MD04C5_SOURCE_METADATA_INVALID")
        seen.add(item.source_id)
    inspected = tuple(s.source_id for s in allowed if s.source_id in seen)
    missing = tuple(s.source_id for s in allowed if s.source_id not in seen)

    if endpoint == "KR_ITEMCHART":
        mapping: PolicyMapping = (
            "KR_DOCUMENTED_EXAMPLE_ONLY"
            if "KR_ITEMCHART_EXAMPLE" in seen and "KR_ITEMCHART_CONFIG" in seen
            else "NOT_REVIEWED"
        )
        parameter = "FID_ORG_ADJ_PRC"
    else:
        mapping = (
            "US_EXAMPLE_WITHOUT_PROVIDER_ATTESTATION"
            if "US_DAILYPRICE_EXAMPLE" in seen and "US_BACKTESTER_USAGE" in seen
            else "US_PARAMETER_ONLY" if "US_DAILYPRICE_EXAMPLE" in seen
            else "NOT_REVIEWED"
        )
        parameter = "MODP"

    return DocumentationGapReview(
        endpoint=endpoint,
        parameter_name=parameter,
        mapping_note=mapping,
        inspected_source_ids=inspected,
        missing_source_ids=missing,
        blocker_codes=UNVERIFIED_REASONS,
    )
