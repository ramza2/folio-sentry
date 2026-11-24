/** MD05C exact decimal reference valuation. Pure, no network or persistence.
 * Input scale 8, monetary products scale 16; rounding only at presentation.
 * BigInt is used as the exact decimal coefficient, never IEEE-754 money.
 */
import type { ManualCurrentQuote, RealTracked } from "./realPortfolioApi.ts";

export const RECEIPT_MAX_AGE_MS = 5 * 60 * 1000;
const FUTURE_TOLERANCE_MS = 5000;
const SCALE = 100000000n;
const MONEY_SCALE = SCALE * SCALE;
type Currency = "KRW" | "USD";
type Status = "READY" | "MISSING_COST" | "MISSING_QUANTITY" | "NO_QUOTE" |
  "STALE_RECEIPT" | "INVALID_INPUT" | "WATCH" | "DISABLED";

export interface ReferenceValuation {
  status: Status;
  currency: Currency;
  marketValue: bigint | null;
  cost: bigint | null;
  pnl: bigint | null;
  receipt: string | null;
}

function decimal8(value: unknown): bigint | null {
  if (typeof value !== "string" ||
      !/^(0|[1-9][0-9]{0,15})(?:\.[0-9]{1,8})?$/.test(value)) return null;
  const [whole, frac = ""] = value.split(".");
  return BigInt(whole) * SCALE + BigInt(frac.padEnd(8, "0"));
}

export function calculateValuation(
  item: RealTracked, quote: ManualCurrentQuote | undefined,
  nowMs: number, enabled: boolean,
): ReferenceValuation {
  const currency = item.instrument.currency;
  const empty = (status: Status): ReferenceValuation => ({
    status, currency, marketValue: null, cost: null, pnl: null, receipt: null,
  });
  if (item.kind === "WATCH") return empty("WATCH");
  if (!enabled) return empty("DISABLED");
  if (item.kind !== "HOLDING" || !["KRW", "USD"].includes(currency)) return empty("INVALID_INPUT");
  if (!quote || quote.status === "UNAVAILABLE") return empty("NO_QUOTE");
  if (quote.status !== "RECEIVED" || quote.currency !== currency ||
      quote.source !== "KIS" || quote.is_final !== false ||
      quote.realtime_verified !== false || quote.provider_time_status !== "UNKNOWN" ||
      quote.delay_status !== "UNKNOWN" || quote.market_session !== "UNKNOWN") {
    return empty("INVALID_INPUT");
  }
  if (typeof quote.fetched_at !== "string" ||
      !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(quote.fetched_at)) {
    return empty("INVALID_INPUT");
  }
  const receiptMs = Date.parse(quote.fetched_at);
  if (!Number.isFinite(receiptMs) || !Number.isFinite(nowMs)) return empty("INVALID_INPUT");
  const age = nowMs - receiptMs;
  if (age < -FUTURE_TOLERANCE_MS || age >= RECEIPT_MAX_AGE_MS) return empty("STALE_RECEIPT");
  const price = decimal8(quote.price);
  if (price === null || price <= 0n) return empty("INVALID_INPUT");
  if (item.quantity === null) return empty("MISSING_QUANTITY");
  const qty = decimal8(item.quantity);
  if (qty === null || qty <= 0n) return empty("INVALID_INPUT");
  const marketValue = qty * price;
  if (item.average_cost === null) {
    return { ...empty("MISSING_COST"), marketValue, receipt: quote.fetched_at };
  }
  const unitCost = decimal8(item.average_cost);
  if (unitCost === null) return empty("INVALID_INPUT");
  const cost = qty * unitCost;
  return { status: "READY", currency, marketValue, cost,
    pnl: marketValue - cost, receipt: quote.fetched_at };
}

/** Round half away from zero, including negative losses. */
function roundRatio(numerator: bigint, denominator: bigint): bigint {
  const absolute = numerator < 0n ? -numerator : numerator;
  const rounded = (absolute * 2n + denominator) / (denominator * 2n);
  return numerator < 0n ? -rounded : rounded;
}

function formatHundredths(value: bigint): string {
  const abs = value < 0n ? -value : value;
  const whole = (abs / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return (value < 0n ? "-" : "") + whole + "." + (abs % 100n).toString().padStart(2, "0");
}

export function formatMoney(value: bigint | null): string {
  return value === null ? "—" : formatHundredths(roundRatio(value * 100n, MONEY_SCALE));
}

export function formatReturn(pnl: bigint | null, cost: bigint | null): string {
  return pnl === null || cost === null || cost <= 0n
    ? "—" : formatHundredths(roundRatio(pnl * 10000n, cost)) + "%";
}

export interface CurrencySummary {
  currency: Currency;
  holdings: number;
  valued: number;
  withCost: number;
  marketValue: bigint | null;
  cost: bigint | null;
  pnl: bigint | null;
  oldestReceipt: string | null;
  newestReceipt: string | null;
}

/** The totals cover only loaded holdings. Never sum currencies or unknown as zero.
 * Cost and PnL use the same cost-known subset; market value may cover more.
 */
export function summarizeValuations(values: readonly ReferenceValuation[]): CurrencySummary[] {
  return (["KRW", "USD"] as const).map(currency => {
    const summary: CurrencySummary = { currency, holdings: 0, valued: 0, withCost: 0,
      marketValue: null, cost: null, pnl: null, oldestReceipt: null, newestReceipt: null };
    for (const row of values) {
      if (row.currency !== currency || row.status === "WATCH") continue;
      summary.holdings++;
      if (row.marketValue === null) continue;
      summary.valued++;
      summary.marketValue = (summary.marketValue ?? 0n) + row.marketValue;
      if (row.cost !== null && row.pnl !== null) {
        summary.withCost++;
        summary.cost = (summary.cost ?? 0n) + row.cost;
        summary.pnl = (summary.pnl ?? 0n) + row.pnl;
      }
      if (row.receipt !== null) {
        if (summary.oldestReceipt === null || Date.parse(row.receipt) < Date.parse(summary.oldestReceipt)) {
          summary.oldestReceipt = row.receipt;
        }
        if (summary.newestReceipt === null || Date.parse(row.receipt) > Date.parse(summary.newestReceipt)) {
          summary.newestReceipt = row.receipt;
        }
      }
    }
    return summary;
  });
}
