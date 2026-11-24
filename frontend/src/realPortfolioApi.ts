/** Live single-owner portfolio adapter (never reads /demo endpoints). */
import { parseHiddenQuote, type HiddenQuote } from "./realQuoteStatus.ts";

export type Market = "KR" | "US";
export type TrackedKind = "HOLDING" | "WATCH";
export type AssetType = "STOCK" | "ETF";
export interface RealInstrument {
  id: string;
  market: Market;
  exchange_mic: string;
  symbol: string;
  name: string;
  currency: "KRW" | "USD";
  asset_type: AssetType;
  source: "MANUAL_UNVERIFIED";
}
export interface RealTracked {
  id: string;
  instrument: RealInstrument;
  kind: TrackedKind;
  quantity: string | null;
  average_cost: string | null;
  alerts_enabled: boolean;
  memo: string | null;
  quote: HiddenQuote;
  market_value: null;
  unrealized_pnl: null;
  unrealized_pnl_percent: null;
}
export interface Paginated<T> {
  items: T[];
  next_cursor: string | null;
}
/** Separate, owner-triggered KIS historical reference. Never changes RealTracked.quote. */
export interface ManualDailyReference {
  status: "REFERENCE" | "STALE" | "UNAVAILABLE";
  close: string | null;
  session_date: string | null;
  fetched_at: string | null;
  source: "KIS" | null;
  price_basis: "RAW" | null;
  currency: "KRW" | "USD";
  is_final: false;
}

/** KIS's last reported REST price, NOT a verified realtime tick. */
export interface ManualCurrentQuote {
  status: "RECEIVED" | "UNAVAILABLE";
  price: string | null;
  fetched_at: string | null;
  currency: "KRW" | "USD";
  source: "KIS" | null;
  provider_time_status: "UNKNOWN";
  delay_status: "UNKNOWN";
  market_session: "UNKNOWN";
  realtime_verified: false;
  is_final: false;
}

export type ManualInstrumentInput = Pick<
  RealInstrument, "market" | "exchange_mic" | "symbol" | "name" | "asset_type"
>;
export interface TrackInput {
  instrument_id: string;
  kind: TrackedKind;
  quantity: string | null;
  average_cost: string | null;
  alerts_enabled: boolean;
  memo: string | null;
}
export type TrackPatch = Partial<Omit<TrackInput, "instrument_id">>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function isNullableDecimal(value: unknown): value is string | null {
  return value === null || (typeof value === "string" && /^(0|[1-9]\d{0,15})(?:\.\d{1,8})?$/.test(value));
}
function parseInstrument(raw: unknown): RealInstrument {
  if (!isRecord(raw) || typeof raw.id !== "string" ||
      !["KR", "US"].includes(String(raw.market)) ||
      typeof raw.exchange_mic !== "string" || typeof raw.symbol !== "string" ||
      typeof raw.name !== "string" ||
      !["KRW", "USD"].includes(String(raw.currency)) ||
      !["STOCK", "ETF"].includes(String(raw.asset_type)) ||
      raw.source !== "MANUAL_UNVERIFIED") {
    throw new Error("실제 종목 응답 형식이 올바르지 않습니다.");
  }
  return raw as unknown as RealInstrument;
}
function parseTracked(raw: unknown): RealTracked {
  if (!isRecord(raw) || typeof raw.id !== "string" ||
      !["HOLDING", "WATCH"].includes(String(raw.kind)) ||
      !isNullableDecimal(raw.quantity) || !isNullableDecimal(raw.average_cost) ||
      typeof raw.alerts_enabled !== "boolean" ||
      !(raw.memo === null || typeof raw.memo === "string") ||
      raw.market_value !== null || raw.unrealized_pnl !== null ||
      raw.unrealized_pnl_percent !== null) {
    throw new Error("실제 등록 종목 응답 형식이 올바르지 않습니다.");
  }
  const instrument = parseInstrument(raw.instrument);
  const quote = parseHiddenQuote(raw.quote);
  if (raw.kind === "WATCH" && (raw.quantity !== null || raw.average_cost !== null)) {
    throw new Error("관심 종목 데이터에 보유 수량이 포함되어 있습니다.");
  }
  return { ...raw, instrument, quote } as RealTracked;
}
function parsePage<T>(value: unknown, parseItem: (value: unknown) => T): Paginated<T> {
  if (!isRecord(value) || !Array.isArray(value.items) ||
      !(value.next_cursor === null || typeof value.next_cursor === "string")) {
    throw new Error("실제 종목 목록 응답 형식이 올바르지 않습니다.");
  }
  return { items: value.items.map(parseItem), next_cursor: value.next_cursor as string | null };
}
function requestError(status: number): Error {
  if (status === 401) return new Error("세션이 만료됐습니다. 다시 로그인하세요.");
  if (status === 403) return new Error("요청 인증이 거부됐습니다. 페이지를 새로고침하세요.");
  if (status === 404) return new Error("선택한 종목을 찾을 수 없습니다. 목록을 새로고침하세요.");
  if (status === 409) return new Error("이미 등록된 종목입니다. 기존 목록에서 선택하세요.");
  if (status === 422) return new Error("종목 정보·보유 수량·평균단가를 확인하세요.");
  if (status === 503) return new Error("실제 종목 저장소가 아직 준비되지 않았습니다. 운영 마이그레이션 상태를 확인하세요.");
  return new Error("실제 종목 요청에 실패했습니다 (HTTP " + status + ").");
}

