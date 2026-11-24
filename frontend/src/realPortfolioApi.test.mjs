import test from "node:test";
import assert from "node:assert/strict";
import {
  loadInstruments, loadTracked, loadTrackedQuoteStatus,
  loadManualReferenceCapability, loadManualDailyReference,
  loadManualCurrentCapability, loadManualCurrentQuote, loadValuationCapability,
  addInstrument, addTracked, editTracked, removeTracked,
} from "./realPortfolioApi.ts";

const csrf = "test-csrf-token-abcdefghijklmnopqrstuvwxyz-0123456789";
const manual = {
  id: "11111111-1111-4111-8111-111111111111",
  market: "KR", exchange_mic: "XKRX", symbol: "005930",
  name: "synthetic-company", currency: "KRW", asset_type: "STOCK",
  source: "MANUAL_UNVERIFIED",
};
const position = {
  id: "22222222-2222-4222-8222-222222222222",
  instrument: manual, kind: "HOLDING",
  quantity: "2.00000000", average_cost: "70000.50000000",
  alerts_enabled: false, memo: null,
  quote: { status: "UNAVAILABLE", close: null, change_pct: null, as_of: null, source: null },
  market_value: null, unrealized_pnl: null, unrealized_pnl_percent: null,
};
const okJson = (value, status = 200) => ({ ok: true, status, json: async () => value });

test("real portfolio GET reads only protected non-demo paths", async () => {
  const prior = globalThis.fetch;
  const called = [];
  globalThis.fetch = async (url, opt) => {
    called.push(url);
    assert.equal(opt.credentials, "same-origin");
    assert.equal(opt.cache, "no-store");
    return url.includes("instruments")
      ? okJson({ items: [manual], next_cursor: null })
      : okJson({ items: [position], next_cursor: null });
  };
  try {
    assert.equal((await loadInstruments("005930")).items[0].source, "MANUAL_UNVERIFIED");
    assert.equal((await loadTracked()).items[0].quote.status, "UNAVAILABLE");
    assert.equal(called.length, 2);
    assert.ok(called.every((url) => url.startsWith("/api/v1/") && !url.includes("/demo/")));
  } finally { globalThis.fetch = prior; }
});

test("mutations send JSON decimal strings with CSRF, not localStorage", async () => {
  const prior = globalThis.fetch;
  const called = [];
  globalThis.fetch = async (url, opt) => {
    called.push([url, opt]);
    if (url.endsWith("/instruments")) return okJson(manual, 201);
    if (url.endsWith("/tracked")) return okJson(position, 201);
    if (opt.method === "PATCH") return okJson({ ...position, kind: "WATCH", quantity: null, average_cost: null });
    if (opt.method === "DELETE") return { ok: true, status: 204 };
    throw Error("unexpected URL");
  };
  try {
    await addInstrument({ market: "KR", exchange_mic: "XKRX", symbol: "005930",
      name: "synthetic-company", asset_type: "STOCK" }, csrf);
    await addTracked({ instrument_id: manual.id, kind: "HOLDING",
      quantity: "2.00000000", average_cost: "70000.50000000",
      alerts_enabled: false, memo: null }, csrf);
    await editTracked(position.id, { kind: "WATCH", quantity: null, average_cost: null }, csrf);
    await removeTracked(position.id, csrf);
    assert.deepEqual(called.map((x) => x[1].method), ["POST", "POST", "PATCH", "DELETE"]);
    assert.ok(called.every((x) => x[1].headers["X-CSRF-Token"] === csrf));
    assert.ok(called.every((x) => x[1].credentials === "same-origin"));
    const saved = JSON.parse(called[1][1].body);
    assert.equal(saved.average_cost, "70000.50000000");
    assert.equal(typeof saved.average_cost, "string");
  } finally { globalThis.fetch = prior; }
});

