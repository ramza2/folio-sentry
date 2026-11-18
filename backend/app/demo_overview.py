"""Fixed *fictional* data for designing UI; not a stock price feed."""
from datetime import datetime

from app.contract import DemoOverviewDTO

DEMO_REFERENCE = datetime.fromisoformat("2026-10-30T21:00:00+00:00")

# All values are made up. No upstream API, no account, no database access.
_DEMO_PAYLOAD = {
    "mode": "DEMO",
    "disclaimer": "예시 데이터이며 실제 시세·보유 내역·뉴스·매매 신호가 아닙니다.",
    "as_of": DEMO_REFERENCE,
    "summary": {
        "registered_count": 3,
        "holding_count": 2,
        "watch_count": 1,
        "available_signal_count": 2,
        "valuation_by_currency": {"KRW": "720000", "USD": "361.50"},
    },
    "tracked": [
        {
            "id": "21000000-0000-4000-8000-000000000001",
            "instrument": {
                "id": "10000000-0000-4000-8000-000000000001",
                "market": "KR",
                "exchange_mic": "XKRX",
                "symbol": "005930",
                "name": "삼성전자",
                "currency": "KRW",
                "asset_type": "STOCK",
            },
            "kind": "HOLDING",
            "quantity": "10",
            "average_cost": "70000",
            "quote": {
                "status": "DEMO",
                "close": "72000",
                "change_pct": "1.23",
                "as_of": "2026-10-30T06:30:00+00:00",
                "source": "MOCK",
            },
            "market_value": "720000",
            "unrealized_pnl": "20000",
            "unrealized_pnl_percent": "2.8571",
            "alerts_enabled": True,
        },
        {
            "id": "21000000-0000-4000-8000-000000000002",
            "instrument": {
                "id": "10000000-0000-4000-8000-000000000002",
                "market": "US",
                "exchange_mic": "XNAS",
                "symbol": "NVDA",
                "name": "NVIDIA",
                "currency": "USD",
                "asset_type": "STOCK",
            },
            "kind": "HOLDING",
            "quantity": "3",
            "average_cost": "110",
            "quote": {
                "status": "DEMO",
                "close": "120.50",
                "change_pct": "-0.58",
                "as_of": "2026-10-30T20:00:00+00:00",
                "source": "MOCK",
            },
            "market_value": "361.50",
            "unrealized_pnl": "31.50",
            "unrealized_pnl_percent": "9.5455",
            "alerts_enabled": True,
        },
        {
            "id": "21000000-0000-4000-8000-000000000003",
            "instrument": {
                "id": "10000000-0000-4000-8000-000000000003",
                "market": "US",
                "exchange_mic": "ARCX",
                "symbol": "SPY",
                "name": "SPDR S&P 500 ETF",
                "currency": "USD",
                "asset_type": "ETF",
            },
            "kind": "WATCH",
            "quantity": None,
            "average_cost": None,
            "quote": {
                "status": "UNAVAILABLE",
                "close": None,
                "change_pct": None,
                "as_of": None,
                "source": None,
            },
            "market_value": None,
            "unrealized_pnl": None,
            "unrealized_pnl_percent": None,
            "alerts_enabled": False,
        },
    ],
    "news": [
        {
            "id": "31000000-0000-4000-8000-000000000001",
            "instrument_id": "10000000-0000-4000-8000-000000000001",
            "title": "[데모 기사] 반도체 업황 관련 산업 동향",
            "publisher": "가상 뉴스 제공처",
            "published_at": "2026-10-30T02:00:00+00:00",
            "url": "https://example.com/demo/folio/news/1",
            "category": "INDUSTRY",
        },
        {
            "id": "31000000-0000-4000-8000-000000000002",
            "instrument_id": "10000000-0000-4000-8000-000000000002",
            "title": "[데모 기사] 해외 기술기업 투자 관련 주요 이슈",
            "publisher": "가상 뉴스 제공처",
            "published_at": "2026-10-30T17:30:00+00:00",
            "url": "https://example.com/demo/folio/news/2",
            "category": "OTHER",
        },
    ],
    "signals": [
        {
            "id": "41000000-0000-4000-8000-000000000001",
            "instrument_id": "10000000-0000-4000-8000-000000000001",
            "type": "BUY_REVIEW",
            "state": "DEMO",
            "session_date": "2026-10-30",
            "evaluated_at": "2026-10-30T06:45:00+00:00",
            "strategy_id": "demo-indicator-example",
            "strategy_version": "preview-1",
            "reason": "가상 지표 조합에 따른 매수 검토 화면 예시입니다. 실제 분석이 아닙니다.",
            "evidence": [
                {"metric": "RSI14", "observed": "43.2", "condition": "RSI 회복 가정", "met": True},
                {"metric": "VOLUME_RATIO", "observed": "0.9", "condition": "거래량 증가 가정", "met": False},
            ],
        },
        {
            "id": "41000000-0000-4000-8000-000000000002",
            "instrument_id": "10000000-0000-4000-8000-000000000002",
            "type": "HOLD",
            "state": "DEMO",
            "session_date": "2026-10-30",
            "evaluated_at": "2026-10-30T20:30:00+00:00",
            "strategy_id": "demo-indicator-example",
            "strategy_version": "preview-1",
            "reason": "가상 관망 상태를 표현하기 위한 UI 예시입니다.",
            "evidence": [],
        },
    ],
}


def get_demo_overview() -> DemoOverviewDTO:
    """Create a fresh validated DTO; mutation never leaks between requests."""
    return DemoOverviewDTO.model_validate(_DEMO_PAYLOAD)
