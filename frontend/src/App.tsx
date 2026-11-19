import { useEffect, useState } from "react";

type Instrument = {
  market: "KR" | "US";
  exchange: string;
  symbol: string;
  name: string;
  currency: "KRW" | "USD";
  is_demo: true;
};
type DemoResponse = { mode: "demo"; instruments: Instrument[] };
type ApiState =
  | { status: "loading" }
  | { status: "failed" }
  | { status: "ready"; data: DemoResponse };

export default function App() {
  const [state, setState] = useState<ApiState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/demo/instruments", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("API unavailable");
        return response.json() as Promise<DemoResponse>;
      })
      .then((data) => {
        if (data.mode !== "demo" || !Array.isArray(data.instruments)) {
          throw new Error("Invalid demo response");
        }
        setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === "AbortError") return;
        setState({ status: "failed" });
      });
    return () => controller.abort();
  }, []);

  return (
    <main>
      <h1>FolioSentry</h1>
      <p>개인용 국내·미국 주식 모니터링 — Phase 0 연결 점검</p>
      <section aria-label="서비스 상태">
        {state.status === "loading" && <p>API 확인 중…</p>}
        {state.status === "failed" && (
          <p role="alert">API 연결 실패. Backend 실행 상태를 확인하세요.</p>
        )}
        {state.status === "ready" && (
          <>
            <p>모의 종목 API 연결 성공</p>
            <ul>
              {state.data.instruments.map((item) => (
                <li key={item.exchange + ":" + item.symbol}>
                  {item.market} · {item.name} ({item.symbol}) · {item.currency}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
      <p className="notice">
        이 화면에는 실제 시세, 보유 자산, 매매 신호가 없습니다.
        본격적인 UI는 Figma Make 디자인 확정 후 구현합니다.
      </p>
    </main>
  );
}