test("price-bearing or DEMO data can never appear in real positions", async () => {
  const prior = globalThis.fetch;
  globalThis.fetch = async () => okJson({
    items: [{ ...position, quote: { ...position.quote, status: "DEMO", close: "99999" } }],
    next_cursor: null,
  });
  try { await assert.rejects(loadTracked(), /검증되지 않은 실제 시세 응답을 차단했습니다/); }
  finally { globalThis.fetch = prior; }
});

test("future quality-only statuses are accepted without financial values", async () => {
  const prior = globalThis.fetch;
  try {
    for (const status of ["UNFINALIZED", "STALE", "ERROR"]) {
      globalThis.fetch = async () => okJson({
        items: [{ ...position, quote: { ...position.quote, status } }],
        next_cursor: null,
      });
      const item = (await loadTracked()).items[0];
      assert.equal(item.quote.status, status);
      assert.equal(item.quote.close, null);
      assert.equal(item.market_value, null);
      assert.equal(item.unrealized_pnl, null);
      assert.equal(item.unrealized_pnl_percent, null);
    }
  } finally { globalThis.fetch = prior; }
});

test("non-final state cannot smuggle a price, as_of, source or promotion", async () => {
  const prior = globalThis.fetch;
  const malicious = [
    { status: "UNFINALIZED", close: "105" },
    { status: "STALE", as_of: "2026-11-20" },
    { status: "ERROR", source: "KIS" },
    { status: "UNFINALIZED", is_final: true },
    { status: "CURRENT" },
  ];
  try {
    for (const injected of malicious) {
      globalThis.fetch = async () => okJson({
        items: [{ ...position, quote: { ...position.quote, ...injected } }],
        next_cursor: null,
      });
      await assert.rejects(loadTracked());
    }
  } finally { globalThis.fetch = prior; }
});

test("schema failure is not replaced with mock holdings", async () => {
  const prior = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 503 });
  try {
    await assert.rejects(loadTracked(), /아직 준비되지/);
    await assert.rejects(loadInstruments(), /아직 준비되지/);
  } finally { globalThis.fetch = prior; }
});

test("missing CSRF prevents any mutation request", async () => {
  const prior = globalThis.fetch;
  globalThis.fetch = async () => { throw Error("must not send"); };
  try {
    await assert.rejects(addTracked({
      instrument_id: manual.id, kind: "WATCH",
      quantity: null, average_cost: null, alerts_enabled: false, memo: null,
    }, "x"), /유효한 인증 세션/);
  } finally { globalThis.fetch = prior; }
});


test("owner-only status GET uses no-store, does not contact demo, and returns no prices", async () => {
  const prior = globalThis.fetch;
  const called = [];
  globalThis.fetch = async (url, options) => {
    called.push([url, options]);
    return okJson({
      tracked_id: position.id,
      quote: { ...position.quote, status: "UNAVAILABLE" },
    });
  };
  try {
    const quote = await loadTrackedQuoteStatus(position.id);
    assert.deepEqual(quote, position.quote);
    assert.equal(called.length, 1);
    assert.equal(called[0][0], "/api/v1/tracked/" + position.id + "/quote-status");
    assert.equal(called[0][1].credentials, "same-origin");
    assert.equal(called[0][1].cache, "no-store");
    assert.equal(called[0][1].method, undefined);
    assert.equal(called[0][1].headers.Accept, "application/json");
    assert.ok(!called[0][0].includes("demo"));
    assert.ok(!called[0][0].includes("kis"));
    assert.equal(quote.close, null);
  } finally { globalThis.fetch = prior; }
});

test("status-only GET requires exact tracked identity and disallows added financial data", async () => {
  const prior = globalThis.fetch;
  const invalid = [
    { tracked_id: manual.id, quote: position.quote },
    { tracked_id: position.id, quote: { ...position.quote, close: "105" } },
    { tracked_id: position.id, quote: { ...position.quote, status: "CURRENT" } },
    { tracked_id: position.id, quote: { ...position.quote, is_final: true } },
    { tracked_id: position.id, quote: position.quote, market_value: "210" },
    { tracked_id: position.id, quote: position.quote, unrealized_pnl: "10" },
    { quote: position.quote },
    {},
  ];
  try {
    for (const payload of invalid) {
      globalThis.fetch = async () => okJson(payload);
      await assert.rejects(loadTrackedQuoteStatus(position.id));
    }
  } finally { globalThis.fetch = prior; }
});

