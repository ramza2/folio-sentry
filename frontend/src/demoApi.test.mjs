import test from "node:test";
import assert from "node:assert/strict";

import {
  parseDemoOverview, formatMoney, formatPercent, formatQuantity,
  stockViews, fetchDemoOverview, signalBadge,
} from "./demoApi.ts";

const emptyFixture = () => ({
  mode: "DEMO",
  disclaimer: "예시 데이터이며 실제 시세가 아닙니다.",
  as_of: "2026-10-30T21:00:00+00:00",
  summary: {
    registered_count: 0,
    holding_count: 0,
    watch_count: 0,
    available_signal_count: 0,
    valuation_by_currency: {},
  },
  tracked: [], news: [], signals: [],
});

const stockFixture = () => {
  const fixture = emptyFixture();
  fixture.summary = {
    registered_count: 2, holding_count: 1, watch_count: 1,
    available_signal_count: 1,
    valuation_by_currency: { KRW: "720000", USD: "0" },
  };
  fixture.tracked = [
    {
      id: "tracked-1", kind: "HOLDING", quantity: "10", average_cost: "70000",
      market_value: "720000", unrealized_pnl: "20000",
      unrealized_pnl_percent: "2.8571", alerts_enabled: true,
      instrument: {
        id: "instrument-1", market: "KR", exchange_mic: "XKRX",
        symbol: "005930", name: "삼성전자", currency: "KRW", asset_type: "STOCK",
      },
      quote: {
        status: "DEMO", close: "72000", change_pct: "1.23",
        as_of: "2026-10-30T06:30:00+00:00", source: "MOCK",
      },
    },
    {
      id: "tracked-2", kind: "WATCH", quantity: null, average_cost: null,
      market_value: null, unrealized_pnl: null,
      unrealized_pnl_percent: null, alerts_enabled: false,
      instrument: {
        id: "instrument-2", market: "US", exchange_mic: "ARCX",
        symbol: "SPY", name: "SPDR S&P500 ETF", currency: "USD", asset_type: "ETF",
      },
      quote: {
        status: "UNAVAILABLE", close: null, change_pct: null,
        as_of: null, source: null,
      },
    },
  ];
  fixture.signals = [{
    id: "signal-1", instrument_id: "instrument-1",
    type: "BUY_REVIEW", state: "DEMO", session_date: "2026-10-30",
    evaluated_at: "2026-10-30T06:45:00+00:00",
    strategy_id: "demo", strategy_version: "preview-1",
    reason: "가상 RSI 조건", evidence: [
      { metric: "RSI14", observed: "43.2", condition: "가상 조건", met: true },
    ],
  }];
  return fixture;
};

test("strict DEMO contract rejects non-DEMO payload", () => {
  const fixture = emptyFixture();
  assert.equal(parseDemoOverview(fixture).mode, "DEMO");
  assert.throws(() => parseDemoOverview({ ...fixture, mode: "LIVE" }), /DEMO/);
  assert.throws(() => parseDemoOverview({ ...fixture, tracked: null }), /DEMO/);
});

test("decimal values are formatted without floating-point conversions", () => {
  assert.equal(formatMoney("72000", "KRW"), "72,000원");
  assert.equal(formatMoney("120.50", "USD"), "$120.50");
  assert.equal(formatMoney("-21.3456", "USD", true), "-$21.3456");
  assert.equal(formatMoney("0", "USD"), "$0.00");
  assert.equal(formatMoney(null, "KRW"), "—");
  assert.equal(formatPercent("2.8571"), "+2.8571%");
  assert.equal(formatQuantity("10.25"), "10.25주");
});

test("unavailable quote remains null; no synthetic price appears", () => {
  const views = stockViews(parseDemoOverview(stockFixture()));
  assert.equal(views[0].price, "72,000원");
  assert.equal(views[0].signal, "매수 검토");
  assert.equal(views[1].price, "시세 없음");
  assert.equal(views[1].pnl, "—");
  assert.equal(views[1].quoteStatus, "UNAVAILABLE");
});

test("reject invalid watchlist valuation and incomplete demo quote", () => {
  const invalidWatch = stockFixture();
  invalidWatch.tracked[1].market_value = "15";
  assert.throws(() => parseDemoOverview(invalidWatch), /관심 종목/);

  const invalidQuote = stockFixture();
  invalidQuote.tracked[0].quote.as_of = null;
  assert.throws(() => parseDemoOverview(invalidQuote), /기준시각/);
});

test("reject forged email/sent state masquerading as DEMO signal", () => {
  const fixture = stockFixture();
  fixture.signals[0].state = "FINAL";
  assert.throws(() => parseDemoOverview(fixture), /신호 데이터/);
  assert.equal(signalBadge("BUY_REVIEW").label, "매수 검토");
});

test("network error never falls back to hard-coded quotes", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 503 });
  try {
    await assert.rejects(fetchDemoOverview(), /HTTP 503/);
  } finally {
    globalThis.fetch = original;
  }
});
