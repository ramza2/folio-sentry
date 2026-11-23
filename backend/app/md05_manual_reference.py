"""MD-05A manual KIS daily reference close — OFF BY DEFAULT.

Owner-initiated POST only. A daily historical close is neither a realtime
quote nor a verified FINAL settlement close. No DB writes, orders, holdings
calculation, scheduler, retries, DEMO fallback or background worker.

Do NOT enable on MiniPC without separate approval for KIS API/token usage,
market-data display, credentials, shared state and deployment.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import os
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.kis_readonly import (
    KisCredentials, KisReadOnlyDailyProvider, KisReadOnlyError,
)
from app.kis_shared_state import KisSharedState
from app.market_data import (
    DailyBarBatch, InstrumentIdentity, MarketDataContractError,
)
from app.portfolio_api import error
from app.portfolio_models import Instrument, TrackedInstrument

router = APIRouter(prefix="/api/v1")


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManualQuoteCapability(StrictDTO):
    manual_daily_reference_enabled: bool


class DailyReferenceDTO(StrictDTO):
    status: Literal["REFERENCE", "STALE", "UNAVAILABLE"]
    close: str | None
    session_date: date | None
    fetched_at: datetime | None
    source: Literal["KIS"] | None
    price_basis: Literal["RAW"] | None
    currency: Literal["KRW", "USD"]
    is_final: Literal[False] = False


class TrackedDailyReferenceDTO(StrictDTO):
    tracked_id: UUID
    reference: DailyReferenceDTO


def _flag(name: str) -> bool:
    return os.getenv(name) == "yes"


def _enabled() -> bool:
    # Two independent operator-set server switches; neither is configured
    # in the repository or any production compose by this PR.
    return (
        _flag("FOLIOSENTRY_MD05_MANUAL_READ_ENABLED")
        and _flag("FOLIOSENTRY_MD05_REFERENCE_DISPLAY_ENABLED")
    )


def _provider() -> KisReadOnlyDailyProvider:
    """Only called *after* BOTH feature gates and owner authentication."""
    creds = KisCredentials.from_private_files(
        os.getenv("FOLIOSENTRY_KIS_APPKEY_FILE", ""),
        os.getenv("FOLIOSENTRY_KIS_APPSECRET_FILE", ""),
    )
    state_dir = os.getenv("FOLIOSENTRY_KIS_SHARED_STATE_DIR", "")
    if not state_dir.startswith("/"):
        raise KisReadOnlyError("KIS_SHARED_DIR_MUST_BE_ABSOLUTE")
    return KisReadOnlyDailyProvider(
        creds, live_enabled=True, shared_state=KisSharedState(state_dir),
        allow_shared_token_issue=_flag("FOLIOSENTRY_MD05_NEW_TOKEN_ISSUE_ALLOWED"),
    )


def _reference(
    identity: InstrumentIdentity, batch: DailyBarBatch,
    *, checked_at: datetime, max_session_day: date,
) -> dict:
    """All-or-nothing validation before exposing a non-final reference.

    Latest bar is <= yesterday in the market timezone, not today's partial
    intraday bar. Do not substitute fetched_at for provider_observed_at.
    """
    if (
        not isinstance(batch, DailyBarBatch)
        or batch.instrument != identity
        or batch.provider != "KIS"
        or not isinstance(checked_at, datetime)
        or checked_at.tzinfo is None
        or checked_at.utcoffset() is None
    ):
        raise MarketDataContractError("MD05_REFERENCE_BATCH_INVALID")
    if not batch.bars:
        return {
            "status": "UNAVAILABLE", "close": None,
            "session_date": None, "fetched_at": None,
            "source": None, "price_basis": None,
            "currency": identity.currency, "is_final": False,
        }
    dates = [item.session_date for item in batch.bars]
    if len(dates) != len(set(dates)):
        raise MarketDataContractError("MD05_DUPLICATE_REFERENCE_DAY")
    last = max(batch.bars, key=lambda item: item.session_date)
    if (
        last.session_date > max_session_day
        or last.session_date < max_session_day - timedelta(days=14)
        or last.source != "KIS"
        or last.price_basis != "RAW"
        or last.is_final is not False
        or last.source_observed_at is not None
        or type(last.close) is not Decimal
        or not last.close.is_finite()
        or last.close <= 0
        or not isinstance(last.fetched_at, datetime)
        or last.fetched_at.tzinfo is None
        or last.fetched_at.utcoffset() is None
        or last.fetched_at.astimezone(timezone.utc) > checked_at.astimezone(timezone.utc) + timedelta(minutes=1)
    ):
        raise MarketDataContractError("MD05_REFERENCE_NOT_TRUSTED")
    is_stale = (max_session_day - last.session_date).days > 5
    return {
        "status": "STALE" if is_stale else "REFERENCE",
        "close": None if is_stale else format(last.close, "f"),
        "session_date": last.session_date,
        "fetched_at": last.fetched_at.astimezone(timezone.utc),
        "source": "KIS",
        "price_basis": "RAW",
        "currency": identity.currency,
        "is_final": False,
    }


@router.get("/market-data/capabilities", response_model=ManualQuoteCapability)
def market_data_capabilities():
    """Auth-protected, no KIS/token/DB call and no credentials in response."""
    return {"manual_daily_reference_enabled": _enabled()}


@router.post("/tracked/{tracked_id}/daily-reference", response_model=TrackedDailyReferenceDTO)
def get_manual_daily_reference(tracked_id: UUID):
    """Authenticated + CSRF-protected POST: one KIS read attempt on demand.

    This is a provider-read *operation*, never a passive GET. A successful
    response contains only a non-final historical reference; valuation and
    signals remain unavailable. Default config returns 503 before secrets/DB.
    """
    if not _enabled():
        return error(503, "MD05_MANUAL_REFERENCE_DISABLED",
                     "시세 수동 조회는 아직 활성화되지 않았습니다.")
    try:
        with Session(get_engine()) as db:
            row = db.execute(
                select(Instrument)
                .join(TrackedInstrument, TrackedInstrument.instrument_id == Instrument.id)
                .where(TrackedInstrument.id == tracked_id, Instrument.active.is_(True))
            ).scalar_one_or_none()
            if row is None:
                return error(404, "TRACKED_NOT_FOUND", "등록 종목을 찾을 수 없습니다.")
            identity = InstrumentIdentity(
                row.market, row.exchange_mic, row.normalized_symbol, row.currency,
            )
    except SQLAlchemyError:
        return error(503, "PORTFOLIO_DATABASE_UNAVAILABLE",
                     "등록 종목 저장소에 접근할 수 없습니다.")
    except MarketDataContractError:
        return error(422, "MD05_UNSUPPORTED_INSTRUMENT",
                     "시세 조회를 지원하지 않는 종목 정보입니다.")

    checked_at = datetime.now(timezone.utc)
    # Deliberately exclude the current market-local session date. Latest
    # available prior session may be a weekend/holiday; empty is normal.
    last_session = checked_at.astimezone(identity.exchange_timezone).date() - timedelta(days=1)
    try:
        batch = _provider().fetch_daily(
            identity, last_session - timedelta(days=14), last_session, "RAW",
        )
        snapshot = _reference(
            identity, batch, checked_at=datetime.now(timezone.utc),
            max_session_day=last_session,
        )
    except (KisReadOnlyError, MarketDataContractError):
        return error(503, "MD05_PROVIDER_UNAVAILABLE",
                     "KIS 일봉 참고 시세를 조회할 수 없습니다.")
    except Exception:
        # Unexpected provider errors must never disclose token, URL, raw
        # quote response, session/account details, or library exceptions.
        return error(503, "MD05_PROVIDER_UNAVAILABLE",
                     "KIS 일봉 참고 시세를 조회할 수 없습니다.")
    return {"tracked_id": tracked_id, "reference": snapshot}
