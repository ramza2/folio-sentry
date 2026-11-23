"""MD-04C1: non-publishing quote envelope, offline only.

Pure contract for future authenticated API integration. There is NO API route,
DB query, KIS call, scheduler, price computation, or finality promotion here.
All economic values and provenance remain null until a separately approved
verified-price contract exists.
"""
from app.md04_finality import FinalityGapReport


class HiddenQuoteContractError(ValueError):
    """Fixed error code, never echo instruments or prices."""


def masked_quote_from_finality(report: FinalityGapReport | None) -> dict:
    """Return only visibility metadata for an already-audited daily batch.

    None = no provider information. The current MD-04B audit can only produce
    UNAVAILABLE or UNFINALIZED; even a successful audit is NEVER publishable.
    STALE/ERROR are reserved frontend-only hidden display states for future
    explicit read-only response contracts, not inferred from absent evidence.
    """
    if report is None:
        status = "UNAVAILABLE"
    elif not isinstance(report, FinalityGapReport):
        raise HiddenQuoteContractError("QUOTE_FINALITY_REPORT_INVALID")
    elif (
        report.is_final is not False
        or report.source_observed_at is not None
        or report.promotion_allowed is not False
        or report.publication_allowed is not False
        or report.analysis_allowed is not False
        or report.automatic_storage_allowed is not False
    ):
        raise HiddenQuoteContractError("QUOTE_PRICE_PUBLICATION_NOT_ALLOWED")
    elif (
        report.availability == "UNAVAILABLE"
        and report.reviewed_rows == 0
        and report.quality_status is None
        and bool(report.blockers)
    ):
        status = "UNAVAILABLE"
    elif (
        report.availability == "UNFINALIZED"
        and type(report.reviewed_rows) is int and report.reviewed_rows > 0
        and report.quality_status == "PARTIAL"
        and bool(report.blockers)
    ):
        status = "UNFINALIZED"
    else:
        raise HiddenQuoteContractError("QUOTE_FINALITY_STATE_INVALID")
    return {
        "status": status,
        "close": None,
        "change_pct": None,
        "as_of": None,
        "source": None,
    }