async function apiRequest(
  path: string, options: RequestInit = {},
): Promise<unknown> {
  const response = await fetch("/api/v1/" + path, {
    credentials: "same-origin", cache: "no-store",
    ...options,
    headers: { Accept: "application/json", ...options.headers },
  });
  if (!response.ok) throw requestError(response.status);
  if (response.status === 204) return null;
  return await response.json() as unknown;
}

function mutation(method: "POST" | "PATCH" | "DELETE", path: string,
  csrf: string, data?: object): Promise<unknown> {
  if (!csrf || csrf.length < 32) throw new Error("유효한 인증 세션이 필요합니다.");
  return apiRequest(path, {
    method,
    headers: {
      "X-CSRF-Token": csrf,
      ...(data ? { "Content-Type": "application/json" } : {}),
    },
    ...(data ? { body: JSON.stringify(data) } : {}),
  });
}

export async function loadInstruments(
  q = "", cursor: string | null = null, signal?: AbortSignal,
): Promise<Paginated<RealInstrument>> {
  const params = new URLSearchParams({ limit: "100" });
  if (q.trim()) params.set("q", q.trim());
  if (cursor) params.set("cursor", cursor);
  return parsePage(await apiRequest("instruments?" + params.toString(), { signal }), parseInstrument);
}

export async function loadTracked(cursor: string | null = null, signal?: AbortSignal):
  Promise<Paginated<RealTracked>> {
  const params = new URLSearchParams({ limit: "100" });
  if (cursor) params.set("cursor", cursor);
  return parsePage(await apiRequest("tracked?" + params.toString(), { signal }), parseTracked);
}

/** Explicit owner-only metadata GET. Never fetches prices, DEMO or triggers KIS. */
export async function loadTrackedQuoteStatus(
  trackedId: string, signal?: AbortSignal,
): Promise<HiddenQuote> {
  const value = await apiRequest(
    "tracked/" + encodeURIComponent(trackedId) + "/quote-status", { signal },
  );
  if (!isRecord(value) ||
      Object.keys(value).length !== 2 ||
      !Object.hasOwn(value, "tracked_id") ||
      !Object.hasOwn(value, "quote") ||
      value.tracked_id !== trackedId) {
    throw new Error("실제 종목 시세 상태의 식별자가 올바르지 않습니다.");
  }
  return parseHiddenQuote(value.quote);
}

