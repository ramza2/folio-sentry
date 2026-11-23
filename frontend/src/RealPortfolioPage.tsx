import { useEffect, useState, type FormEvent } from "react";
import { useOwnerAuth } from "./AuthGate";
import { hiddenQuoteLabel } from "./realQuoteStatus";
import {
  addInstrument, addTracked, editTracked, loadInstruments, loadTracked,
  loadTrackedQuoteStatus, loadManualReferenceCapability,
  loadManualDailyReference, removeTracked,
  type AssetType, type ManualInstrumentInput, type Market,
  type RealInstrument, type RealTracked, type TrackedKind,
  type ManualDailyReference,
} from "./realPortfolioApi";

const NEW_MANUAL: ManualInstrumentInput = {
  market: "KR", exchange_mic: "XKRX", symbol: "", name: "", asset_type: "STOCK",
};
const EXCHANGES: Record<Market, { code: string; name: string }[]> = {
  KR: [{ code: "XKRX", name: "한국거래소(XKRX)" }, { code: "XKOS", name: "코스닥(XKOS)" }],
  US: [{ code: "XNAS", name: "NASDAQ(XNAS)" }, { code: "XNYS", name: "NYSE(XNYS)" },
       { code: "XASE", name: "NYSE American(XASE)" }],
};
type PositionForm = {
  kind: TrackedKind;
  quantity: string;
  average_cost: string;
  memo: string;
  alerts_enabled: boolean;
};
const EMPTY_POSITION: PositionForm = {
  kind: "WATCH", quantity: "", average_cost: "",
  memo: "", alerts_enabled: false,
};
type ViewFilter = "ALL" | TrackedKind;

function PositionFields({ value, update, disabled }: {
  value: PositionForm;
  update: (changes: Partial<PositionForm>) => void;
  disabled: boolean;
}) {
  return (
    <div className="real-form-grid">
      <label>
        분류
        <select value={value.kind} disabled={disabled}
          onChange={(e) => {
            const kind = e.target.value as TrackedKind;
            update(kind === "WATCH"
              ? { kind, quantity: "", average_cost: "" } : { kind });
          }}>
          <option value="WATCH">관심 종목</option>
          <option value="HOLDING">보유 종목</option>
        </select>
      </label>
      {value.kind === "HOLDING" && (
        <>
          <label>
            보유 수량 (선택)
            <input type="text" inputMode="decimal" autoComplete="off"
              disabled={disabled} value={value.quantity}
              placeholder="예: 3.125"
              onChange={(e) => update({ quantity: e.target.value })} />
          </label>
          <label>
            평균 매입 단가 (선택 · 종목 통화)
            <input type="text" inputMode="decimal" autoComplete="off"
              disabled={disabled} value={value.average_cost}
              placeholder="예: 75000.50"
              onChange={(e) => update({ average_cost: e.target.value })} />
          </label>
        </>
      )}
      <label>
        메모 (선택)
        <input type="text" maxLength={1000} disabled={disabled}
          value={value.memo} onChange={(e) => update({ memo: e.target.value })} />
      </label>
      <label className="real-checkbox">
        <input type="checkbox" checked={value.alerts_enabled} disabled={disabled}
          onChange={(e) => update({ alerts_enabled: e.target.checked })} />
        향후 알림 사용 희망 (발송 기능 미구현)
      </label>
    </div>
  );
}

function mapPosition(position: PositionForm) {
  return {
    kind: position.kind,
    quantity: position.kind === "HOLDING" && position.quantity.trim()
      ? position.quantity.trim() : null,
    average_cost: position.kind === "HOLDING" && position.average_cost.trim()
      ? position.average_cost.trim() : null,
    memo: position.memo.trim() || null,
    alerts_enabled: position.alerts_enabled,
  };
}

function formatPosition(item: RealTracked): string {
  if (item.kind === "WATCH") return "—";
  if (!item.quantity) return "미입력";
  const trimmed = item.quantity.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
  return trimmed;
}