test("authenticated status GET surfaces 401/404/503 without fake fallback", async () => {
  const prior = globalThis.fetch;
  try {
    for (const [code, message] of [
      [401, /세션이 만료/],
      [404, /찾을 수 없/],
      [503, /준비되지/],
    ]) {
      globalThis.fetch = async () => ({ ok: false, status: code });
      await assert.rejects(loadTrackedQuoteStatus(position.id), message);
    }
  } finally { globalThis.fetch = prior; }
});

const rawReference = {
  status: "REFERENCE",
  close: "105.25000000",
  session_date: "2026-11-20",
  fetched_at: "2026-11-23T02:15:00+00:00",
  source: "KIS",
  price_basis: "RAW",
  currency: "KRW",
  is_final: false,
};

test("manual reference capability is strict, no-store and owner-auth GET", async () => {
  const prior = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options]);
    return okJson({ manual_daily_reference_enabled: true });
  };
  try {
    assert.equal(await loadManualReferenceCapability(), true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], "/api/v1/market-data/capabilities");
    assert.equal(calls[0][1].credentials, "same-origin");
    assert.equal(calls[0][1].cache, "no-store");
    assert.equal(calls[0][1].method, undefined);
    assert.ok(!calls[0][0].includes("kis"));
    globalThis.fetch = async () => okJson({ manual_daily_reference_enabled: "true" });
    await assert.rejects(loadManualReferenceCapability(), /기능 상태/);
    globalThis.fetch = async () => okJson({ manual_daily_reference_enabled: true, secret: "oops" });
    await assert.rejects(loadManualReferenceCapability(), /기능 상태/);
  } finally { globalThis.fetch = prior; }
});

test("explicit reference request uses POST with CSRF, never modifies hidden quote", async () => {
  const prior = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push([url, options]);
    return okJson({ tracked_id: position.id, reference: rawReference });
  };
  try {
    const reference = await loadManualDailyReference(position.id, csrf);
    assert.deepEqual(reference, rawReference);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], "/api/v1/tracked/" + position.id + "/daily-reference");
    assert.equal(calls[0][1].method, "POST");
    assert.equal(calls[0][1].headers["X-CSRF-Token"], csrf);
    assert.equal(calls[0][1].credentials, "same-origin");
    assert.equal(calls[0][1].cache, "no-store");
    assert.equal(position.quote.status, "UNAVAILABLE");
    assert.equal(position.quote.close, null);
    assert.equal(position.market_value, null);
    assert.ok(!calls[0][0].includes("demo"));
    assert.ok(!calls[0][0].includes("kis"));
  } finally { globalThis.fetch = prior; }
});

test("manual reference without valid CSRF cannot send any request", async () => {
  const prior = globalThis.fetch;
  globalThis.fetch = async () => { throw Error("network must not be called"); };
  try { await assert.rejects(loadManualDailyReference(position.id, "short"), /유효한 인증/); }
  finally { globalThis.fetch = prior; }
});

test("STALE or UNAVAILABLE reference never contains a price", async () => {
  const prior = globalThis.fetch;
  try {
    for (const reference of [
      { ...rawReference, status: "STALE", close: null },
      { ...rawReference, status: "UNAVAILABLE", close: null, session_date: null,
        fetched_at: null, source: null, price_basis: null },
    ]) {
      globalThis.fetch = async () => okJson({
        tracked_id: position.id, reference,
      });
      assert.deepEqual(await loadManualDailyReference(position.id, csrf), reference);
    }
  } finally { globalThis.fetch = prior; }
});

