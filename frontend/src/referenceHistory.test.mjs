import test from "node:test";
import assert from "node:assert/strict";
import { loadReferenceHistory, loadReferenceHistoryCapability, parseReferenceHistory, priceUnits } from "./realPortfolioApi.ts";

const id = "22222222-2222-4222-8222-222222222222";
const bar = { session_date: "2026-11-23", open:"100.00000000", high:"112.00000000",
  low:"90.00000000", close:"105.00000000", volume:"123456",
  fetched_at:"2026-11-24T00:00:00Z", is_final:false };
const data = { tracked_id:id, currency:"KRW", source:"KIS", price_basis:"RAW",
  quality_status:"PARTIAL", status:"STORED_REFERENCE", days:30,
  start_date:"2026-10-25", end_date:"2026-11-23", stored_rows:1,
  latest_session_date:bar.session_date, latest_receipt:bar.fetched_at, bars:[bar] };

test("protected history GET only, no KIS calls", async () => {
  const old = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push(url);
    assert.equal(options.credentials,"same-origin");
    assert.equal(options.cache,"no-store");
    assert.ok(!options.method || options.method === "GET");
    return {ok:true,status:200,json:async()=>url.endsWith("history-capabilities")
      ? {reference_history_enabled:true}:data};
  };
  try {
    assert.equal(await loadReferenceHistoryCapability(),true);
    assert.deepEqual(await loadReferenceHistory(id,"KRW",30),data);
    assert.deepEqual(calls,["/api/v1/market-data/history-capabilities",
      "/api/v1/tracked/"+id+"/reference-history?days=30"]);
  } finally {globalThis.fetch=old;}
});

test("empty stored history does not invent prices", () => {
  const empty = {...data,status:"EMPTY",stored_rows:0,bars:[],latest_session_date:null,latest_receipt:null};
  assert.deepEqual(parseReferenceHistory(empty,id,"KRW",30).bars,[]);
});

test("invalid finality, currency, date, OHLC, volume, duplicates and counts rejected", () => {
  for (const value of [
    {...data, currency:"USD"}, {...data, source:"DEMO"}, {...data, stored_rows:2},
    {...data, latest_receipt:"2026-11-25T00:00:00Z"},
    {...data, bars:[{...bar,is_final:true}]},
    {...data, bars:[{...bar,low:"111"}]},
    {...data, bars:[{...bar,session_date:"2026-11-31"}]},
    {...data, bars:[{...bar,volume:"-1"}]},
    {...data, bars:[bar,bar],stored_rows:2},
  ]) assert.throws(()=>parseReferenceHistory(value,id,"KRW",30),/올바르지/);
});

test("large prices retain differences at fixed precision", () => {
  assert.equal(priceUnits("9999999999999999.00000001")-priceUnits("9999999999999999.00000000"),1n);
});
