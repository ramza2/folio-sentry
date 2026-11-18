"""Phase 1A DTO contracts: no database, no broker, no live market calls."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstrumentDTO(StrictDTO):
    id: UUID
    market: Literal["KR", "US"]
    exchange_mic: str = Field(pattern=r"^[A-Z0-9]{4}$")
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1)
    currency: Literal["KRW", "USD"]
    asset_type: Literal["STOCK", "ETF"]


class QuoteDTO(StrictDTO):
    status: Literal["DEMO", "CURRENT", "STALE", "UNAVAILABLE"]
    close: Decimal | None
    change_pct: Decimal | None
    as_of: datetime | None
    source: str | None

    @model_validator(mode="after")
    def validate_missing_price(self):
        if self.status == "UNAVAILABLE" and (
            self.close is not None or self.change_pct is not None
        ):
            raise ValueError("UNAVAILABLE quotes must not contain prices")
        if self.close is not None and self.close <= 0:
            raise ValueError("quote close must be positive")
        if self.status in {"DEMO", "CURRENT", "STALE"} and (
            self.close is None or self.as_of is None or not self.source
        ):
            raise ValueError("available quotes require close, as_of and source")
        return self


class TrackedInstrumentDTO(StrictDTO):
    id: UUID
    instrument: InstrumentDTO
    kind: Literal["HOLDING", "WATCH"]
    quantity: Decimal | None
    average_cost: Decimal | None
    quote: QuoteDTO
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_percent: Decimal | None = None
    alerts_enabled: bool = True

    @model_validator(mode="after")
    def validate_holding(self):
        if self.kind == "WATCH" and any(
            value is not None
            for value in (
                self.quantity,
                self.average_cost,
                self.market_value,
                self.unrealized_pnl,
                self.unrealized_pnl_percent,
            )
        ):
            raise ValueError("WATCH cannot carry holdings or valuation")
        if self.quantity is not None and self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.average_cost is not None and self.average_cost < 0:
            raise ValueError("average_cost must not be negative")
        if self.average_cost is not None and self.quantity is None:
            raise ValueError("average_cost requires quantity")
        if self.quote.status == "UNAVAILABLE" and any(
            value is not None
            for value in (
                self.market_value,
                self.unrealized_pnl,
                self.unrealized_pnl_percent,
            )
        ):
            raise ValueError("valuation requires an available quote")
        return self


class NewsDTO(StrictDTO):
    id: UUID
    instrument_id: UUID
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    published_at: datetime
    url: HttpUrl
    category: Literal["RESULT", "REGULATION", "INDUSTRY", "OTHER"]


class EvidenceDTO(StrictDTO):
    metric: str
    observed: Decimal | None
    condition: str
    met: bool


class SignalDTO(StrictDTO):
    id: UUID
    instrument_id: UUID
    type: Literal["BUY_REVIEW", "SELL_REVIEW", "HOLD", "RISK"]
    state: Literal["DEMO", "FINAL", "SUPPRESSED"]
    session_date: date
    evaluated_at: datetime
    strategy_id: str
    strategy_version: str
    reason: str
    evidence: list[EvidenceDTO]


class OverviewSummaryDTO(StrictDTO):
    registered_count: int = Field(ge=0)
    holding_count: int = Field(ge=0)
    watch_count: int = Field(ge=0)
    available_signal_count: int = Field(ge=0)
    # Separate currencies, never total KRW and USD into one number.
    valuation_by_currency: dict[Literal["KRW", "USD"], Decimal]


class DemoOverviewDTO(StrictDTO):
    mode: Literal["DEMO"]
    disclaimer: str
    as_of: datetime
    summary: OverviewSummaryDTO
    tracked: list[TrackedInstrumentDTO]
    news: list[NewsDTO]
    signals: list[SignalDTO]