test("manual reference rejects injected provider/financial fields and fake finality", async () => {
  const prior = globalThis.fetch;
  const invalid = [
    { ...rawReference, is_final: true },
    { ...rawReference, status: "CURRENT" },
    { ...rawReference, status: "FINAL" },
    { ...rawReference, source: "DEMO" },
    { ...rawReference, price_basis: "ADJUSTED" },
    { ...rawReference, close: 105.25 },
    { ...rawReference, close: "-20" },
    { ...rawReference, close: "0" },
    { ...rawReference, session_date: "not-a-date" },
    { ...rawReference, fetched_at: "not-time" },
    { ...rawReference, extra: "token" },
    { ...rawReference, market_value: "105" },
    { ...rawReference, status: "STALE" },
    { ...rawReference, status: "UNAVAILABLE", close: "105" },
  ];
  try {
    for (const reference of invalid) {
      globalThis.fetch = async () => okJson({
        tracked_id: position.id, reference,
      });
      await assert.rejects(loadManualDailyReference(position.id, csrf));
    }
    for (const broken of [
      { tracked_id: manual.id, reference: rawReference },
      { tracked_id: position.id, reference: rawReference, pnl: "5" },
      { tracked_id: position.id },
    ]) {
      globalThis.fetch = async () => okJson(broken);
      await assert.rejects(loadManualDailyReference(position.id, csrf));
    }
  } finally { globalThis.fetch = prior; }
});

test("manual reference outage cannot fall back to synthetic price", async () => {
  const prior = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 503 });
  try {
    await assert.rejects(loadManualDailyReference(position.id, csrf), /준비되지/);
  } finally { globalThis.fetch = prior; }
});

const currentQuote = {
  status: "RECEIVED", price: "251.2300",
  fetched_at: "2026-11-24T01:00:00+00:00",
  currency: "USD", source: "KIS",
  provider_time_status: "UNKNOWN", delay_status: "UNKNOWN",
  market_session: "UNKNOWN", realtime_verified: false, is_final: false,
};

test("MD05B capability is exact auth GET without price/network fallback", async () => {
  const before = globalThis.fetch;
  const seen = [];
  globalThis.fetch = async (url, opt) => {
    seen.push([url, opt]);
    return okJson({ manual_current_quote_enabled: false });
  };
  try {
    assert.equal(await loadManualCurrentCapability(), false);
    assert.equal(seen[0][0], "/api/v1/market-data/current-capabilities");
    assert.equal(seen[0][1].credentials, "same-origin");
    assert.equal(seen[0][1].cache, "no-store");
    assert.equal(seen[0][1].method, undefined);
    assert.ok(!seen[0][0].includes("kis"));
    globalThis.fetch = async () => okJson({ manual_current_quote_enabled: "true" });
    await assert.rejects(loadManualCurrentCapability(), /기능 상태/);
    globalThis.fetch = async () => okJson({
      manual_current_quote_enabled: true, token: "leak",
    });
    await assert.rejects(loadManualCurrentCapability(), /기능 상태/);
  } finally { globalThis.fetch = before; }
});

test("MD05B current price requires owner POST/CSRF and stays independent of PnL", async () => {
  const before = globalThis.fetch;
  const seen = [];
  globalThis.fetch = async (url, opt) => {
    seen.push([url, opt]);
    return okJson({ tracked_id: position.id, current_quote: currentQuote });
  };
  try {
    assert.deepEqual(await loadManualCurrentQuote(position.id, csrf), currentQuote);
    assert.equal(seen.length, 1);
    assert.equal(seen[0][0], "/api/v1/tracked/" + position.id + "/current-quote");
    assert.equal(seen[0][1].method, "POST");
    assert.equal(seen[0][1].credentials, "same-origin");
    assert.equal(seen[0][1].cache, "no-store");
    assert.equal(seen[0][1].headers["X-CSRF-Token"], csrf);
    assert.equal(position.quote.close, null);
    assert.equal(position.market_value, null);
    assert.equal(position.unrealized_pnl, null);
    assert.ok(!seen[0][0].includes("demo"));
    assert.ok(!seen[0][0].includes("kis"));
  } finally { globalThis.fetch = before; }
});

