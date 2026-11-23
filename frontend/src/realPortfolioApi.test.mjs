import test from "node:test";
import assert from "node:assert/strict";
import {
  loadInstruments, loadTracked, addInstrument, addTracked, editTracked, removeTracked,
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
