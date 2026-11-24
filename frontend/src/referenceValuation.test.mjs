import test from "node:test";
import assert from "node:assert/strict";
import {calculateValuation, summarizeValuations, formatMoney, formatReturn, RECEIPT_MAX_AGE_MS} from "./referenceValuation.ts";

const now = Date.parse("2026-11-24T01:00:00Z");
const holding = { id: "h", kind: "HOLDING", instrument: {currency: "KRW"},
  quantity: "2.12500000", average_cost: "100.25" };
const quote = {status:"RECEIVED", price:"105.25", currency:"KRW", source:"KIS",
  fetched_at: new Date(now).toISOString(), provider_time_status:"UNKNOWN", delay_status:"UNKNOWN",
  market_session:"UNKNOWN", realtime_verified:false, is_final:false};
const calc = (item = holding, q = quote, time = now, enabled = true) =>
  calculateValuation(item, q, time, enabled);

test("exact fractional holdings and weighted return", () => {
  const v = calc();
  assert.equal(v.status, "READY");
  assert.equal(formatMoney(v.marketValue), "223.66");
  assert.equal(formatMoney(v.cost), "213.03");
  assert.equal(formatMoney(v.pnl), "10.63");
  assert.equal(formatReturn(v.pnl, v.cost), "4.99%");
});
test("negative half-cent rounds away from zero", () => {
  const v = calc({...holding, quantity:"0.5", average_cost:"1.01"}, {...quote, price:"1"});
  assert.equal(formatMoney(v.pnl), "-0.01");
  assert.equal(formatReturn(v.pnl,v.cost), "-0.99%");
});
test("zero cost permits value and gain, but not return", () => {
  const v = calc({...holding, average_cost:"0"});
  assert.equal(v.pnl, v.marketValue);
  assert.equal(formatReturn(v.pnl, v.cost), "—");
});
test("missing cost preserves market value without fabricating PnL", () => {
  const v = calc({...holding, average_cost:null});
  assert.equal(v.status,"MISSING_COST");
  assert.ok(v.marketValue > 0n);
  assert.equal(v.cost,null);
  assert.equal(v.pnl,null);
});
test("watch, disabled, missing quantity and unavailable quotes are excluded", () => {
  for (const [v, status] of [
    [calc({...holding, kind:"WATCH"}), "WATCH"],
    [calc(holding,quote,now,false), "DISABLED"],
    [calc({...holding,quantity:null}), "MISSING_QUANTITY"],
    [calc(holding,{...quote,status:"UNAVAILABLE",price:null}), "NO_QUOTE"],
    [calculateValuation(holding,undefined,now,true), "NO_QUOTE"],
  ]) {
    assert.equal(v.status,status);
    assert.equal(v.marketValue,null);
    assert.equal(v.pnl,null);
  }
});
test("receipt age is not provider timestamp; expires at five minutes", () => {
  assert.equal(calc(holding,quote,now+RECEIPT_MAX_AGE_MS-1).status,"READY");
  for(const t of [now+RECEIPT_MAX_AGE_MS,now-5001]) {
    const v=calc(holding,quote,t);
    assert.equal(v.status,"STALE_RECEIPT");
    assert.equal(v.marketValue,null);
  }
});
test("reject forged source, realtime claims, wrong currency, prices and timestamps", () => {
  for(const patch of [
    {source:"DEMO"}, {currency:"USD"}, {is_final:true}, {realtime_verified:true},
    {delay_status:"LIVE"}, {market_session:"OPEN"}, {provider_time_status:"VERIFIED"},
    {status:"REFERENCE"}, {price:"0"}, {price:"-1"}, {price:1}, {price:"1e3"},
    {price:"1.123456789"}, {price:"99999999999999999"}, {price:"NaN"},
    {fetched_at:"bad"}, {fetched_at:"2026-11-24T01:00:00"}
  ]) {
    const v=calc(holding,{...quote,...patch});
    assert.equal(v.status,"INVALID_INPUT");
    assert.equal(v.marketValue,null);
  }
  for(const patch of [{quantity:"0"},{quantity:"-1"},{quantity:"1e3"},
    {quantity:1},{average_cost:"-2"},{average_cost:"1.123456789"}]) {
    assert.equal(calc({...holding,...patch}).status,"INVALID_INPUT");
  }
});
test("large and fractional decimal coefficients retain exact precision", () => {
  const v = calc({...holding, quantity:"9999999999999999.99999999", average_cost:"0"},
    {...quote, price:"9999999999999999.99999999"});
  assert.equal(v.marketValue, 999999999999999999999999n ** 2n);
  assert.equal(v.pnl,v.marketValue);
  const small=calc({...holding,quantity:"0.00000001",average_cost:"0.00000001"},{...quote,price:"0.00000002"});
  assert.equal(small.pnl,1n);
});
test("currency totals exclude watches and missing quotes, preserve subset coverage", () => {
  const a=calc({...holding,quantity:"2",average_cost:"100"},{...quote,price:"105"});
  const b=calc({...holding,quantity:"1",average_cost:null},{...quote,price:"300"});
  const c=calc({...holding,instrument:{currency:"USD"},quantity:"1",average_cost:"10"},
    {...quote,currency:"USD",price:"11",fetched_at:new Date(now-1000).toISOString()});
  const no=calculateValuation(holding,undefined,now,true);
  const watch=calc({...holding,kind:"WATCH"});
  const [kr,us]=summarizeValuations([a,b,c,no,watch]);
  assert.equal(kr.holdings,3);
  assert.equal(kr.valued,2);
  assert.equal(kr.withCost,1);
  assert.equal(formatMoney(kr.marketValue),"510.00");
  assert.equal(formatMoney(kr.cost),"200.00");
  assert.equal(formatMoney(kr.pnl),"10.00");
  assert.equal(formatReturn(kr.pnl,kr.cost),"5.00%");
  assert.equal(us.holdings,1);
  assert.equal(formatMoney(us.marketValue),"11.00");
  assert.equal(formatMoney(us.pnl),"1.00");
  assert.equal(us.oldestReceipt,c.receipt);
});
test("no values are null not zero and aggregate rounds once", () => {
  const empty=summarizeValuations([]);
  assert.equal(empty[0].marketValue,null);
  assert.equal(empty[1].pnl,null);
  const a=calc({...holding,quantity:"0.5",average_cost:"0"},{...quote,price:"0.01"});
  const b=calc({...holding,quantity:"0.5",average_cost:"0"},{...quote,price:"0.01"});
  assert.equal(formatMoney(summarizeValuations([a,b])[0].marketValue),"0.01");
});