test("MD05B no CSRF never sends a request", async () => {
  const before = globalThis.fetch;
  globalThis.fetch = async () => { throw Error("should not send"); };
  try { await assert.rejects(loadManualCurrentQuote(position.id, "short"), /인증 세션/); }
  finally { globalThis.fetch = before; }
});

test("MD05B unavailable output must be strictly empty", async () => {
  const before = globalThis.fetch;
  const empty = {
    ...currentQuote, status: "UNAVAILABLE", price: null,
    fetched_at: null, source: null,
  };
  globalThis.fetch = async () => okJson({
    tracked_id: position.id, current_quote: empty,
  });
  try { assert.deepEqual(await loadManualCurrentQuote(position.id, csrf), empty); }
  finally { globalThis.fetch = before; }
});

test("MD05B cannot smuggle finality, DEMO, realtime or unverified priced states", async () => {
  const before = globalThis.fetch;
  const invalid = [
    { ...currentQuote, status: "FINAL" },
    { ...currentQuote, status: "STALE" },
    { ...currentQuote, is_final: true },
    { ...currentQuote, realtime_verified: true },
    { ...currentQuote, provider_time_status: "LIVE" },
    { ...currentQuote, delay_status: "REALTIME" },
    { ...currentQuote, market_session: "OPEN" },
    { ...currentQuote, source: "DEMO" },
    { ...currentQuote, price: 251.23 },
    { ...currentQuote, price: "-1" },
    { ...currentQuote, price: "0" },
    { ...currentQuote, price: "01" },
    { ...currentQuote, price: "NaN" },
    { ...currentQuote, price: "10000000000000000" },
    { ...currentQuote, price: "5.123456789" },
    { ...currentQuote, fetched_at: "now" },
    { ...currentQuote, quote_as_of: "2026-11-24" },
    { ...currentQuote, market_value: "100" },
    { ...currentQuote, unrealized_pnl: "5" },
    { ...currentQuote, status: "UNAVAILABLE", price: "100" },
  ];
  try {
    for (const row of invalid) {
      globalThis.fetch = async () => okJson({
        tracked_id: position.id, current_quote: row,
      });
      await assert.rejects(loadManualCurrentQuote(position.id, csrf));
    }
    for (const broken of [
      { tracked_id: manual.id, current_quote: currentQuote },
      { tracked_id: position.id, current_quote: currentQuote, extra: "secret" },
      { tracked_id: position.id },
    ]) {
      globalThis.fetch = async () => okJson(broken);
      await assert.rejects(loadManualCurrentQuote(position.id, csrf));
    }
  } finally { globalThis.fetch = before; }
});

test("MD05B current-price 401/403/503 errors never fall back to a DEMO price", async () => {
  const before = globalThis.fetch;
  try {
    for (const status of [401, 403, 503]) {
      globalThis.fetch = async () => ({ ok: false, status });
      await assert.rejects(loadManualCurrentQuote(position.id, csrf));
    }
  } finally { globalThis.fetch = before; }
});

test("MD05C valuation capability GET is owner-auth metadata, strict and no-store", async () => {
  const before = globalThis.fetch;
  const calls = [];
  try {
    globalThis.fetch = async (url, options) => {
      calls.push([url, options]);
      return okJson({ reference_valuation_enabled: true });
    };
    assert.equal(await loadValuationCapability(), true);
    assert.equal(calls[0][0], "/api/v1/market-data/valuation-capabilities");
    assert.equal(calls[0][1].method, undefined);
    assert.equal(calls[0][1].credentials, "same-origin");
    assert.equal(calls[0][1].cache, "no-store");
    for (const bad of [
      {reference_valuation_enabled:"true"},
      {reference_valuation_enabled:true, pnl:"10"},
      {manual_current_quote_enabled:true},
    ]) {
      globalThis.fetch = async () => okJson(bad);
      await assert.rejects(loadValuationCapability(), /기능 상태/);
    }
  } finally { globalThis.fetch = before; }
});
