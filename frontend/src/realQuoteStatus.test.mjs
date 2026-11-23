import test from "node:test";
import assert from "node:assert/strict";
import { hiddenQuoteLabel, parseHiddenQuote } from "./realQuoteStatus.ts";

const noPrice = {
  status: "UNAVAILABLE", close: null, change_pct: null,
  as_of: null, source: null,
};

test("all explicitly non-publishing statuses have price-free Korean labels", () => {
  const labels = {
    UNAVAILABLE: "시세 없음 · 손익 미계산",
    UNFINALIZED: "종가 미확정 · 손익 미계산",
    STALE: "오래된 시세 · 손익 미계산",
    ERROR: "시세 확인 실패 · 손익 미계산",
  };
  for (const [status, label] of Object.entries(labels)) {
    const quote = parseHiddenQuote({ ...noPrice, status });
    assert.equal(quote.status, status);
    assert.equal(quote.close, null);
    assert.equal(quote.change_pct, null);
    assert.equal(quote.as_of, null);
    assert.equal(quote.source, null);
    assert.equal(hiddenQuoteLabel(quote.status), label);
    assert.equal(Object.keys(quote).length, 5);
  }
});

test("price-bearing, promoted and demo quote shapes fail closed", () => {
  const invalid = [
    { ...noPrice, status: "CURRENT" },
    { ...noPrice, status: "VALID" },
    { ...noPrice, status: "DEMO" },
    { ...noPrice, close: "70000.00" },
    { ...noPrice, close: 70000 },
    { ...noPrice, change_pct: "1.0" },
    { ...noPrice, as_of: "2026-11-23T00:00:00Z" },
    { ...noPrice, source: "KIS" },
    { ...noPrice, price: "100" },
    { ...noPrice, is_final: true },
    { status: "UNAVAILABLE", close: null },
    null, undefined, [], "UNAVAILABLE",
  ];
  for (const candidate of invalid) {
    assert.throws(() => parseHiddenQuote(candidate));
  }
});

test("runtime quote parser strips no unknown fields and never invents fallback prices", () => {
  const parsed = parseHiddenQuote({ ...noPrice, status: "UNFINALIZED" });
  assert.deepEqual(parsed, { ...noPrice, status: "UNFINALIZED" });
  const before = JSON.stringify(parsed);
  assert.ok(!before.includes("70000"));
});
