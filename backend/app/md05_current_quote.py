"""MD-05B guarded manual current/last-price API (not realtime guarantee).

Two new OFF-by-default feature switches. No actual KIS call/credentials,
price display, or MiniPC operation until separate owner deployment approval.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID
import os

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.kis_current import CurrentQuoteCandidate, KisReadOnlyCurrentProvider
from app.kis_readonly import KisCredentials, KisReadOnlyError
from app.kis_shared_state import KisSharedState
from app.market_data import InstrumentIdentity, MarketDataContractError
from app.portfolio_api import error
from app.portfolio_models import Instrument, TrackedInstrument

router = APIRouter(prefix="/api/v1")


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CurrentCapabilityDTO(StrictDTO):
    manual_current_quote_enabled: bool


class ValuationCapabilityDTO(StrictDTO):
    reference_valuation_enabled: bool


class CurrentQuoteDTO(StrictDTO):
    status: Literal["RECEIVED", "UNAVAILABLE"]
    price: str | None
    fetched_at: datetime | None
    currency: Literal["KRW", "USD"]
    source: Literal["KIS"] | None
    provider_time_status: Literal["UNKNOWN"] = "UNKNOWN"
    delay_status: Literal["UNKNOWN"] = "UNKNOWN"
    market_session: Literal["UNKNOWN"] = "UNKNOWN"
    realtime_verified: Literal[False] = False
    is_final: Literal[False] = False


class TrackedCurrentQuoteDTO(StrictDTO):
    tracked_id: UUID
    current_quote: CurrentQuoteDTO


def _flag(name: str) -> bool:
    return os.getenv(name) == "yes"


def _enabled() -> bool:
    return (
        _flag("FOLIOSENTRY_MD05_CURRENT_READ_ENABLED")
        and _flag("FOLIOSENTRY_MD05_CURRENT_DISPLAY_ENABLED")
    )


def _provider() -> KisReadOnlyCurrentProvider:
    creds = KisCredentials.from_private_files(
        os.getenv("FOLIOSENTRY_KIS_APPKEY_FILE", ""),
        os.getenv("FOLIOSENTRY_KIS_APPSECRET_FILE", ""),
    )
    state_dir = os.getenv("FOLIOSENTRY_KIS_SHARED_STATE_DIR", "")
    if not state_dir.startswith("/"):
        raise KisReadOnlyError("KIS_SHARED_DIR_MUST_BE_ABSOLUTE")
    return KisReadOnlyCurrentProvider(
        creds, KisSharedState(state_dir),
        live_enabled=True,
        # Deliberately reuses the explicit MD05 token issue authorization.
        allow_new_token=_flag("FOLIOSENTRY_MD05_NEW_TOKEN_ISSUE_ALLOWED"),
    )


def _snapshot(
    identity: InstrumentIdentity, candidate: CurrentQuoteCandidate,
    *, checked_at: datetime,
) -> dict:
    if not isinstance(candidate, CurrentQuoteCandidate) or (
        candidate.instrument != identity
        or candidate.source != "KIS"
        or candidate.realtime_verified is not False
        or candidate.provider_observed_at is not None
        or candidate.is_final is not False
    ):
        raise MarketDataContractError("MD05B_QUOTE_UNVERIFIED_REQUIRED")
    if candidate.price is None:
        if candidate.fetched_at is not None:
            raise MarketDataContractError("MD05B_EMPTY_QUOTE_HAS_TIMESTAMP")
        return dict(
            status="UNAVAILABLE", price=None, fetched_at=None,
            currency=identity.currency, source=None,
        )
    stamp = candidate.fetched_at
    if (
        type(candidate.price) is not Decimal
        or not candidate.price.is_finite()
        or candidate.price <= 0
        or not isinstance(stamp, datetime)
        or stamp.tzinfo is None
        or stamp.utcoffset() is None
        or not isinstance(checked_at, datetime)
        or checked_at.tzinfo is None
        or checked_at.utcoffset() is None
    ):
        raise MarketDataContractError("MD05B_QUOTE_PAYLOAD_INVALID")
    age = checked_at.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)
    if age < -timedelta(seconds=5) or age > timedelta(minutes=2):
        raise MarketDataContractError("MD05B_RECEIPT_TIMESTAMP_OUT_OF_RANGE")
    return dict(
        status="RECEIVED", price=format(candidate.price, "f"),
        fetched_at=stamp.astimezone(timezone.utc),
        currency=identity.currency, source="KIS",
    )


@router.get("/market-data/current-capabilities", response_model=CurrentCapabilityDTO)
def current_quote_capability():
    """Authenticated metadata GET never contacts KIS, database or secrets."""
    return {"manual_current_quote_enabled": _enabled()}


@router.get("/market-data/valuation-capabilities", response_model=ValuationCapabilityDTO)
def valuation_capability():
    """No price, secrets, database or KIS access. Independent display opt-in."""
    return {"reference_valuation_enabled": (
        _enabled() and _flag("FOLIOSENTRY_MD05_VALUATION_DISPLAY_ENABLED")
    )}


@router.post("/tracked/{tracked_id}/current-quote", response_model=TrackedCurrentQuoteDTO)
def manual_current_quote(tracked_id: UUID):
    """Owner POST+Origin+CSRF; one provider read, no polling or PnL.

    The provider's price timestamp/delay status is UNKNOWN, even when
    fetched_at is recent. A received price must never be called realtime.
    """
    if not _enabled():
        return error(
            503, "MD05B_MANUAL_CURRENT_DISABLED",
            "현재가 수동 조회 기능은 아직 활성화되지 않았습니다.",
        )
    try:
        with Session(get_engine()) as db:
            instrument = db.execute(
                select(Instrument)
                .join(TrackedInstrument, TrackedInstrument.instrument_id == Instrument.id)
                .where(TrackedInstrument.id == tracked_id, Instrument.active.is_(True))
            ).scalar_one_or_none()
            if instrument is None:
                return error(404, "TRACKED_NOT_FOUND", "등록 종목을 찾을 수 없습니다.")
            identity = InstrumentIdentity(
                instrument.market, instrument.exchange_mic,
                instrument.normalized_symbol, instrument.currency,
            )
    except SQLAlchemyError:
        return error(
            503, "PORTFOLIO_DATABASE_UNAVAILABLE",
            "등록 종목을 조회할 수 없습니다.",
        )
    except MarketDataContractError:
        return error(
            422, "MD05B_UNSUPPORTED_INSTRUMENT",
            "현재가 조회를 지원하지 않는 종목입니다.",
        )
    try:
        candidate = _provider().fetch_current(identity)
        result = _snapshot(
            identity, candidate, checked_at=datetime.now(timezone.utc),
        )
    except (KisReadOnlyError, MarketDataContractError):
        return error(
            503, "MD05B_PROVIDER_UNAVAILABLE",
            "KIS 현재가를 조회할 수 없습니다.",
        )
    except Exception:
        # No raw exception or provider response is returned/logged.
        return error(
            503, "MD05B_PROVIDER_UNAVAILABLE",
            "KIS 현재가를 조회할 수 없습니다.",
        )
    return {"tracked_id": tracked_id, "current_quote": result}
