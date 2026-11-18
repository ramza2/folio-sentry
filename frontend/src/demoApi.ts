/**
 * UI-02: strictly read-only design preview adapter.
 *
 * The endpoint returns FIXED, FICTIONAL data. Never silently fall back to
 * bundled quotes, and never treat its output as a real financial feed.
 */
export type Currency = "KRW" | "USD";
export type SignalType = "BUY_REVIEW" | "SELL_REVIEW" | "HOLD" | "RISK";
export type QuoteStatus = "DEMO" | "CURRENT" | "STALE" | "UNAVAILABLE";

export interface Instrument {
  id: string;
  market: "KR" | "US";
  exchange_mic: string;
  symbol: string;
  name: string;
  currency: Currency;
  asset_type: "STOCK" | "ETF";
}
export interface Quote {
  status: QuoteStatus;
  close: string | null;
  change_pct: string | null;
  as_of: string | null;
  source: string | null;
}
export interface TrackedInstrument {
  id: string;
  instrument: Instrument;
  kind: "HOLDING" | "WATCH";
  quantity: string | null;
  average_cost: string | null;
  quote: Quote;
  market_value: string | null;
  unrealized_pnl: string | null;
  unrealized_pnl_percent: string | null;
  alerts_enabled: boolean;
}
export interface NewsItem {
  id: string;
  instrument_id: string;
  title: string;
  publisher: string;
  published_at: string;
  url: string;
  category: "RESULT" | "REGULATION" | "INDUSTRY" | "OTHER";
}
export interface SignalItem {
  id: string;
  instrument_id: string;
  type: SignalType;
  state: "DEMO" | "FINAL" | "SUPPRESSED";
  session_date: string;
  evaluated_at: string;
  strategy_id: string;
  strategy_version: string;
  reason: string;
  evidence: Array<{
    metric: string;
    observed: string | null;
    condition: string;
    met: boolean;
  }>;
}
export interface DemoOverview {
  mode: "DEMO";
  disclaimer: string;
  as_of: string;
  summary: {
    registered_count: number;
    holding_count: number;
    watch_count: number;
    available_signal_count: number;
    valuation_by_currency: Partial<Record<Currency, string>>;
  };
  tracked: TrackedInstrument[];
  news: NewsItem[];
  signals: SignalItem[];
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const isString = (value: unknown): value is string => typeof value === "string";
const isNullableString = (value: unknown): value is string | null =>
  value === null || isString(value);
const isDecimal = (value: unknown): value is string =>
  isString(value) && /^-?\d+(?:\.\d+)?$/.test(value);
const isNullableDecimal = (value: unknown) =>
  value === null || isDecimal(value);

export function parseDemoOverview(value: unknown): DemoOverview {
  if (!isObject(value) || value.mode !== "DEMO" ||
      !isString(value.disclaimer) || !isString(value.as_of) ||
      !isObject(value.summary) || !Array.isArray(value.tracked) ||
      !Array.isArray(value.news) || !Array.isArray(value.signals)) {
    throw new Error("올바른 DEMO API 응답이 아닙니다.");
  }
  const summary = value.summary;
  if (!Number.isInteger(summary.registered_count) ||
      !Number.isInteger(summary.holding_count) ||
      !Number.isInteger(summary.watch_count) ||
      !Number.isInteger(summary.available_signal_count) ||
      !isObject(summary.valuation_by_currency)) {
    throw new Error("잘못된 포트폴리오 요약 형식입니다.");
  }
  for (const currency of Object.keys(summary.valuation_by_currency)) {
    if (!["KRW", "USD"].includes(currency) ||
        !isDecimal(summary.valuation_by_currency[currency])) {
      throw new Error("통화별 평가액 형식이 올바르지 않습니다.");
    }
  }
  for (const item of value.tracked) {
    if (!isObject(item) || !isString(item.id) ||
        !["HOLDING", "WATCH"].includes(String(item.kind)) ||
        !isObject(item.instrument) || !isObject(item.quote) ||
        !isNullableDecimal(item.quantity) ||
        !isNullableDecimal(item.average_cost) ||
        !isNullableDecimal(item.market_value) ||
        !isNullableDecimal(item.unrealized_pnl) ||
        !isNullableDecimal(item.unrealized_pnl_percent) ||
        typeof item.alerts_enabled !== "boolean") {
      throw new Error("잘못된 등록 종목 형식입니다.");
    }
    const instrument = item.instrument;
    const quote = item.quote;
    if (!isString(instrument.id) || !isString(instrument.symbol) ||
        !isString(instrument.name) || !isString(instrument.exchange_mic) ||
        !["KR", "US"].includes(String(instrument.market)) ||
        !["KRW", "USD"].includes(String(instrument.currency)) ||
        !["STOCK", "ETF"].includes(String(instrument.asset_type)) ||
        !["DEMO", "UNAVAILABLE"].includes(String(quote.status)) ||
        !isNullableDecimal(quote.close) || !isNullableDecimal(quote.change_pct) ||
        !isNullableString(quote.as_of) || !isNullableString(quote.source)) {
      throw new Error("잘못된 종목/시세 데이터입니다.");
    }
    if (item.kind === "WATCH" && (
      item.quantity !== null || item.average_cost !== null ||
      item.market_value !== null || item.unrealized_pnl !== null
    )) {
      throw new Error("관심 종목에 보유 내역이 포함되어 있습니다.");
    }
    if (quote.status === "UNAVAILABLE" && (
      quote.close !== null || quote.change_pct !== null ||
      item.market_value !== null || item.unrealized_pnl !== null ||
      item.unrealized_pnl_percent !== null
    )) {
      throw new Error("시세 없음 상태에 유효하지 않은 평가액이 있습니다.");
    }
    if (quote.status === "DEMO" && (
      quote.close === null || !isString(quote.as_of) ||
      !isString(quote.source) || quote.source.length === 0
    )) {
      throw new Error("DEMO 시세에 기준시각 또는 가격이 없습니다.");
    }
  }
  for (const item of value.news) {
    if (!isObject(item) || !isString(item.id) || !isString(item.instrument_id) ||
        !isString(item.title) || !isString(item.publisher) ||
        !isString(item.published_at) || !isString(item.url) ||
        !["RESULT", "REGULATION", "INDUSTRY", "OTHER"].includes(String(item.category))) {
      throw new Error("잘못된 뉴스 데이터입니다.");
    }
  }
  for (const item of value.signals) {
    if (!isObject(item) || !isString(item.id) || !isString(item.instrument_id) ||
        !["BUY_REVIEW", "SELL_REVIEW", "HOLD", "RISK"].includes(String(item.type)) ||
        item.state !== "DEMO" || !isString(item.evaluated_at) ||
        !isString(item.session_date) || !isString(item.reason) ||
        !isString(item.strategy_id) || !isString(item.strategy_version) ||
        !Array.isArray(item.evidence) ||
        !item.evidence.every((e: unknown) =>
          isObject(e) && isString(e.metric) && isNullableDecimal(e.observed) &&
          isString(e.condition) && typeof e.met === "boolean")) {
      throw new Error("잘못된 신호 데이터입니다.");
    }
  }
  return value as unknown as DemoOverview;
}

export async function fetchDemoOverview(signal?: AbortSignal): Promise<DemoOverview> {
  const response = await fetch("/api/v1/demo/overview", {
    method: "GET",
    cache: "no-store",
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`DEMO API 응답 오류 (HTTP ${response.status})`);
  }
  return parseDemoOverview(await response.json() as unknown);
}

const commaGroup = (digits: string) => digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
function decimalText(value: string, maxFraction = 4): string {
  const negative = value.startsWith("-");
  const absolute = negative ? value.slice(1) : value;
  const [integer, fraction] = absolute.split(".");
  const shown = fraction?.slice(0, maxFraction).replace(/0+$/, "") ?? "";
  return `${negative ? "-" : ""}${commaGroup(integer)}${shown ? "." + shown : ""}`;
}
export function formatMoney(value: string | null, currency: Currency, signed = false): string {
  if (value === null || !isDecimal(value)) return "—";
  // Preserve precision; never convert currency strings through JS floating point.
  const grouped = decimalText(value, 8);
  const amount = currency === "USD" && !grouped.includes(".") ? grouped + ".00"
    : currency === "USD" && /\.\d$/.test(grouped) ? grouped + "0" : grouped;
  const sign = signed && !value.startsWith("-") && !/^0+(?:\.0+)?$/.test(value) ? "+" : "";
  return currency === "KRW" ? `${sign}${amount}원` : `${sign}${amount}`;
}
export function formatPercent(value: string | null): string {
  if (value === null || !isDecimal(value)) return "—";
  const sign = value.startsWith("-") || /^0+(?:\.0+)?$/.test(value) ? "" : "+";
  return `${sign}${decimalText(value, 4)}%`;
}
export function formatQuantity(value: string | null): string {
  return value !== null && isDecimal(value) ? `${decimalText(value)}주` : "—";
}
export function isNegative(value: string | null): boolean {
  return typeof value === "string" && /^-/.test(value) && !/^-0+(?:\.0+)?$/.test(value);
}
export function formatDateTime(value: string | null, timezone = "Asia/Seoul"): string {
  if (!value) return "시각 없음";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "시각 없음";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(parsed);
}
export type BadgeKind = "buy" | "sell" | "watch" | "risk" | "neutral";
export function signalBadge(type: SignalType | null): {label: string; kind: BadgeKind} {
  switch (type) {
    case "BUY_REVIEW": return {label: "매수 검토", kind: "buy"};
    case "SELL_REVIEW": return {label: "매도 검토", kind: "sell"};
    case "HOLD": return {label: "관망", kind: "watch"};
    case "RISK": return {label: "위험 경고", kind: "risk"};
    default: return {label: "신호 없음", kind: "neutral"};
  }
}
export interface ViewStock {
  id: string;
  name: string;
  ticker: string;
  market: string;
  flag: "KR" | "US";
  currency: Currency;
  kind: "HOLDING" | "WATCH";
  price: string;
  change: string;
  qty: string;
  avg: string;
  pnl: string;
  pnlRate: string;
  up: boolean;
  signal: string;
  signalKind: BadgeKind;
  alertsEnabled: boolean;
  quoteStatus: QuoteStatus;
  asOf: string;
}
export function stockViews(data: DemoOverview): ViewStock[] {
  return data.tracked.map((item) => {
    const signal = data.signals.find((s) => s.instrument_id === item.instrument.id);
    const badge = signalBadge(signal?.type ?? null);
    return {
      id: item.instrument.id,
      name: item.instrument.name,
      ticker: item.instrument.symbol,
      market: item.instrument.exchange_mic,
      flag: item.instrument.market,
      currency: item.instrument.currency,
      kind: item.kind,
      price: item.quote.close === null ? "시세 없음" :
        formatMoney(item.quote.close, item.instrument.currency),
      change: formatPercent(item.quote.change_pct),
      qty: formatQuantity(item.quantity),
      avg: formatMoney(item.average_cost, item.instrument.currency),
      pnl: formatMoney(item.unrealized_pnl, item.instrument.currency, true),
      pnlRate: formatPercent(item.unrealized_pnl_percent),
      up: !isNegative(item.quote.change_pct),
      signal: badge.label,
      signalKind: badge.kind,
      alertsEnabled: item.alerts_enabled,
      quoteStatus: item.quote.status,
      asOf: formatDateTime(item.quote.as_of),
    };
  });
}
