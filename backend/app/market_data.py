"""Offline-only Phase 1 market-data normalization boundary (no network or DB access).

The adapter intentionally DOES NOT declare bars final or publish quotes. KIS
requires account/credentials; caller must first independently establish the
provider's quote permissions, adjustment basis and source observation time.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Literal, Mapping, Protocol
from zoneinfo import ZoneInfo

Market = Literal["KR", "US"]
PriceBasis = Literal["RAW", "ADJUSTED"]

KIS_MARKET = {
    "XKRX": ("KR", "KRW", "Asia/Seoul", "J"),
    "XKOS": ("KR", "KRW", "Asia/Seoul", "J"),
    "XNAS": ("US", "USD", "America/New_York", "NAS"),
    "XNYS": ("US", "USD", "America/New_York", "NYS"),
    "XASE": ("US", "USD", "America/New_York", "AMS"),
}
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.-]{1,32}$")
DECIMAL_PATTERN = re.compile(r"^(0|[1-9][0-9]{0,15})(?:\.[0-9]{1,8})?$")
VOLUME_PATTERN = re.compile(r"^(0|[1-9][0-9]{0,27})$")


class MarketDataContractError(ValueError):
    """Provider values were incomplete, inconsistent, or unsuitable for use."""


@dataclass(frozen=True)
class InstrumentIdentity:
    market: Market
    exchange_mic: str
    symbol: str
    currency: str

    def __post_init__(self):
        meta = KIS_MARKET.get(self.exchange_mic)
        if meta is None or (self.market, self.currency) != meta[:2]:
            raise MarketDataContractError("UNSUPPORTED_MARKET_OR_CURRENCY")
        if not SYMBOL_PATTERN.fullmatch(self.symbol):
            raise MarketDataContractError("INVALID_SYMBOL")
        if self.market == "KR" and not re.fullmatch(r"\d{6}", self.symbol):
            raise MarketDataContractError("INVALID_KR_SYMBOL")

    @property
    def kis_exchange_code(self) -> str:
        return KIS_MARKET[self.exchange_mic][3]

    @property
    def exchange_timezone(self) -> ZoneInfo:
        return ZoneInfo(KIS_MARKET[self.exchange_mic][2])


@dataclass(frozen=True)
class DailyBarCandidate:
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    price_basis: PriceBasis
    source: Literal["KIS"]
    fetched_at: datetime
    # KIS daily-bar row does NOT guarantee an observation timestamp or
    # finalized settlement. Never derive it from the time we fetched the row.
    source_observed_at: None = None
    is_final: Literal[False] = False


@dataclass(frozen=True)
class DailyBarBatch:
    instrument: InstrumentIdentity
    bars: tuple[DailyBarCandidate, ...]
    provider: Literal["KIS"] = "KIS"

    @property
    def availability(self) -> Literal["UNAVAILABLE", "UNFINALIZED"]:
        return "UNFINALIZED" if self.bars else "UNAVAILABLE"


class DailyBarProvider(Protocol):
    """Future transport boundary. No transport is implemented in this PR."""

    def fetch_daily(
        self, identity: InstrumentIdentity, start: date, end: date,
        price_basis: PriceBasis,
    ) -> DailyBarBatch: ...


def _price(value: object) -> Decimal:
    if not isinstance(value, str) or DECIMAL_PATTERN.fullmatch(value) is None:
        raise MarketDataContractError("INVALID_DECIMAL_PRICE")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise MarketDataContractError("INVALID_DECIMAL_PRICE") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise MarketDataContractError("NONPOSITIVE_PRICE")
    return parsed


def _volume(value: object) -> int:
    if not isinstance(value, str) or VOLUME_PATTERN.fullmatch(value) is None:
        raise MarketDataContractError("INVALID_VOLUME")
    return int(value)


def _session_day(value: object) -> date:
    if not isinstance(value, str) or re.fullmatch(r"\d{8}", value) is None:
        raise MarketDataContractError("INVALID_SESSION_DATE")
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise MarketDataContractError("INVALID_SESSION_DATE") from exc


def _row_to_bar(
    raw: Mapping[str, object], *, market: Market, basis: PriceBasis,
    fetched_at: datetime,
) -> DailyBarCandidate:
    if market == "KR":
        names = ("stck_bsop_date", "stck_oprc", "stck_hgpr",
                 "stck_lwpr", "stck_clpr", "acml_vol")
    else:
        names = ("xymd", "open", "high", "low", "clos", "tvol")
    try:
        day = _session_day(raw[names[0]])
        opn, high, low, close = (_price(raw[n]) for n in names[1:5])
        volume = _volume(raw[names[5]])
    except KeyError as exc:
        raise MarketDataContractError("MISSING_OHLCV_FIELD") from exc
    if low > min(opn, close) or high < max(opn, close) or low > high:
        raise MarketDataContractError("INCONSISTENT_OHLC")
    return DailyBarCandidate(
        session_date=day, open=opn, high=high, low=low, close=close,
        volume=volume, price_basis=basis, source="KIS",
        fetched_at=fetched_at,
    )


def normalize_kis_daily_response(
    payload: Mapping[str, object], *,
    identity: InstrumentIdentity,
    price_basis: PriceBasis,
    fetched_at: datetime,
) -> DailyBarBatch:
    """Parse an already-obtained KIS daily response, strict all-or-nothing.

    This does not make live HTTP calls, fetch credentials, write to the database
    or expose values to the portfolio UI. Finality, source timestamp, market
    permissions, price-basis selector and symbol validation are future gates.
    """
    if price_basis not in ("RAW", "ADJUSTED"):
        raise MarketDataContractError("INVALID_PRICE_BASIS")
    if not isinstance(fetched_at, datetime) or fetched_at.tzinfo is None \
            or fetched_at.utcoffset() is None:
        raise MarketDataContractError("FETCHED_AT_MUST_BE_TIMEZONE_AWARE")
    if not isinstance(payload, Mapping) or payload.get("rt_cd") != "0":
        raise MarketDataContractError("KIS_RESPONSE_NOT_SUCCESSFUL")
    rows = payload.get("output2")
    if not isinstance(rows, list) or len(rows) > 200:
        raise MarketDataContractError("INVALID_BAR_BATCH")
    local_today = fetched_at.astimezone(identity.exchange_timezone).date()
    found = set()
    result = []
    utc_fetched = fetched_at.astimezone(timezone.utc)
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise MarketDataContractError("INVALID_BAR_ROW")
        bar = _row_to_bar(raw, market=identity.market, basis=price_basis,
                          fetched_at=utc_fetched)
        if bar.session_date > local_today:
            raise MarketDataContractError("FUTURE_SESSION_DATE")
        if bar.session_date in found:
            raise MarketDataContractError("DUPLICATE_SESSION_DATE")
        found.add(bar.session_date)
        result.append(bar)
    result.sort(key=lambda item: item.session_date)
    return DailyBarBatch(instrument=identity, bars=tuple(result))