export default function RealPortfolioPage() {
  const { csrfToken } = useOwnerAuth();
  const [rows, setRows] = useState<RealTracked[]>([]);
  const [nextRows, setNextRows] = useState<string | null>(null);
  const [instruments, setInstruments] = useState<RealInstrument[]>([]);
  const [nextInstruments, setNextInstruments] = useState<string | null>(null);
  const [filter, setFilter] = useState<ViewFilter>("ALL");
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<"manual" | "existing">("manual");
  const [manual, setManual] = useState<ManualInstrumentInput>({ ...NEW_MANUAL });
  const [selected, setSelected] = useState("");
  const [position, setPosition] = useState<PositionForm>({ ...EMPTY_POSITION });
  const [editing, setEditing] = useState<string | null>(null);
  const [editPosition, setEditPosition] = useState<PositionForm>({ ...EMPTY_POSITION });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [referenceEnabled, setReferenceEnabled] = useState(false);
  // Reference prices are transient and never mixed into the persisted
  // RealTracked.quote (which remains UNAVAILABLE and price-free).
  const [referenceById, setReferenceById] = useState<Record<string, ManualDailyReference>>({});

  useEffect(() => {
    const controller = new AbortController();
    void loadManualReferenceCapability(controller.signal)
      .then((enabled) => { if (!controller.signal.aborted) setReferenceEnabled(enabled); })
      .catch(() => { if (!controller.signal.aborted) setReferenceEnabled(false); });
    Promise.all([loadTracked(null, controller.signal), loadInstruments("", null, controller.signal)])
      .then(([tracked, catalog]) => {
        if (controller.signal.aborted) return;
        setRows(tracked.items);
        setNextRows(tracked.next_cursor);
        setInstruments(catalog.items);
        setNextInstruments(catalog.next_cursor);
      }).catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setRows([]);
        setInstruments([]);
        setError(reason instanceof Error ? reason.message : "실제 종목 데이터를 불러올 수 없습니다.");
      }).finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const refreshRows = async () => {
    const data = await loadTracked();
    setReferenceById({});
    setRows(data.items);
    setNextRows(data.next_cursor);
  };
  const refreshCatalog = async (q = "") => {
    const data = await loadInstruments(q);
    setInstruments(data.items);
    setNextInstruments(data.next_cursor);
    setSelected("");
  };
  const execute = async (task: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try { await task(); }
    catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "요청에 실패했습니다.");
    } finally { setBusy(false); }
  };

  const register = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void execute(async () => {
      let id = selected;
      if (mode === "manual") {
        const created = await addInstrument({
          ...manual, name: manual.name.trim(), symbol: manual.symbol.trim().toUpperCase(),
        }, csrfToken);
        id = created.id;
      }
      if (!id) throw new Error("등록할 종목을 선택하세요.");
      await addTracked({ instrument_id: id, ...mapPosition(position) }, csrfToken);
      await Promise.all([refreshRows(), refreshCatalog()]);
      setManual({ ...NEW_MANUAL });
      setPosition({ ...EMPTY_POSITION });
      setMessage("등록한 종목을 실제 보유·관심 목록에 저장했습니다. 시세는 아직 제공하지 않습니다.");
    });
  };

  const update = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editing) return;
    void execute(async () => {
      await editTracked(editing, mapPosition(editPosition), csrfToken);
      await refreshRows();
      setEditing(null);
      setMessage("등록 정보를 변경했습니다.");
    });
  };

  const remove = (item: RealTracked) => {
    if (!window.confirm(item.instrument.name + "을(를) 보유·관심 목록에서 삭제하시겠습니까?")) return;
    void execute(async () => {
      await removeTracked(item.id, csrfToken);
      await refreshRows();
      setEditing(null);
      setMessage("등록 목록에서 삭제했습니다. 종목 카탈로그는 유지됩니다.");
    });
  };

  const filtered = rows.filter((item) => filter === "ALL" || item.kind === filter);
  return (
    <div className="page-stack real-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">MY PORTFOLIO · REAL ENTRIES</span>
          <h2>실제 종목 관리</h2>
          <p>직접 등록한 보유·관심 종목을 관리합니다. 승인된 경우에만 KIS의 과거 일봉 종가를 수동 조회할 수 있으며, 현재가·평가손익·알림은 아직 제공하지 않습니다.</p>
        </div>
        <button className="button secondary" disabled={busy || loading}
          onClick={() => void execute(async () => { await Promise.all([refreshRows(), refreshCatalog()]); setMessage("목록을 새로고침했습니다."); })}>
          새로고침
        </button>
      </div>

      <div className="real-warning" role="note">
        <strong>직접 입력 · {referenceEnabled ? "참고 일봉 수동 조회" : "KIS 참고 일봉 조회 비활성"}</strong>
        <span>최근 일봉 종가는 실시간 현재가나 최종 확정가가 아닙니다. 수동 조회는 별도 운영 승인 후 활성화되며, 평가손익·신호·알림 계산에 사용하지 않고 DEMO와도 분리합니다.</span>
      </div>
      {error && <div className="real-error" role="alert">{error}</div>}
      {message && <div className="real-message" role="status">{message}</div>}

      <section className="card real-card">
        <div className="real-section-title">
          <h3>보유·관심 목록</h3><span>{rows.length}건{nextRows ? " 이상" : ""}</span>
        </div>
        <div className="real-filter" role="group" aria-label="목록 분류">
          {([
            ["ALL", "전체"], ["HOLDING", "보유 종목"], ["WATCH", "관심 종목"],
          ] as const).map(([kind, label]) => (
            <button key={kind} type="button" className={filter === kind ? "active" : ""}
              onClick={() => setFilter(kind)}>{label}</button>
          ))}
        </div>
        {loading ? <p role="status">실제 종목 데이터를 확인 중입니다.</p> : (
          <>
            {!filtered.length && <div className="real-empty">등록된 종목이 없습니다. 아래에서 직접 추가할 수 있습니다.</div>}
            {filtered.map((item) => (
              <div className="real-item" key={item.id}>
                <div className="real-item-main">
                  <strong>{item.instrument.name}</strong>
                  <span>{item.instrument.symbol} · {item.instrument.exchange_mic} · {item.instrument.currency}</span>
                  <span className="real-pill">{item.kind === "HOLDING" ? "보유" : "관심"}</span>
                </div>
                <div className="real-item-values">
                  <span>수량 <b>{formatPosition(item)}</b></span>
                  <span>평균단가 <b>{item.average_cost ?? "미입력"} {item.average_cost ? item.instrument.currency : ""}</b></span>
                  <span className="real-muted" aria-label="시세 품질 상태">{hiddenQuoteLabel(item.quote.status)}</span>
                  {referenceById[item.id] && (
                    <span className="real-muted" role="status" aria-label="KIS 비확정 일봉 참고 가격">
                      {referenceById[item.id].status === "REFERENCE"
                        ? `KIS 참고 일봉 종가: ${referenceById[item.id].close} ${referenceById[item.id].currency}`
                        : referenceById[item.id].status === "STALE"
                        ? "오래된 KIS 일봉 · 가격 표시 안 함"
                        : "조회 가능한 일봉 없음"}
                      {referenceById[item.id].session_date
                        ? ` · 거래일 ${referenceById[item.id].session_date}` : ""}
                      {referenceById[item.id].fetched_at
                        ? ` · 수신 ${new Date(referenceById[item.id].fetched_at!).toLocaleString("ko-KR", { timeZone: "Asia/Seoul", hour12: false })} KST` : ""}
                      {" · 최종 확정 미검증 · 손익 미계산"}
                    </span>
                  )}
                </div>
                <div className="real-item-actions">
                  <button type="button" disabled={busy || !referenceEnabled}
                    aria-label={item.instrument.name + " KIS 참고 일봉 종가 수동 조회"}
                    onClick={() => void execute(async () => {
                      setReferenceById((current) => {
                        const next = { ...current };
                        delete next[item.id];
                        return next;
                      });
                      const reference = await loadManualDailyReference(item.id, csrfToken);
                      if (reference.currency !== item.instrument.currency) {
                        throw new Error("KIS 참고 시세 통화가 종목 정보와 일치하지 않습니다.");
                      }
                      setReferenceById((current) => ({ ...current, [item.id]: reference }));
                      setMessage("KIS의 과거 일봉 참고값만 조회했습니다. 현재가·최종 종가나 평가손익으로 사용하지 않습니다.");
                    })}>참고 종가 조회</button>
                  <button type="button" disabled={busy}
                    aria-label={item.instrument.name + " 시세 품질 상태 확인"}
                    onClick={() => void execute(async () => {
                      const quote = await loadTrackedQuoteStatus(item.id);
                      setRows((current) => current.map((row) =>
                        row.id === item.id ? { ...row, quote } : row
                      ));
                      setMessage("시세 품질 상태만 확인했습니다. 가격과 손익은 조회하지 않습니다.");
                    })}>상태 확인</button>
                  <button type="button" disabled={busy} onClick={() => {
                    setEditing(item.id);
                    setEditPosition({
                      kind: item.kind, quantity: item.quantity ?? "",
                      average_cost: item.average_cost ?? "", memo: item.memo ?? "",
                      alerts_enabled: item.alerts_enabled,
                    });
                    setError(""); setMessage("");
                  }}>수정</button>
                  <button type="button" disabled={busy} onClick={() => remove(item)}>삭제</button>
                </div>
              </div>
            ))}
            {nextRows && <button className="button secondary" disabled={busy} onClick={() => void execute(async () => {
              const page = await loadTracked(nextRows);
              setRows((current) => [...current, ...page.items]);
              setNextRows(page.next_cursor);
            })}>목록 더 보기</button>}
          </>
        )}
      </section>

      {editing && (
        <section className="card real-card">
          <div className="real-section-title"><h3>등록 종목 수정</h3>
            <button className="button secondary" disabled={busy} onClick={() => setEditing(null)}>닫기</button>
          </div>
          <form onSubmit={update}>
            <PositionFields value={editPosition} disabled={busy}
              update={(changes) => setEditPosition((prev) => ({ ...prev, ...changes }))} />
            <div className="real-actions">
              <button type="submit" className="button primary" disabled={busy}>변경 저장</button>
            </div>
          </form>
        </section>
      )}

      <section className="card real-card">
        <div className="real-section-title"><h3>종목 추가</h3><span>직접 입력 또는 기존 종목 선택</span></div>
        <div className="real-filter" role="group" aria-label="추가 방법">
          <button type="button" className={mode === "manual" ? "active" : ""}
            onClick={() => setMode("manual")}>새 종목 직접 입력</button>
          <button type="button" className={mode === "existing" ? "active" : ""}
            onClick={() => setMode("existing")}>기존 등록 종목 선택</button>
        </div>
        <form onSubmit={register}>
          {mode === "manual" ? (
            <div className="real-form-grid">
              <label>시장
                <select disabled={busy} value={manual.market} onChange={(e) => {
                  const market = e.target.value as Market;
                  setManual((m) => ({ ...m, market, exchange_mic: EXCHANGES[market][0].code }));
                }}>
                  <option value="KR">한국 (KRW)</option>
                  <option value="US">미국 (USD)</option>
                </select>
              </label>
              <label>거래소
                <select disabled={busy} value={manual.exchange_mic}
                  onChange={(e) => setManual((m) => ({ ...m, exchange_mic: e.target.value }))}>
                  {EXCHANGES[manual.market].map((x) => <option key={x.code} value={x.code}>{x.name}</option>)}
                </select>
              </label>
              <label>종목 코드
                <input required maxLength={32} autoComplete="off" disabled={busy}
                  placeholder={manual.market === "KR" ? "예: 005930" : "예: AAPL"}
                  value={manual.symbol} onChange={(e) => setManual((m) => ({ ...m, symbol: e.target.value }))} />
              </label>
              <label>종목명
                <input required maxLength={256} autoComplete="off" disabled={busy}
                  placeholder="종목명을 직접 입력하세요"
                  value={manual.name} onChange={(e) => setManual((m) => ({ ...m, name: e.target.value }))} />
              </label>
              <label>유형
                <select disabled={busy} value={manual.asset_type}
                  onChange={(e) => setManual((m) => ({ ...m, asset_type: e.target.value as AssetType }))}>
                  <option value="STOCK">주식</option><option value="ETF">ETF</option>
                </select>
              </label>
            </div>
          ) : (
            <div className="real-form-grid">
              <label>기존 종목 검색
                <div className="real-search">
                  <input value={search} disabled={busy} placeholder="종목명 또는 코드"
                    onChange={(e) => setSearch(e.target.value)} />
                  <button type="button" disabled={busy} onClick={() => void execute(async () => { await refreshCatalog(search); })}>검색</button>
                </div>
              </label>
              <label>등록할 종목
                <select value={selected} disabled={busy} required
                  onChange={(e) => setSelected(e.target.value)}>
                  <option value="">종목을 선택하세요</option>
                  {instruments.map((stock) => (
                    <option key={stock.id} value={stock.id}>
                      {stock.name} ({stock.symbol} · {stock.exchange_mic})
                    </option>
                  ))}
                </select>
              </label>
              {nextInstruments && (
                <button type="button" disabled={busy} className="button secondary"
                  onClick={() => void execute(async () => {
                    const more = await loadInstruments(search, nextInstruments);
                    setInstruments((current) => [...current, ...more.items]);
                    setNextInstruments(more.next_cursor);
                  })}>검색 결과 더 보기</button>
              )}
            </div>
          )}
          <PositionFields value={position} disabled={busy}
            update={(changes) => setPosition((prev) => ({ ...prev, ...changes }))} />
          <div className="real-actions">
            <button className="button primary" type="submit" disabled={busy || loading}>
              {busy ? "저장 중…" : "종목 등록"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