export async function addInstrument(data: ManualInstrumentInput, csrf: string):
  Promise<RealInstrument> {
  return parseInstrument(await mutation("POST", "instruments", csrf, data));
}
export async function addTracked(data: TrackInput, csrf: string): Promise<RealTracked> {
  return parseTracked(await mutation("POST", "tracked", csrf, data));
}
export async function editTracked(id: string, data: TrackPatch, csrf: string):
  Promise<RealTracked> {
  return parseTracked(await mutation("PATCH", "tracked/" + encodeURIComponent(id), csrf, data));
}
export async function removeTracked(id: string, csrf: string): Promise<void> {
  await mutation("DELETE", "tracked/" + encodeURIComponent(id), csrf);
}

/** No provider request; capability only. A missing backend feature must not activate UI. */
export async function loadManualReferenceCapability(
  signal?: AbortSignal,
): Promise<boolean> {
  const raw = await apiRequest("market-data/capabilities", { signal });
  if (!isRecord(raw) ||
      Object.keys(raw).length !== 1 ||
      typeof raw.manual_daily_reference_enabled !== "boolean") {
    throw new Error("KIS 참고 시세 기능 상태를 확인할 수 없습니다.");
  }
  return raw.manual_daily_reference_enabled;
}

const referenceKeys = new Set([
  "status", "close", "session_date", "fetched_at",
  "source", "price_basis", "currency", "is_final",
]);

function parseManualDailyReference(raw: unknown): ManualDailyReference {
  if (!isRecord(raw) ||
      Object.keys(raw).length !== referenceKeys.size ||
      Object.keys(raw).some(key => !referenceKeys.has(key)) ||
      !["REFERENCE", "STALE", "UNAVAILABLE"].includes(String(raw.status)) ||
      !["KRW", "USD"].includes(String(raw.currency)) ||
      raw.is_final !== false) {
    throw new Error("참고 일봉 응답 형식이 올바르지 않습니다.");
  }
  if (raw.status === "UNAVAILABLE") {
    if (raw.close !== null || raw.session_date !== null ||
        raw.fetched_at !== null || raw.source !== null ||
        raw.price_basis !== null) {
      throw new Error("참고 일봉의 비정상 가격 응답을 차단했습니다.");
    }
  } else {
    if (raw.source !== "KIS" || raw.price_basis !== "RAW" ||
        typeof raw.session_date !== "string" ||
        !/^\d{4}-\d{2}-\d{2}$/.test(raw.session_date) ||
        typeof raw.fetched_at !== "string" ||
        !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(raw.fetched_at) ||
        !Number.isFinite(Date.parse(raw.fetched_at))) {
      throw new Error("참고 일봉의 기준일·조회시각이 올바르지 않습니다.");
    }
    if (raw.status === "STALE") {
      if (raw.close !== null) {
        throw new Error("오래된 참고 시세의 가격 노출을 차단했습니다.");
      }
    } else if (typeof raw.close !== "string" ||
               !/^(0|[1-9]\d{0,15})(?:\.\d{1,8})?$/.test(raw.close) ||
               /^0(?:\.0+)?$/.test(raw.close)) {
      throw new Error("참고 시세의 가격 형식이 올바르지 않습니다.");
    }
  }
  return raw as unknown as ManualDailyReference;
}

/** Explicit POST + CSRF. One manual KIS attempt; no automatic polling or caching. */
export async function loadManualDailyReference(
  trackedId: string, csrf: string,
): Promise<ManualDailyReference> {
  if (!csrf || csrf.length < 32) throw new Error("유효한 인증 세션이 필요합니다.");
  const raw = await apiRequest(
    "tracked/" + encodeURIComponent(trackedId) + "/daily-reference",
    { method: "POST", headers: { "X-CSRF-Token": csrf } },
  );
  if (!isRecord(raw) ||
      Object.keys(raw).length !== 2 ||
      raw.tracked_id !== trackedId ||
      !Object.hasOwn(raw, "reference")) {
    throw new Error("참고 일봉 응답의 등록 종목 ID가 일치하지 않습니다.");
  }
  return parseManualDailyReference(raw.reference);
}

/** Capability only; no KIS request, no silent fallback to enabled. */
export async function loadManualCurrentCapability(
  signal?: AbortSignal,
): Promise<boolean> {
  const raw = await apiRequest("market-data/current-capabilities", { signal });
  if (!isRecord(raw) || Object.keys(raw).length !== 1 ||
      typeof raw.manual_current_quote_enabled !== "boolean") {
    throw new Error("KIS 현재가 조회 기능 상태를 확인할 수 없습니다.");
  }
  return raw.manual_current_quote_enabled;
}

