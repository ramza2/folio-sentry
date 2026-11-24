import { useEffect, useState } from "react";
import { loadReferenceHistory, priceUnits, type RealTracked, type ReferenceHistory,
  type ReferenceHistoryDays } from "./realPortfolioApi";

function format(value: string) {
  const [whole, fraction = ""] = value.split(".");
  const tail = fraction.replace(/0+$/, "");
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (tail ? "." + tail : "");
}
function receipt(value: string) {
  return new Date(value).toLocaleString("ko-KR", { timeZone: "Asia/Seoul", hour12: false }) + " KST";
}

function Candles({ history, selected, select }: {
  history: ReferenceHistory; selected: number; select: (index: number) => void;
}) {
  const bars = history.bars;
  const low = bars.reduce((a, b) => priceUnits(b.low) < a ? priceUnits(b.low) : a, priceUnits(bars[0].low));
  const high = bars.reduce((a, b) => priceUnits(b.high) > a ? priceUnits(b.high) : a, priceUnits(bars[0].high));
  const maxVolume = bars.reduce((a, b) => BigInt(b.volume) > a ? BigInt(b.volume) : a, 0n);
  const ratio = (value: bigint, span: bigint) => span === 0n ? 0.5 : Number(value * 1000000n / span) / 1000000;
  const y = (price: string) => 195 - 175 * ratio(priceUnits(price) - low, high - low);
  const dx = 700 / bars.length;
  const width = Math.min(22, Math.max(2, dx * 0.63));
  return (
    <svg viewBox="0 0 760 280" role="img"
      aria-label="저장된 참고 일봉 캔들 및 거래량 차트"
      style={{ display: "block", width: "100%", minWidth: 0, height: "auto" }}>
      <text x="20" y="11" fill="currentColor" fontSize="11">최고 {format(bars.find(b => priceUnits(b.high) === high)!.high)} {history.currency}</text>
      <text x="720" y="207" textAnchor="end" fill="currentColor" fontSize="11">최저 {format(bars.find(b => priceUnits(b.low) === low)!.low)}</text>
      <text x="20" y="207" fill="currentColor" fontSize="10">거래량</text>
      {[20, 64, 108, 152, 195, 258].map(v =>
        <line key={v} x1="20" x2="720" y1={v} y2={v} stroke="currentColor" opacity={0.15}/>)}
      {bars.map((bar, i) => {
        const x = 20 + dx * (i + 0.5);
        const color = priceUnits(bar.close) >= priceUnits(bar.open) ? "#d34b59" : "#3c83d6";
        const top = Math.min(y(bar.open), y(bar.close));
        const h = Math.max(1.4, Math.abs(y(bar.open) - y(bar.close)));
        const volume = maxVolume === 0n ? 0 : 46 * ratio(BigInt(bar.volume), maxVolume);
        return <g key={bar.session_date} onClick={() => select(i)} style={{ cursor: "pointer" }}>
          <title>{bar.session_date + " 종가 " + format(bar.close) + " " + history.currency}</title>
          {i === selected && <rect x={x-dx/2} y="12" width={dx} height="248" rx="2"
            fill="currentColor" opacity={0.09}/>}
          <line x1={x} x2={x} y1={y(bar.high)} y2={y(bar.low)} stroke={color} strokeWidth="1.3"/>
          <rect x={x-width/2} y={top} width={width} height={h} fill={color}/>
          <rect x={x-width/2} y={258-volume} width={width} height={volume} fill={color} opacity={0.55}/>
          <rect x={x-dx/2} y="12" width={dx} height="248" fill="transparent"/>
        </g>;
      })}
      <text x="20" y="273" fill="currentColor" fontSize="11">{bars[0].session_date}</text>
      {bars.length > 1 && <text x="720" y="273" textAnchor="end" fill="currentColor" fontSize="11">{bars[bars.length-1].session_date}</text>}
    </svg>
  );
}

export default function ReferenceHistoryChart({ item, close }: {
  item: RealTracked; close: () => void;
}) {
  const [days, setDays] = useState<ReferenceHistoryDays>(90);
  const [history, setHistory] = useState<ReferenceHistory | null>(null);
  const [selected, setSelected] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setHistory(null);
    setError("");
    void loadReferenceHistory(item.id, item.instrument.currency, days, controller.signal)
      .then(data => {
        if (controller.signal.aborted) return;
        setHistory(data);
        setSelected(Math.max(0, data.bars.length-1));
      })
      .catch(reason => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "참고 일봉 조회 실패");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [item.id, item.instrument.currency, days, refresh]);
  const data = history?.days === days && history.tracked_id === item.id ? history : null;
  const bar = data?.bars[selected];
  return (
    <section className="card real-card" aria-label="저장된 참고 일봉 차트">
      <div className="real-section-title">
        <h3>{item.instrument.name} · 참고 일봉 차트</h3>
        <button className="button secondary" onClick={close}>닫기</button>
      </div>
      <p className="real-muted">KIS 저장 이력 · 원주가(RAW) · 최종 확정 미검증 · 실시간 아님. 누락 거래일 및 기업행사 반영 여부는 확인되지 않았습니다. 가로축은 저장된 거래일을 같은 간격으로 배치하며 누락 날짜를 채우지 않습니다.</p>
      <div className="real-filter" role="group" aria-label="차트 기간">
        {([30,90] as const).map(d => <button type="button" key={d} aria-pressed={days === d}
          className={days === d ? "active" : ""} onClick={() => setDays(d)}>{d}일</button>)}
        <button type="button" disabled={loading} onClick={() => setRefresh(n => n+1)}>저장 이력 새로고침</button>
      </div>
      {loading && <p role="status">저장된 일봉을 확인 중입니다.</p>}
      {!loading && error && <p className="real-error" role="alert">{error}</p>}
      {!loading && data && <>
        <div className="real-item-values">
          <span>조회 범위 <b>{data.start_date} ~ {data.end_date}</b></span>
          <span>저장 행 <b>{data.stored_rows}건</b></span>
          <span>최근 저장 거래일 <b>{data.latest_session_date ?? "—"}</b></span>
          <span>가장 최근 수신 <b>{data.latest_receipt ? receipt(data.latest_receipt) : "—"}</b></span>
        </div>
        {!data.bars.length ? <div className="real-empty">저장된 참고 일봉이 없습니다. 수집 여부 및 결과를 확인하세요. 이 화면에서는 KIS를 호출하지 않습니다.</div> :
          <>
            <Candles history={data} selected={selected} select={setSelected}/>
            <label>거래일 선택 <select value={selected} onChange={e => setSelected(Number(e.target.value))}>
              {data.bars.map((b,i) => <option key={b.session_date} value={i}>{b.session_date}</option>)}
            </select></label>
            {bar && <div className="real-item-values" aria-label="선택 일봉 상세">
              <span>시가 <b>{format(bar.open)} {data.currency}</b></span>
              <span>고가 <b>{format(bar.high)}</b></span>
              <span>저가 <b>{format(bar.low)}</b></span>
              <span>종가 <b>{format(bar.close)}</b></span>
              <span>거래량 <b>{format(bar.volume)}</b></span>
              <span>앱 수신 <b>{receipt(bar.fetched_at)}</b></span>
            </div>}
          </>}
      </>}
    </section>
  );
}
