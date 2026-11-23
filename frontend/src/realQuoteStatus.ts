/** MD-04C1: status-only real-portfolio quote boundary (no market prices). */
export type HiddenQuoteStatus = "UNAVAILABLE" | "UNFINALIZED" | "STALE" | "ERROR";

export interface HiddenQuote {
  status: HiddenQuoteStatus;
  close: null;
  change_pct: null;
  as_of: null;
  source: null;
}

const allowedKeys = new Set(["status", "close", "change_pct", "as_of", "source"]);
const statuses: readonly HiddenQuoteStatus[] = [
  "UNAVAILABLE", "UNFINALIZED", "STALE", "ERROR",
];

export function parseHiddenQuote(raw: unknown): HiddenQuote {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("실제 시세 상태 응답 형식이 올바르지 않습니다.");
  }
  const value = raw as Record<string, unknown>;
  if (Object.keys(value).length !== allowedKeys.size ||
      Object.keys(value).some((key) => !allowedKeys.has(key)) ||
      !statuses.includes(value.status as HiddenQuoteStatus) ||
      value.close !== null || value.change_pct !== null ||
      value.as_of !== null || value.source !== null) {
    // A future CURRENT/VALID or non-null price must NEVER silently display.
    throw new Error("검증되지 않은 실제 시세 응답을 차단했습니다.");
  }
  return {
    status: value.status as HiddenQuoteStatus,
    close: null, change_pct: null, as_of: null, source: null,
  };
}

const STATUS_LABELS: Record<HiddenQuoteStatus, string> = {
  UNAVAILABLE: "시세 없음 · 손익 미계산",
  UNFINALIZED: "종가 미확정 · 손익 미계산",
  STALE: "오래된 시세 · 손익 미계산",
  ERROR: "시세 확인 실패 · 손익 미계산",
};

export function hiddenQuoteLabel(status: HiddenQuoteStatus): string {
  return STATUS_LABELS[status];
}
