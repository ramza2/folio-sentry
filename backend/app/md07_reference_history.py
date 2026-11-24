"""Owner-only stored reference history. No KIS I/O, writes, or finality claims."""
from datetime import date, datetime, timedelta, timezone
import os
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.market_data import InstrumentIdentity, MarketDataContractError
from app.portfolio_api import error
from app.portfolio_models import Instrument, TrackedInstrument
from app.price_models import PriceBar

router = APIRouter(prefix="/api/v1")


class StrictHistoryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HistoryCapability(StrictHistoryDTO):
    reference_history_enabled: bool


class ReferenceHistoryBar(StrictHistoryDTO):
    session_date: date
    open: str
    high: str
    low: str
    close: str
    volume: str
    fetched_at: datetime
    is_final: Literal[False] = False


class ReferenceHistory(StrictHistoryDTO):
    tracked_id: UUID
    currency: Literal["KRW", "USD"]
    source: Literal["KIS"] = "KIS"
    price_basis: Literal["RAW"] = "RAW"
    quality_status: Literal["PARTIAL"] = "PARTIAL"
    status: Literal["STORED_REFERENCE", "EMPTY"]
    days: Literal[30, 90]
    start_date: date
    end_date: date
    stored_rows: int
    latest_session_date: date | None
    latest_receipt: datetime | None
    bars: list[ReferenceHistoryBar]


def enabled():
    return os.getenv("FOLIOSENTRY_MD07_REFERENCE_HISTORY_DISPLAY_ENABLED") == "yes"


@router.get("/market-data/history-capabilities", response_model=HistoryCapability)
def history_capabilities():
    return {"reference_history_enabled": enabled()}


@router.get("/tracked/{tracked_id}/reference-history", response_model=ReferenceHistory)
def reference_history(tracked_id: UUID, days: int = 90):
    """Only stored RAW daily reference rows in the requested calendar window.

    Counts and latest receipt describe returned rows, not scheduler health,
    provider coverage, final settlement, or realtime market status.
    """
    if days not in (30, 90):
        return error(422, "MD07_HISTORY_RANGE_INVALID", "30일 또는 90일을 선택하세요.")
    if not enabled():
        return error(503, "MD07_HISTORY_DISABLED", "참고 일봉 차트가 아직 활성화되지 않았습니다.")
    try:
        with Session(get_engine()) as db:
            row = db.scalars(select(Instrument).join(
                TrackedInstrument, TrackedInstrument.instrument_id == Instrument.id
            ).where(TrackedInstrument.id == tracked_id,
                    Instrument.active.is_(True))).one_or_none()
            if row is None:
                return error(404, "TRACKED_NOT_FOUND", "등록 종목을 찾을 수 없습니다.")
            identity = InstrumentIdentity(row.market, row.exchange_mic,
                                          row.normalized_symbol, row.currency)
            now = datetime.now(timezone.utc)
            end = now.astimezone(identity.exchange_timezone).date() - timedelta(days=1)
            start = end - timedelta(days=days - 1)
            bars = db.scalars(select(PriceBar).where(
                PriceBar.instrument_id == row.id,
                PriceBar.timeframe == "1d", PriceBar.price_basis == "RAW",
                PriceBar.source == "KIS", PriceBar.quality_status == "PARTIAL",
                PriceBar.is_final.is_(False), PriceBar.source_observed_at.is_(None),
                PriceBar.session_date >= start, PriceBar.session_date <= end,
            ).order_by(PriceBar.session_date).limit(days)).all()
            values = []
            for bar in bars:
                fetched = bar.fetched_at
                # SQLite synthetic tests use naive UTC; production uses timestamptz.
                if fetched.tzinfo is None or fetched.utcoffset() is None:
                    if db.bind.dialect.name != "sqlite":
                        raise ValueError("MD07_INVALID_RECEIPT")
                    fetched = fetched.replace(tzinfo=timezone.utc)
                fetched = fetched.astimezone(timezone.utc)
                if fetched > now + timedelta(seconds=5) or bar.session_date >= fetched.astimezone(identity.exchange_timezone).date():
                    raise ValueError("MD07_INVALID_RECEIPT")
                values.append({
                    "session_date": bar.session_date,
                    **{key: format(getattr(bar, key), "f") for key in ("open", "high", "low", "close", "volume")},
                    "fetched_at": fetched, "is_final": False,
                })
            return {
                "tracked_id": tracked_id, "currency": identity.currency,
                "status": "STORED_REFERENCE" if values else "EMPTY",
                "days": days, "start_date": start, "end_date": end,
                "stored_rows": len(values),
                "latest_session_date": values[-1]["session_date"] if values else None,
                "latest_receipt": max(v["fetched_at"] for v in values) if values else None,
                "bars": values,
            }
    except MarketDataContractError:
        return error(422, "MD07_UNSUPPORTED_INSTRUMENT", "지원하지 않는 종목입니다.")
    except (SQLAlchemyError, ValueError):
        return error(503, "MD07_HISTORY_UNAVAILABLE", "저장된 참고 일봉을 확인할 수 없습니다.")
