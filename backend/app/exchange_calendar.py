"""Explicit, source-cited exchange sessions. Unknown days fail closed.

Only dates manually checked against official exchange calendars/announcements
are represented here. This intentionally is NOT a complete yearly calendar,
an online updater, or evidence that KIS settlement prices are final.
"""
from dataclasses import dataclass
from datetime import date, time
from typing import Literal

from app.market_data import InstrumentIdentity

Status = Literal["OPEN", "CLOSED"]


class ExchangeCalendarError(ValueError):
    """Static, non-sensitive failure code."""


@dataclass(frozen=True)
class AttestedExchangeSession:
    exchange_mic: str
    session_date: date
    status: Status
    opens_at: time | None
    closes_at: time | None
    source_url: str

    def __post_init__(self):
        if self.status not in ("OPEN", "CLOSED"):
            raise ExchangeCalendarError("INVALID_SESSION_STATUS")
        if self.status == "OPEN":
            if not isinstance(self.opens_at, time) or not isinstance(self.closes_at, time) \
                    or self.opens_at >= self.closes_at:
                raise ExchangeCalendarError("INVALID_SESSION_HOURS")
        elif self.opens_at is not None or self.closes_at is not None:
            raise ExchangeCalendarError("CLOSED_SESSION_HAS_HOURS")
        if not self.source_url.startswith("https://"):
            raise ExchangeCalendarError("INVALID_SESSION_EVIDENCE")


KRX_KOSPI_NOTICE = (
    "https://kind.krx.co.kr/external/2026/11/05/000141/"
    "20261105000216/99303.htm"
)
KRX_KOSDAQ_NOTICE = (
    "https://kind.krx.co.kr/external/2026/11/05/000145/"
    "20261104001218/70780.htm"
)
NYSE_CALENDAR = "https://www.nyse.com/trade/hours-calendars"
NASDAQ_CALENDAR = (
    "https://www.nasdaq.com/market-activity/stock-market-holiday-schedule"
)


def _session(exchange: str, day: str, status: Status, source: str,
             opens: tuple[int, int] | None = None,
             closes: tuple[int, int] | None = None) -> AttestedExchangeSession:
    return AttestedExchangeSession(
        exchange_mic=exchange, session_date=date.fromisoformat(day),
        status=status,
        opens_at=time(*opens) if opens is not None else None,
        closes_at=time(*closes) if closes is not None else None,
        source_url=source,
    )


# Explicit limited whitelist, not an inferred calendar. Evidence was checked
# November 20, 2026. Events may be superseded by future exchange notices.
_KNOWN = [
    _session("XKRX", "2026-11-19", "OPEN", KRX_KOSPI_NOTICE, (10, 0), (16, 30)),
    _session("XKOS", "2026-11-19", "OPEN", KRX_KOSDAQ_NOTICE, (10, 0), (16, 30)),
    _session("XNAS", "2026-11-19", "OPEN", NASDAQ_CALENDAR, (9, 30), (16, 0)),
    _session("XNYS", "2026-11-19", "OPEN", NYSE_CALENDAR, (9, 30), (16, 0)),
    _session("XASE", "2026-11-19", "OPEN", NYSE_CALENDAR, (9, 30), (16, 0)),
    # US Thanksgiving: all cash equity markets closed.
    *[
        _session(exchange, "2026-11-26", "CLOSED", source)
        for exchange, source in (
            ("XNAS", NASDAQ_CALENDAR), ("XNYS", NYSE_CALENDAR), ("XASE", NYSE_CALENDAR)
        )
    ],
    # Both Nasdaq and NYSE groups post the early 13:00 ET closing.
    *[
        _session(exchange, "2026-11-27", "OPEN", source, (9, 30), (13, 0))
        for exchange, source in (
            ("XNAS", NASDAQ_CALENDAR), ("XNYS", NYSE_CALENDAR), ("XASE", NYSE_CALENDAR)
        )
    ],
    *[
        _session(exchange, "2026-12-24", "OPEN", source, (9, 30), (13, 0))
        for exchange, source in (
            ("XNAS", NASDAQ_CALENDAR), ("XNYS", NYSE_CALENDAR), ("XASE", NYSE_CALENDAR)
        )
    ],
    # March 9 2026 is a regular US trading day under EDT, DST regression.
    _session("XNAS", "2026-03-09", "OPEN", NASDAQ_CALENDAR, (9, 30), (16, 0)),
]
_BY_KEY = {(s.exchange_mic, s.session_date): s for s in _KNOWN}
assert len(_BY_KEY) == len(_KNOWN)


def attested_session(identity: InstrumentIdentity, day: date) -> AttestedExchangeSession:
    if not isinstance(identity, InstrumentIdentity) or not isinstance(day, date):
        raise ExchangeCalendarError("INVALID_SESSION_LOOKUP")
    session = _BY_KEY.get((identity.exchange_mic, day))
    if session is None:
        raise ExchangeCalendarError("PRICE_SESSION_CALENDAR_UNVERIFIED")
    if session.status != "OPEN":
        raise ExchangeCalendarError("PRICE_EXCHANGE_CLOSED")
    return session
