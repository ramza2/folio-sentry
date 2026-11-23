"""MD-04B: fail-closed, price-free evidence-gap audit for KIS daily bars.

This is NOT a finality verifier. Official trading hours and a successfully
normalized bar are necessary checks, never proof of a provider-final close.
Until an independently verified finality/correction policy exists, every
daily candidate is UNFINALIZED and cannot be promoted, published or analyzed.

No KIS connection, secrets, DB, scheduler, API route or financial values.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.market_data import DailyBarBatch, InstrumentIdentity, PriceBasis
from app.md04_intake import inspect_unverified_intake


class FinalityPolicyError(ValueError):
    """Only fixed error codes; never echo candidate values or identifiers."""


# Stable, non-sensitive reason codes. Even a verified exchange session does
# not supply provider observation/finality/corporate-action evidence.
NO_DATA = "MD04B_NO_DAILY_BARS"
UNVERIFIED_REASONS = (
    "MD04B_PROVIDER_OBSERVATION_UNAVAILABLE",
    "MD04B_PROVIDER_FINAL_CLOSE_UNATTESTED",
    "MD04B_PRICE_BASIS_UNATTESTED",
    "MD04B_CORRECTION_WINDOW_UNATTESTED",
    "MD04B_CORPORATE_ACTION_REVISIONS_UNATTESTED",
    "MD04B_FINALITY_PROMOTION_NOT_IMPLEMENTED",
)


@dataclass(frozen=True, slots=True)
class FinalityGapReport:
    availability: Literal["UNAVAILABLE", "UNFINALIZED"]
    reviewed_rows: int
    blockers: tuple[str, ...]
    quality_status: Literal["PARTIAL"] | None
    # No API/DB/UI/signal may interpret this report as permission.
    is_final: Literal[False] = False
    source_observed_at: None = None
    promotion_allowed: Literal[False] = False
    publication_allowed: Literal[False] = False
    analysis_allowed: Literal[False] = False
    automatic_storage_allowed: Literal[False] = False


def review_daily_finality_gaps(
    expected_identity: InstrumentIdentity,
    batch: DailyBarBatch,
    *,
    requested_basis: PriceBasis,
    now: datetime,
) -> FinalityGapReport:
    """Audit an already obtained and MD-03-validated daily batch.

    Rejects requested RAW/ADJUSTED intent mismatches. A source's reported
    basis is NOT self-authenticating, and no existing KIS daily payload proves
    source observation time, final close or later price corrections.
    This pure diagnostic can never yield a final bar or authorization.
    """
    if requested_basis not in ("RAW", "ADJUSTED") or not isinstance(requested_basis, str):
        raise FinalityPolicyError("MD04B_PRICE_BASIS_INVALID")
    intake = inspect_unverified_intake(expected_identity, batch, now=now)
    if any(bar.price_basis != requested_basis for bar in batch.bars):
        raise FinalityPolicyError("MD04B_REQUESTED_BASIS_MISMATCH")
    if not intake.accepted_rows:
        return FinalityGapReport(
            availability="UNAVAILABLE", reviewed_rows=0,
            blockers=(NO_DATA,), quality_status=None,
        )
    return FinalityGapReport(
        availability="UNFINALIZED", reviewed_rows=intake.accepted_rows,
        blockers=UNVERIFIED_REASONS, quality_status="PARTIAL",
    )
