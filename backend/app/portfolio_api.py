"""Authenticated Phase 1 manual stock registry and tracked portfolio API.

User-entered instrument identities are unverified until a market provider is
configured. Never use DEMO quotes or synthesize real prices here.
"""
from decimal import Decimal
import re
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.portfolio_models import Instrument, TrackedInstrument
from app.quote_visibility import masked_quote_from_finality

router = APIRouter(prefix="/api/v1")
Market = Literal["KR", "US"]
Kind = Literal["HOLDING", "WATCH"]
Exchange = Literal["XKRX", "XKOS", "XNAS", "XNYS", "XASE"]
AssetType = Literal["STOCK", "ETF"]
SYMBOL = re.compile(r"^[A-Z0-9.-]{1,32}$")
DECIMAL_INPUT = re.compile(r"^(0|[1-9][0-9]{0,15})(\.[0-9]{1,8})?$")
MARKET_META = {
    "KR": {"exchanges": {"XKRX", "XKOS"}, "currency": "KRW", "timezone": "Asia/Seoul"},
    "US": {"exchanges": {"XNAS", "XNYS", "XASE"}, "currency": "USD", "timezone": "America/New_York"},
}


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": None}},
        headers={"Cache-Control": "no-store"},
    )


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HiddenQuoteStatusDTO(StrictInput):
    """MD-04C2: never expose OHLCV, timestamps, source or verification claims."""
    status: Literal["UNAVAILABLE"]
    close: None
    change_pct: None
    as_of: None
    source: None


class TrackedQuoteStatusDTO(StrictInput):
    tracked_id: UUID
    quote: HiddenQuoteStatusDTO


class InstrumentCreate(StrictInput):
    market: Market
    exchange_mic: Exchange
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=256)
    asset_type: AssetType

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value):
        if not isinstance(value, str):
            raise ValueError("종목 코드는 문자열이어야 합니다.")
        normalized = value.strip().upper()
        if not SYMBOL.fullmatch(normalized):
            raise ValueError("종목 코드에는 영문자, 숫자, 점과 하이픈만 사용할 수 있습니다.")
        return normalized

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        if not isinstance(value, str):
            raise ValueError("종목명은 문자열이어야 합니다.")
        value = value.strip()
        if not value:
            raise ValueError("종목명을 입력하세요.")
        return value

    @model_validator(mode="after")
    def check_market(self):
        if self.exchange_mic not in MARKET_META[self.market]["exchanges"]:
            raise ValueError("시장과 거래소 코드가 일치하지 않습니다.")
        if self.market == "KR" and not re.fullmatch(r"[0-9]{6}", self.symbol):
            raise ValueError("현재 한국 시장 수동 종목 등록은 6자리 코드만 지원합니다.")
        return self


def strict_decimal(value):
    if value is None:
        return None
    # JSON floating point is deliberately rejected to preserve financial
    # precision; callers must send decimal strings.
    if not isinstance(value, str) or DECIMAL_INPUT.fullmatch(value) is None:
        raise ValueError("수량과 평균단가는 8자리 소수까지의 10진 문자열이어야 합니다.")
    return Decimal(value)


class TrackedCreate(StrictInput):
    instrument_id: UUID
    kind: Kind
    quantity: Decimal | None = None
    average_cost: Decimal | None = None
    alerts_enabled: StrictBool = True
    memo: str | None = Field(default=None, max_length=1000)

    _quantity_validator = field_validator("quantity", "average_cost", mode="before")(strict_decimal)


class TrackedPatch(StrictInput):
    kind: Kind | None = None
    quantity: Decimal | None = None
    average_cost: Decimal | None = None
    alerts_enabled: StrictBool | None = None
    memo: str | None = Field(default=None, max_length=1000)

    _quantity_validator = field_validator("quantity", "average_cost", mode="before")(strict_decimal)


def position_valid(kind: Kind, qty: Decimal | None, cost: Decimal | None) -> bool:
    return not (
        (kind == "WATCH" and (qty is not None or cost is not None))
        or (qty is not None and qty <= 0)
        or (cost is not None and (cost < 0 or qty is None))
    )


def instrument_json(value: Instrument) -> dict:
    return {
        "id": str(value.id), "market": value.market,
        "exchange_mic": value.exchange_mic, "symbol": value.symbol,
        "name": value.name, "currency": value.currency,
        "asset_type": value.asset_type, "source": "MANUAL_UNVERIFIED",
    }


