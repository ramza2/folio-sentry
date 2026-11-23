"""MD-04A offline-only intake decision; never requests or publishes prices.

A provenance-matched DailyBarBatch has already been obtained by an explicit
caller. This module validates it with MD-03's fail-closed calendar/quality
gate and returns NON-PRICE diagnostic metadata. No network, secrets, database,
background scheduler, API route or price display integration is performed.
"""
from dataclasses import dataclass
from typing import Literal

from app.market_data import DailyBarBatch, InstrumentIdentity
from app.price_quality import validate_batch


class MD04IntakeError(ValueError):
    """Static, non-sensitive error code."""


@dataclass(frozen=True, slots=True)
class IntakeReadiness:
    accepted_rows: int
    availability: Literal["UNAVAILABLE", "UNFINALIZED"]
    quality_status: Literal["PARTIAL"] | None
    is_final: Literal[False] = False
    source_observed_at: None = None
    publication_allowed: Literal[False] = False
    # MD-03 repository requires a separate, default-denied write opt-in.
    automatic_storage_allowed: Literal[False] = False


def inspect_unverified_intake(
    expected_identity: InstrumentIdentity,
    batch: DailyBarBatch,
    *,
    now,
) -> IntakeReadiness:
    """Validate a KIS daily batch for a *specific* registered instrument.

    Identity matching prevents assigning data for a different exchange,
    symbol, currency or market to the requested instrument. This function is
    diagnostic only: it never returns OHLCV or an instruction to publish it.
    """
    if not isinstance(expected_identity, InstrumentIdentity) \
            or not isinstance(batch, DailyBarBatch):
        raise MD04IntakeError("MD04_INPUT_INVALID")
    if batch.instrument != expected_identity:
        raise MD04IntakeError("MD04_INSTRUMENT_IDENTITY_MISMATCH")
    checked = validate_batch(batch, now=now)
    return IntakeReadiness(
        accepted_rows=len(checked),
        availability="UNFINALIZED" if checked else "UNAVAILABLE",
        quality_status="PARTIAL" if checked else None,
    )