const currentKeys = new Set([
  "status", "price", "fetched_at", "currency", "source",
  "provider_time_status", "delay_status", "market_session",
  "realtime_verified", "is_final",
]);

function parseManualCurrentQuote(raw: unknown): ManualCurrentQuote {
  if (!isRecord(raw) ||
      Object.keys(raw).length !== currentKeys.size ||
      Object.keys(raw).some((key) => !currentKeys.has(key)) ||
      !["RECEIVED", "UNAVAILABLE"].includes(String(raw.status)) ||
      !["KRW", "USD"].includes(String(raw.currency)) ||
      raw.provider_time_status !== "UNKNOWN" ||
      raw.delay_status !== "UNKNOWN" ||
      raw.market_session !== "UNKNOWN" ||
      raw.realtime_verified !== false ||
      raw.is_final !== false) {
    throw new Error("현재가 응답 형식이 올바르지 않습니다.");
  }
  if (raw.status === "UNAVAILABLE") {
    if (raw.price !== null || raw.fetched_at !== null || raw.source !== null) {
      throw new Error("조회 불가 현재가의 잘못된 가격을 차단했습니다.");
    }
  } else {
    if (raw.source !== "KIS" ||
        typeof raw.price !== "string" ||
        !/^(0|[1-9]\d{0,15})(?:\.\d{1,8})?$/.test(raw.price) ||
        /^0(?:\.0+)?$/.test(raw.price) ||
        typeof raw.fetched_at !== "string" ||
        !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(raw.fetched_at) ||
        !Number.isFinite(Date.parse(raw.fetched_at))) {
      throw new Error("KIS 현재가나 수신 시각이 올바르지 않습니다.");
    }
  }
  return raw as unknown as ManualCurrentQuote;
}

/** Owner-only POST/CSRF: an intentional KIS current-price read, no auto refresh. */
export async function loadManualCurrentQuote(
  trackedId: string, csrf: string,
): Promise<ManualCurrentQuote> {
  if (!csrf || csrf.length < 32) {
    throw new Error("유효한 인증 세션이 필요합니다.");
  }
  const raw = await apiRequest(
    "tracked/" + encodeURIComponent(trackedId) + "/current-quote",
    { method: "POST", headers: { "X-CSRF-Token": csrf } },
  );
  if (!isRecord(raw) ||
      Object.keys(raw).length !== 2 ||
      raw.tracked_id !== trackedId ||
      !Object.hasOwn(raw, "current_quote")) {
    throw new Error("현재가 조회 종목 ID가 일치하지 않습니다.");
  }
  return parseManualCurrentQuote(raw.current_quote);
}

/** Owner-authenticated metadata only; no KIS access or calculated data. */
export async function loadValuationCapability(signal?: AbortSignal): Promise<boolean> {
  const raw = await apiRequest("market-data/valuation-capabilities", { signal });
  if (!isRecord(raw) || Object.keys(raw).length !== 1 ||
      typeof raw.reference_valuation_enabled !== "boolean") {
    throw new Error("평가손익 기능 상태를 확인할 수 없습니다.");
  }
  return raw.reference_valuation_enabled;
}

export type ReferenceHistoryDays = 30 | 90;
export interface ReferenceHistoryBar {
  session_date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
  fetched_at: string;
  is_final: false;
}
export interface ReferenceHistory {
  tracked_id: string;
  currency: "KRW" | "USD";
  source: "KIS";
  price_basis: "RAW";
  quality_status: "PARTIAL";
  status: "STORED_REFERENCE" | "EMPTY";
  days: ReferenceHistoryDays;
  start_date: string;
  end_date: string;
  stored_rows: number;
  latest_session_date: string | null;
  latest_receipt: string | null;
  bars: ReferenceHistoryBar[];
}