def tracked_json(row: TrackedInstrument, instrument: Instrument) -> dict:
    def decimal_string(value: Decimal | None):
        return None if value is None else format(value, ".8f")
    return {
        "id": str(row.id), "instrument": instrument_json(instrument),
        "kind": row.kind, "quantity": decimal_string(row.quantity),
        "average_cost": decimal_string(row.average_cost),
        "alerts_enabled": row.alerts_enabled, "memo": row.memo,
        # Until a real quote provider is connected, NO synthetic valuation.
        "quote": {"status": "UNAVAILABLE", "close": None, "change_pct": None,
                  "as_of": None, "source": None},
        "market_value": None, "unrealized_pnl": None,
        "unrealized_pnl_percent": None,
    }


def query_filter(q: str | None):
    if not q:
        return None
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return or_(
        Instrument.name.ilike(f"%{escaped}%", escape="\\"),
        Instrument.normalized_symbol.ilike(f"%{escaped}%", escape="\\"),
    )


@router.post("/instruments", status_code=201)
def create_instrument(payload: InstrumentCreate):
    """Manual instrument metadata only; never price/quote or broker account."""
    meta = MARKET_META[payload.market]
    try:
        with Session(get_engine(), expire_on_commit=False) as db:
            with db.begin():
                row = Instrument(
                    market=payload.market, exchange_mic=payload.exchange_mic,
                    symbol=payload.symbol, normalized_symbol=payload.symbol,
                    name=payload.name, asset_type=payload.asset_type,
                    currency=meta["currency"], timezone=meta["timezone"],
                )
                db.add(row)
                db.flush()
                data = instrument_json(row)
        return data
    except IntegrityError:
        return error(409, "INSTRUMENT_ALREADY_EXISTS", "이미 등록된 거래소·종목 코드입니다.")
    except SQLAlchemyError:
        return error(503, "PORTFOLIO_DATABASE_UNAVAILABLE", "종목 저장소에 접근할 수 없습니다.")


@router.get("/instruments")
def list_instruments(
    q: Annotated[str | None, Query(max_length=80)] = None,
    market: Market | None = None,
    asset_type: AssetType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: UUID | None = None,
):
    try:
        with Session(get_engine()) as db:
            stmt = select(Instrument).where(Instrument.active.is_(True))
            if q is not None:
                clause = query_filter(q.strip())
                if clause is not None:
                    stmt = stmt.where(clause)
            if market is not None:
                stmt = stmt.where(Instrument.market == market)
            if asset_type is not None:
                stmt = stmt.where(Instrument.asset_type == asset_type)
            if cursor is not None:
                stmt = stmt.where(Instrument.id > cursor)
            rows = db.scalars(stmt.order_by(Instrument.id).limit(limit + 1)).all()
            return {"items": [instrument_json(v) for v in rows[:limit]],
                    "next_cursor": str(rows[limit - 1].id) if len(rows) > limit else None}
    except SQLAlchemyError:
        return error(503, "PORTFOLIO_DATABASE_UNAVAILABLE", "종목 조회가 불가능합니다.")


@router.get("/instruments/{instrument_id}")
def get_instrument(instrument_id: UUID):
    try:
        with Session(get_engine()) as db:
            row = db.get(Instrument, instrument_id)
            if row is None:
                return error(404, "INSTRUMENT_NOT_FOUND", "종목을 찾을 수 없습니다.")
            return instrument_json(row)
    except SQLAlchemyError:
        return error(503, "PORTFOLIO_DATABASE_UNAVAILABLE", "종목 조회가 불가능합니다.")


@router.get("/tracked")
def list_tracked(
    kind: Kind | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: UUID | None = None,
):
    try:
        with Session(get_engine()) as db:
            stmt = select(TrackedInstrument, Instrument).join(
                Instrument, TrackedInstrument.instrument_id == Instrument.id
            )
            if kind is not None:
                stmt = stmt.where(TrackedInstrument.kind == kind)
            if cursor is not None:
                stmt = stmt.where(TrackedInstrument.id > cursor)
            rows = db.execute(stmt.order_by(TrackedInstrument.id).limit(limit + 1)).all()
            return {
                "items": [tracked_json(row, inst) for row, inst in rows[:limit]],
                "next_cursor": str(rows[limit - 1][0].id) if len(rows) > limit else None,
            }
    except SQLAlchemyError:
        return error(503, "PORTFOLIO_DATABASE_UNAVAILABLE", "보유·관심 목록 조회가 불가능합니다.")


