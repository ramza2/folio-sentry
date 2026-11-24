"""MD-05B owner-triggered KIS current/last-price provider, OFF BY DEFAULT.

This is NOT a realtime tick stream. KIS REST examples explicitly direct
realtime users to websocket; overseas prices may be delayed. No provider tick
timestamp is established. Returned last price is informational only.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Callable, Literal, Mapping

from app.kis_readonly import (
    KR_CURRENT_PATH, US_CURRENT_PATH, KisCredentials, KisHttpsTransport,
    KisReadOnlyError, SharedQuoteGate, Transport,
)
from app.market_data import InstrumentIdentity, MarketDataContractError

PRICE_RE = re.compile(r"^(0|[1-9][0-9]{0,15})(?:\.[0-9]{1,8})?$")
CURRENT_TR = {
    KR_CURRENT_PATH: "FHKST01010100",
    US_CURRENT_PATH: "HHDFS00000300",
}


@dataclass(frozen=True, slots=True)
class CurrentQuoteCandidate:
    instrument: InstrumentIdentity
    price: Decimal | None
    fetched_at: datetime | None
    source: Literal["KIS"] = "KIS"
    provider_observed_at: None = None
    realtime_verified: Literal[False] = False
    is_final: Literal[False] = False


def parse_current_quote(
    response: Mapping[str, object], *,
    identity: InstrumentIdentity, fetched_at: datetime,
) -> CurrentQuoteCandidate:
    if not isinstance(identity, InstrumentIdentity) or (
        not isinstance(fetched_at, datetime)
        or fetched_at.tzinfo is None or fetched_at.utcoffset() is None
    ):
        raise MarketDataContractError("MD05B_QUOTE_CONTEXT_INVALID")
    if not isinstance(response, Mapping) or response.get("rt_cd") != "0":
        raise MarketDataContractError("MD05B_KIS_RESPONSE_INVALID")
    raw = response.get("output")
    if not isinstance(raw, Mapping):
        raise MarketDataContractError("MD05B_KIS_OUTPUT_INVALID")
    field = "stck_prpr" if identity.market == "KR" else "last"
    value = raw.get(field)
    if value is None or value == "":
        return CurrentQuoteCandidate(identity, None, None)
    if type(value) is not str or PRICE_RE.fullmatch(value) is None:
        raise MarketDataContractError("MD05B_KIS_PRICE_INVALID")
    try:
        price = Decimal(value)
    except InvalidOperation:
        raise MarketDataContractError("MD05B_KIS_PRICE_INVALID") from None
    if not price.is_finite() or price <= 0:
        raise MarketDataContractError("MD05B_KIS_PRICE_INVALID")
    if identity.market == "KR":
        returned_symbol = raw.get("stck_shrn_iscd")
        if returned_symbol is not None and returned_symbol != identity.symbol:
            raise MarketDataContractError("MD05B_KIS_INSTRUMENT_MISMATCH")
    else:
        # KIS's 'rsym' can include a prefix/exchange; never trust one
        # ending in a different symbol when supplied by the provider.
        returned_symbol = raw.get("rsym")
        if returned_symbol is not None and (
            type(returned_symbol) is not str
            or not returned_symbol.endswith(identity.symbol)
        ):
            raise MarketDataContractError("MD05B_KIS_INSTRUMENT_MISMATCH")
    return CurrentQuoteCandidate(
        instrument=identity, price=price,
        fetched_at=fetched_at.astimezone(timezone.utc),
    )


class KisReadOnlyCurrentProvider:
    """One KIS request through persistent cross-process quota shared with MD05A.

    SharedQuoteGate is REQUIRED; never fall back to unsynchronized token logic.
    Only exact read-only TR/path pairs are possible.
    """

    def __init__(
        self, credentials: KisCredentials, shared_state: SharedQuoteGate, *,
        live_enabled: bool = False, allow_new_token: bool = False,
        transport: Transport | None = None,
        utcnow: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        if not isinstance(credentials, KisCredentials):
            raise KisReadOnlyError("INVALID_KIS_CREDENTIALS")
        if shared_state is None or not callable(getattr(shared_state, "call_quote", None)):
            raise KisReadOnlyError("KIS_SHARED_STATE_REQUIRED")
        self._credentials = credentials
        self._shared_state = shared_state
        self._live = live_enabled
        self._allow_new_token = allow_new_token
        self._transport = transport if transport is not None else KisHttpsTransport()
        self._utcnow = utcnow

    def fetch_current(self, identity: InstrumentIdentity) -> CurrentQuoteCandidate:
        if not isinstance(identity, InstrumentIdentity):
            raise MarketDataContractError("INVALID_INSTRUMENT")
        if not self._live:
            raise KisReadOnlyError("KIS_LIVE_READ_DISABLED")
        if identity.market == "KR":
            path = KR_CURRENT_PATH
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": identity.symbol,
            }
        else:
            path = US_CURRENT_PATH
            params = {
                "AUTH": "",
                "EXCD": identity.kis_exchange_code,
                "SYMB": identity.symbol,
            }
        result = self._shared_state.call_quote(
            self._credentials, self._transport,
            path=path, tr_id=CURRENT_TR[path], params=params,
            live_enabled=True, allow_new_token=self._allow_new_token,
        )
        return parse_current_quote(
            result, identity=identity, fetched_at=self._utcnow(),
        )
