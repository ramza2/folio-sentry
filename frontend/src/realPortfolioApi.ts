/** Live single-owner portfolio adapter (never reads /demo endpoints). */

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
  quote: {
    status: "UNAVAILABLE";
    close: null;
    change_pct: null;
    as_of: null;
    source: null;
  };
  market_value: null;
  unrealized_pnl: null;
  unrealized_pnl_percent: null;
}
export interface Paginated<T> {
  items: T[];
  next_cursor: string | null;
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
      !isRecord(raw.quote) ||
      raw.quote.status !== "UNAVAILABLE" ||
      raw.quote.close !== null || raw.quote.change_pct !== null ||
      raw.quote.as_of !== null || raw.quote.source !== null ||
      raw.market_value !== null || raw.unrealized_pnl !== null ||
      raw.unrealized_pnl_percent !== null) {
    throw new Error("실제 등록 종목 응답 형식이 올바르지 않습니다.");
  }
  const instrument = parseInstrument(raw.instrument);
  if (raw.kind === "WATCH" && (raw.quantity !== null || raw.average_cost !== null)) {
    throw new Error("관심 종목 데이터에 보유 수량이 포함되어 있습니다.");
  }
  return { ...raw, instrument } as RealTracked;
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