@router.post("/tracked", status_code=201)
def create_tracked(payload: TrackedCreate):
    if not position_valid(payload.kind, payload.quantity, payload.average_cost):
        return error(422, "INVALID_HOLDING", "보유 수량·평균단가 또는 관심종목 설정을 확인하세요.")
    try:
        with Session(get_engine(), expire_on_commit=False) as db:
            with db.begin():
                inst = db.get(Instrument, payload.instrument_id)
                if inst is None or not inst.active:
                    return error(404, "INSTRUMENT_NOT_FOUND", "종목을 찾을 수 없습니다.")
                row = TrackedInstrument(
                    instrument_id=inst.id, kind=payload.kind,
                    quantity=payload.quantity, average_cost=payload.average_cost,
                    alerts_enabled=payload.alerts_enabled, memo=payload.memo,
                )
                db.add(row)
                db.flush()
                data = tracked_json(row, inst)
        return data
    except IntegrityError:
        return error(409, "TRACKED_ALREADY_EXISTS", "이 종목은 이미 보유·관심 목록에 있습니다.")
    except SQLAlchemyError:
        return error(503, "PORTFOLIO_DATABASE_UNAVAILABLE", "보유·관심 목록을 저장할 수 없습니다.")


@router.patch("/tracked/{tracked_id}")
def update_tracked(tracked_id: UUID, payload: TrackedPatch):
    fields = payload.model_fields_set
    if not fields:
        return error(400, "EMPTY_PATCH", "변경할 값을 지정하세요.")
    if "kind" in fields and payload.kind is None:
        return error(422, "INVALID_KIND", "분류는 비워 둘 수 없습니다.")
    if "alerts_enabled" in fields and payload.alerts_enabled is None:
        return error(422, "INVALID_ALERTS", "알림 설정은 비워 둘 수 없습니다.")
    try:
        with Session(get_engine(), expire_on_commit=False) as db:
            with db.begin():
                found = db.execute(
                    select(TrackedInstrument, Instrument)
                    .join(Instrument, TrackedInstrument.instrument_id == Instrument.id)
                    .where(TrackedInstrument.id == tracked_id)
                ).one_or_none()
                if found is None:
                    return error(404, "TRACKED_NOT_FOUND", "등록 종목을 찾을 수 없습니다.")
                row, inst = found
                new_kind = payload.kind if "kind" in fields else row.kind
                # HOLDING -> WATCH intentionally discards holding values.
                if new_kind == "WATCH" and "kind" in fields:
                    qty = payload.quantity if "quantity" in fields else None
                    cost = payload.average_cost if "average_cost" in fields else None
                else:
                    qty = payload.quantity if "quantity" in fields else row.quantity
                    cost = payload.average_cost if "average_cost" in fields else row.average_cost
                if not position_valid(new_kind, qty, cost):
                    return error(422, "INVALID_HOLDING", "보유 수량·평균단가 또는 관심종목 설정을 확인하세요.")
                row.kind, row.quantity, row.average_cost = new_kind, qty, cost
                if "alerts_enabled" in fields:
                    row.alerts_enabled = payload.alerts_enabled
                if "memo" in fields:
                    row.memo = payload.memo
                db.flush()
                data = tracked_json(row, inst)
        return data
    except SQLAlchemyError:
        return error(503, "PORTFOLIO_DATABASE_UNAVAILABLE", "등록 종목을 수정할 수 없습니다.")


@router.delete("/tracked/{tracked_id}", status_code=204)
def delete_tracked(tracked_id: UUID):
    try:
        with Session(get_engine()) as db:
            with db.begin():
                row = db.get(TrackedInstrument, tracked_id)
                if row is None:
                    return error(404, "TRACKED_NOT_FOUND", "등록 종목을 찾을 수 없습니다.")
                db.delete(row)
        return None
    except SQLAlchemyError:
        return error(503, "PORTFOLIO_DATABASE_UNAVAILABLE", "등록 종목을 삭제할 수 없습니다.")


@router.get("/tracked/{tracked_id}/quote-status", response_model=TrackedQuoteStatusDTO)
def get_tracked_quote_status(tracked_id: UUID):
    """Owner-only status lookup; no KIS, price_bar, market values or writes.

    Phase MD-04C2 has NO verified price-quality store to consult: return
    UNAVAILABLE even if a partial price_bar exists. A strict response model
    prevents future changes from accidentally returning priced responses.
    """
    try:
        with Session(get_engine()) as db:
            exists = db.scalar(
                select(TrackedInstrument.id)
                .join(Instrument, TrackedInstrument.instrument_id == Instrument.id)
                .where(TrackedInstrument.id == tracked_id, Instrument.active.is_(True))
            )
            if exists is None:
                return error(404, "TRACKED_NOT_FOUND", "등록 종목을 찾을 수 없습니다.")
            return {
                "tracked_id": str(exists),
                "quote": masked_quote_from_finality(None),
            }
    except SQLAlchemyError:
        return error(503, "PORTFOLIO_DATABASE_UNAVAILABLE", "등록 종목의 상태를 확인할 수 없습니다.")