function validDate(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
    && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString().slice(0, 10) === value;
}
function validReceipt(value: unknown): value is string {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value)
    && Number.isFinite(Date.parse(value));
}
export function priceUnits(value: string): bigint {
  const [whole, fraction = ""] = value.split(".");
  return BigInt(whole) * 100000000n + BigInt(fraction.padEnd(8, "0"));
}
function validPrice(value: unknown): value is string {
  return typeof value === "string" && /^(0|[1-9]\d{0,15})(?:\.\d{1,8})?$/.test(value)
    && priceUnits(value) > 0n;
}

export function parseReferenceHistory(raw: unknown, trackedId: string,
  currency: "KRW" | "USD", days: ReferenceHistoryDays): ReferenceHistory {
  const fail = () => { throw new Error("저장된 참고 일봉 응답이 올바르지 않습니다."); };
  const keys = ["tracked_id", "currency", "source", "price_basis", "quality_status",
    "status", "days", "start_date", "end_date", "stored_rows", "latest_session_date",
    "latest_receipt", "bars"];
  if (!isRecord(raw) || Object.keys(raw).length !== keys.length ||
      keys.some(key => !Object.hasOwn(raw, key)) ||
      raw.tracked_id !== trackedId || raw.currency !== currency ||
      raw.source !== "KIS" || raw.price_basis !== "RAW" || raw.quality_status !== "PARTIAL" ||
      raw.days !== days || !validDate(raw.start_date) || !validDate(raw.end_date) ||
      (Date.parse(raw.end_date) - Date.parse(raw.start_date)) / 86400000 !== days - 1 ||
      !Array.isArray(raw.bars) || raw.bars.length > days ||
      raw.stored_rows !== raw.bars.length ||
      raw.status !== (raw.bars.length ? "STORED_REFERENCE" : "EMPTY")) {
    return fail() as never;
  }
  let prior = "";
  let latestReceipt = -Infinity;
  for (const bar of raw.bars) {
    if (!isRecord(bar) || Object.keys(bar).length !== 8 ||
        !validDate(bar.session_date) || bar.session_date < raw.start_date ||
        bar.session_date > raw.end_date || bar.session_date <= prior ||
        bar.is_final !== false || !validReceipt(bar.fetched_at) ||
        !validPrice(bar.open) || !validPrice(bar.high) || !validPrice(bar.low) ||
        !validPrice(bar.close) || typeof bar.volume !== "string" ||
        !/^(0|[1-9]\d{0,27})$/.test(bar.volume)) return fail() as never;
    const o = priceUnits(bar.open), h = priceUnits(bar.high);
    const l = priceUnits(bar.low), c = priceUnits(bar.close);
    if (l > o || l > c || h < o || h < c || l > h) return fail() as never;
    prior = bar.session_date;
    latestReceipt = Math.max(latestReceipt, Date.parse(bar.fetched_at));
  }
  if (raw.bars.length) {
    if (raw.latest_session_date !== prior || !validReceipt(raw.latest_receipt) ||
        Date.parse(raw.latest_receipt) !== latestReceipt) return fail() as never;
  } else if (raw.latest_session_date !== null || raw.latest_receipt !== null) {
    return fail() as never;
  }
  return raw as unknown as ReferenceHistory;
}

export async function loadReferenceHistoryCapability(signal?: AbortSignal): Promise<boolean> {
  const raw = await apiRequest("market-data/history-capabilities", { signal });
  if (!isRecord(raw) || Object.keys(raw).length !== 1 ||
      typeof raw.reference_history_enabled !== "boolean") {
    throw new Error("참고 차트 기능 상태를 확인할 수 없습니다.");
  }
  return raw.reference_history_enabled;
}

/** DB-only GET. No provider request or storage mutation. */
export async function loadReferenceHistory(trackedId: string, currency: "KRW" | "USD",
  days: ReferenceHistoryDays, signal?: AbortSignal): Promise<ReferenceHistory> {
  const raw = await apiRequest("tracked/" + encodeURIComponent(trackedId) +
    "/reference-history?days=" + days, { signal });
  return parseReferenceHistory(raw, trackedId, currency, days);
}
