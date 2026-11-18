"""Clearly labelled fictional onboarding fixtures — never live quotes."""
from typing import Literal

from pydantic import BaseModel


class DemoInstrument(BaseModel):
    market: Literal["KR", "US"]
    exchange: str
    symbol: str
    name: str
    currency: Literal["KRW", "USD"]
    is_demo: Literal[True] = True


DEMO_INSTRUMENTS = (
    DemoInstrument(
        market="KR", exchange="XKRX", symbol="005930",
        name="삼성전자 (예시)", currency="KRW",
    ),
    DemoInstrument(
        market="US", exchange="XNAS", symbol="NVDA",
        name="NVIDIA (예시)", currency="USD",
    ),
)
