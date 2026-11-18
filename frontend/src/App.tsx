import { useEffect, useMemo, useState } from "react";
import {
  fetchDemoOverview, formatDateTime, formatMoney, formatPercent,
  signalBadge, stockViews, type DemoOverview,
} from "./demoApi";

type Page = "dashboard" | "stocks" | "detail" | "news" | "signals" | "settings";
type IconName =
  | "grid"
  | "briefcase"
  | "chart"
  | "news"
  | "bell"
  | "settings"
  | "search"
  | "plus"
  | "chevron"
  | "arrowUp"
  | "arrowDown"
  | "clock"
  | "external"
  | "menu"
  | "close"
  | "more"
  | "refresh"
  | "moon"
  | "sun"
  | "check"
  | "info"
  | "filter"
  | "edit"
  | "shield";

function Icon({
  name,
  size = 18,
  className = "",
}: {
  name: IconName;
  size?: number;
  className?: string;
}) {
  const paths: Record<IconName, React.ReactNode> = {
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="2" />
        <rect x="14" y="3" width="7" height="7" rx="2" />
        <rect x="3" y="14" width="7" height="7" rx="2" />
        <rect x="14" y="14" width="7" height="7" rx="2" />
      </>
    ),
    briefcase: (
      <>
        <rect x="3" y="7" width="18" height="13" rx="3" />
        <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" />
      </>
    ),
    chart: (
      <>
        <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
        <path d="m3 7 6-4 6 5 6-5" />
      </>
    ),
    news: (
      <>
        <path d="M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
        <path d="M7 8h6M7 12h10M7 16h10" />
      </>
    ),
    bell: (
      <>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    arrowUp: (
      <>
        <path d="m18 15-6-6-6 6" />
        <path d="M12 9v10" />
      </>
    ),
    arrowDown: (
      <>
        <path d="m6 9 6 6 6-6" />
        <path d="M12 5v10" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    external: (
      <>
        <path d="M14 4h6v6M20 4l-9 9" />
        <path d="M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6" />
      </>
    ),
    menu: <path d="M4 7h16M4 12h16M4 17h16" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    more: (
      <>
        <circle cx="5" cy="12" r="1" />
        <circle cx="12" cy="12" r="1" />
        <circle cx="19" cy="12" r="1" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 7h-5V2" />
        <path d="M20 7a8 8 0 1 0 1 7" />
      </>
    ),
    moon: <path d="M20 15.5A9 9 0 0 1 8.5 4 9 9 0 1 0 20 15.5Z" />,
    sun: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v5M12 8h.01" />
      </>
    ),
    filter: <path d="M4 5h16M7 12h10M10 19h4" />,
    edit: (
      <>
        <path d="m14 5 5 5L9 20H4v-5Z" />
        <path d="m13 6 5 5" />
      </>
    ),
    shield: (
      <>
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
        <path d="m9 12 2 2 4-4" />
      </>
    ),
  };
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}

const navItems: { page: Page; label: string; icon: IconName }[] = [
  { page: "dashboard", label: "대시보드", icon: "grid" },
  { page: "stocks", label: "내 종목", icon: "briefcase" },
  { page: "detail", label: "종목 상세", icon: "chart" },
  { page: "news", label: "뉴스", icon: "news" },
  { page: "signals", label: "신호 · 알림", icon: "bell" },
  { page: "settings", label: "설정", icon: "settings" },
];

// DEMO data is loaded exclusively from /api/v1/demo/overview.
// There are no hardcoded quote, holdings, news, or signal arrays.

function Logo() {
  return (
    <div className="logo">
      <span className="logo-mark">
        <span />
      </span>
      <strong>FolioSentry</strong>
    </div>
  );
}

function Sidebar({
  page,
  setPage,
  open,
  setOpen,
}: {
  page: Page;
  setPage: (p: Page) => void;
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  return (
    <>
      {open && <div className="mobile-overlay" onClick={() => setOpen(false)} />}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="sidebar-head">
          <Logo />
          <button className="icon-button mobile-only" onClick={() => setOpen(false)}>
            <Icon name="close" />
          </button>
        </div>
        <nav>
          {navItems.map((item) => (
            <button
              key={item.page}
              className={page === item.page ? "active" : ""}
              onClick={() => {
                setPage(item.page);
                setOpen(false);
              }}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.page === "signals" && <em>3</em>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="market-mini">
            <span className="status-dot" />
            <div>
              <b>데모 데이터</b>
              <small>실시간 연동 전</small>
            </div>
          </div>
          <div className="profile">
            <span>FS</span>
            <div>
              <b>개인 포트폴리오</b>
              <small>설정되지 않음</small>
            </div>
            <Icon name="more" />
          </div>
        </div>
      </aside>
    </>
  );
}

function Topbar({
  title,
  setMenu,
  dark,
  setDark,
}: {
  title: string;
  setMenu: (v: boolean) => void;
  dark: boolean;
  setDark: (v: boolean) => void;
}) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <button className="icon-button mobile-menu" onClick={() => setMenu(true)}>
          <Icon name="menu" />
        </button>
        <div>
          <h1>{title}</h1>
          <p>오늘의 포트폴리오와 시장 흐름을 확인하세요</p>
        </div>
      </div>
      <div className="top-actions">
        <div className="global-search">
          <Icon name="search" size={17} />
          <input aria-label="통합 검색 (준비 중)" placeholder="통합 검색 (준비 중)" readOnly title="정식 검색 API 연결 전에는 비활성화됩니다" />
          <kbd>⌘ K</kbd>
        </div>
        <button className="icon-button" onClick={() => setDark(!dark)} aria-label="테마 변경">
          <Icon name={dark ? "sun" : "moon"} />
        </button>
        <button className="icon-button has-dot" disabled title="알림 기능은 이후 단계에서 연결합니다" aria-label="알림 미지원">
          <Icon name="bell" />
        </button>
        <div className="avatar">FS</div>
      </div>
    </header>
  );
}

function DemoBanner() {
  return (
    <div className="demo-banner">
      <Icon name="info" size={16} />
      <b>DEMO</b>
      <span>화면 시연용 가상 데이터입니다. 실제 시세·뉴스·매매 신호가 아닙니다.</span>
      <span className="banner-disclaimer">
        모든 신호는 참고용이며 자동매매 기능을 제공하지 않습니다.
      </span>
    </div>
  );
}

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

function CardHeader({
  title,
  desc,
  action,
}: {
  title: string;
  desc?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="card-header">
      <div>
        <h2>{title}</h2>
        {desc && <p>{desc}</p>}
      </div>
      {action}
    </div>
  );
}

function StatusPill({
  kind,
  children,
}: {
  kind: "buy" | "sell" | "watch" | "risk" | "neutral";
  children: React.ReactNode;
}) {
  return (
    <span className={`status-pill ${kind}`}>
      {kind === "buy" && <Icon name="arrowUp" size={13} />}{" "}
      {kind === "sell" && <Icon name="arrowDown" size={13} />} {kind === "risk" && <span>!</span>}
      {children}
    </span>
  );
}

function Sparkline({ red = false, flat = false }: { red?: boolean; flat?: boolean }) {
  const points = flat
    ? "2,23 15,18 28,20 42,14 56,16 70,10 84,12 100,7"
    : red
      ? "2,7 16,10 30,8 44,16 58,13 72,21 86,18 100,24"
      : "2,24 16,20 30,22 44,13 58,17 72,10 86,12 100,4";
  return (
    <svg className={`spark ${red ? "red" : ""}`} viewBox="0 0 102 30">
      <path d={`M${points} L100,30 L2,30Z`} className="spark-area" />
      <polyline points={points} fill="none" />
    </svg>
  );
}


function Dashboard({
  data, go, goDetail,
}: {
  data: DemoOverview;
  go: (page: Page) => void;
  goDetail: (id: string) => void;
}) {
  const stocks = stockViews(data);
  const holdings = stocks.filter((stock) => stock.kind === "HOLDING");
  const buys = data.signals.filter((signal) => signal.type === "BUY_REVIEW");
  const risks = data.signals.filter((signal) =>
    signal.type === "SELL_REVIEW" || signal.type === "RISK");
  const krw = data.summary.valuation_by_currency.KRW ?? null;
  const usd = data.summary.valuation_by_currency.USD ?? null;
  const instrumentName = (id: string) =>
    stocks.find((stock) => stock.id === id)?.name ?? "미등록 종목";
  return (
    <div className="page-stack">
      <div className="welcome-row">
        <div>
          <span className="eyebrow">디자인 시안 · API 기반 가상 데이터</span>
          <h2>안녕하세요. 등록된 종목을 확인하세요.</h2>
        </div>
        <div className="market-statuses">
          <span><i className="status-dot" /> 한국 시장 <b>상태 미연동</b></span>
          <span><i className="status-dot" /> 미국 시장 <b>상태 미연동</b></span>
          <small><Icon name="refresh" size={13} /> 데모 기준 {formatDateTime(data.as_of)}</small>
        </div>
      </div>
      <DemoBanner />
      <div className="metric-grid">
        <Card className="metric-card">
          <div className="metric-top"><span className="metric-icon blue"><Icon name="briefcase" /></span><small>보유 종목</small><Icon name="more" /></div>
          <strong>{data.summary.holding_count}<em>종목</em></strong>
          <p>국내 {holdings.filter((x) => x.flag === "KR").length} · 미국 {holdings.filter((x) => x.flag === "US").length}</p>
        </Card>
        <Card className="metric-card">
          <div className="metric-top"><span className="metric-icon slate"><Icon name="chart" /></span><small>관심 종목</small><Icon name="more" /></div>
          <strong>{data.summary.watch_count}<em>종목</em></strong>
          <p>추적 중인 관심 종목</p>
        </Card>
        <Card className="metric-card emphasis">
          <div className="metric-top"><span className="metric-icon mint"><Icon name="arrowUp" /></span><small>매수 검토</small><Icon name="chevron" /></div>
          <strong>{buys.length}<em>건</em></strong>
          <p>데모 신호 · 매매 권유 아님</p>
        </Card>
        <Card className="metric-card">
          <div className="metric-top"><span className="metric-icon coral"><Icon name="arrowDown" /></span><small>매도 · 위험</small><Icon name="chevron" /></div>
          <strong>{risks.length}<em>건</em></strong>
          <p>데모 신호 · 전송 안 됨</p>
        </Card>
      </div>
      <div className="asset-grid">
        <Card className="asset-card">
          <div className="asset-heading"><div><span className="flag kr">KR</span><b>국내 주식 자산</b></div><span>KRW</span></div>
          <div className="asset-value"><strong>{formatMoney(krw, "KRW")}</strong><span>가상 시세 기준</span></div>
          <div className="allocation"><span style={{ width: krw ? "100%" : "0%" }} /></div>
          <small>원화 보유분만 계산 · 원화/달러 합산 안 함</small>
        </Card>
        <Card className="asset-card">
          <div className="asset-heading"><div><span className="flag us">US</span><b>미국 주식 자산</b></div><span>USD</span></div>
          <div className="asset-value"><strong>{formatMoney(usd, "USD")}</strong><span>가상 시세 기준</span></div>
          <div className="allocation"><span style={{ width: usd ? "100%" : "0%" }} /></div>
          <small>달러 보유분만 계산 · 환율 미적용</small>
        </Card>
      </div>
      <div className="dashboard-main">
        <Card className="portfolio-card">
          <CardHeader title="내 포트폴리오" desc="API에 등록된 가상 종목입니다" action={
            <button className="text-button" onClick={() => go("stocks")}>전체 보기 <Icon name="chevron" size={14} /></button>
          } />
          <div className="stock-list">
            {holdings.length === 0 && <div className="empty-state">등록된 보유 종목이 없습니다.</div>}
            {holdings.slice(0, 3).map((stock, index) => (
              <button className="stock-row" key={stock.id} onClick={() => goDetail(stock.id)}>
                <div className="stock-id">
                  <span className={"stock-logo s" + index}>{stock.name.slice(0, 1)}</span>
                  <div><b>{stock.name}</b><small>{stock.ticker} · {stock.market}</small></div>
                </div>
                <span className="relevance">차트 미연동</span>
                <div className="stock-price"><b>{stock.price}</b><span className={stock.up ? "positive" : "negative"}>{stock.change}</span></div>
                <div className="stock-pnl"><small>평가손익 (데모)</small><b className={stock.pnl.startsWith("-") ? "negative" : "positive"}>{stock.pnl}</b><span>{stock.pnlRate}</span></div>
                <Icon name="chevron" size={16} />
              </button>
            ))}
          </div>
        </Card>
        <Card className="signals-card">
          <CardHeader title="최근 매매 신호" desc="API 제공 가상 신호 · 실제 분석 아님" action={
            <button className="text-button" onClick={() => go("signals")}>이력 보기 <Icon name="chevron" size={14} /></button>
          } />
          {data.signals.length === 0 && <div className="empty-state">표시할 신호가 없습니다.</div>}
          {data.signals.slice(0, 2).map((signal, index) => {
            const badge = signalBadge(signal.type);
            return (
              <div className="signal-item" key={signal.id}>
                <div className="signal-line">
                  <div className="stock-id">
                    <span className={"stock-logo s" + index}>{instrumentName(signal.instrument_id).slice(0, 1)}</span>
                    <div><b>{instrumentName(signal.instrument_id)}</b><small>{formatDateTime(signal.evaluated_at)}</small></div>
                  </div>
                  <StatusPill kind={badge.kind}>{badge.label} · DEMO</StatusPill>
                </div>
                <p>{signal.reason}</p>
                <div className="indicator-tags">
                  {signal.evidence.map((entry) => (
                    <span key={entry.metric}><i className={entry.met ? "ok" : ""} />{entry.metric}: {entry.observed ?? "—"}</span>
                  ))}
                  {signal.evidence.length === 0 && <span>지표 근거 없음 (데모)</span>}
                </div>
              </div>
            );
          })}
        </Card>
      </div>
      <Card>
        <CardHeader title="보유 종목 관련 최신 뉴스" desc="실제 뉴스가 아닌 API 데모 기사입니다" action={
          <button className="text-button" onClick={() => go("news")}>뉴스 전체 보기 <Icon name="chevron" size={14} /></button>
        } />
        <div className="news-compact-grid">
          {data.news.length === 0 && <div className="empty-state">표시할 뉴스가 없습니다.</div>}
          {data.news.slice(0, 3).map((news) => (
            <article className="news-compact" key={news.id}>
              <div className="news-meta"><span>DEMO</span><b>{news.publisher}</b><small>{formatDateTime(news.published_at)}</small></div>
              <h3>{news.title}</h3>
              <p>기사 본문·AI 요약은 제공되지 않습니다.</p>
              <div><span className="tag">{instrumentName(news.instrument_id)}</span><span className="relevance">실제 원문 아님</span></div>
            </article>
          ))}
        </div>
      </Card>
    </div>
  );
}


function Modal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-wrap" role="dialog" aria-modal="true">
      <div className="modal-backdrop" onClick={onClose} />
      <div className="modal">
        <div className="modal-head">
          <div>
            <h2>보유 종목 등록</h2>
            <p>포트폴리오에 보유 종목을 추가합니다.</p>
          </div>
          <button className="icon-button" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>
        <label>
          종목 검색
          <div className="input-wrap">
            <Icon name="search" />
            <input defaultValue="삼성전자 (005930)" />
          </div>
        </label>
        <div className="selected-stock">
          <span className="stock-logo s0">삼</span>
          <div>
            <b>삼성전자</b>
            <small>005930 · KRX · KRW</small>
          </div>
          <Icon name="check" className="positive" />
        </div>
        <div className="form-grid">
          <label>
            보유 수량
            <input type="number" defaultValue="40" />
            <span>주</span>
          </label>
          <label>
            평균 매수가
            <input type="text" defaultValue="68,250" />
            <span>원</span>
          </label>
        </div>
        <div className="calc-row">
          <span>예상 매입금액</span>
          <b>2,730,000원</b>
        </div>
        <label className="check-label">
          <input type="checkbox" defaultChecked />
          <span>
            <Icon name="check" size={13} />
          </span>
          이 종목의 매매 신호와 뉴스를 알림으로 받기
        </label>
        <div className="modal-actions">
          <button className="button secondary" onClick={onClose}>
            취소
          </button>
          <button className="button primary" disabled title="데모 화면에서는 종목을 실제로 등록할 수 없습니다">
            등록 미지원 (DEMO)
          </button>
        </div>
      </div>
    </div>
  );
}


function StocksPage({
  data, goDetail,
}: {
  data: DemoOverview;
  goDetail: (id: string) => void;
}) {
  const [tab, setTab] = useState("보유 종목");
  const [market, setMarket] = useState("전체");
  const [query, setQuery] = useState("");
  const [modal, setModal] = useState(false);
  const [localAlerts, setLocalAlerts] = useState<Record<string, boolean>>({});
  const stocks = stockViews(data);
  const displayed = stocks.filter((stock) =>
    (market === "전체" || (market === "국내" ? stock.flag === "KR" : stock.flag === "US")) &&
    (stock.name.toLowerCase().includes(query.toLowerCase()) ||
      stock.ticker.toLowerCase().includes(query.toLowerCase())) &&
    (tab === "보유 종목" ? stock.kind === "HOLDING" : stock.kind === "WATCH")
  );
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div><span className="eyebrow">PORTFOLIO · DEMO</span><h2>내 종목</h2><p>API에서 가져온 가상 보유·관심 종목입니다.</p></div>
        <button className="button primary" onClick={() => setModal(true)}><Icon name="plus" /> 종목 등록 (미리보기)</button>
      </div>
      <DemoBanner />
      <Card className="table-card">
        <div className="toolbar">
          <div className="tabs">
            {["보유 종목", "관심 종목"].map((label) => (
              <button className={tab === label ? "active" : ""} onClick={() => setTab(label)} key={label}>
                {label}<span>{label === "보유 종목" ? data.summary.holding_count : data.summary.watch_count}</span>
              </button>
            ))}
          </div>
          <div className="tools">
            <div className="segmented">
              {["전체", "국내", "미국"].map((label) => (
                <button className={market === label ? "active" : ""} onClick={() => setMarket(label)} key={label}>{label}</button>
              ))}
            </div>
            <div className="input-wrap search-small">
              <Icon name="search" /><input placeholder="종목 검색" value={query} onChange={(event) => setQuery(event.target.value)} />
            </div>
            <button className="icon-button" disabled title="고급 필터는 추후 지원"><Icon name="filter" /></button>
          </div>
        </div>
        <div className="data-table">
          <div className="table-row table-head">
            <span>종목</span><span>현재가 / 등락</span><span>보유 수량</span><span>평균 매수가</span>
            <span>평가손익</span><span>신호</span><span>알림</span><span />
          </div>
          {displayed.length ? displayed.map((stock, index) => (
            <div className="table-row" key={stock.id} role="button" tabIndex={0}
              onClick={() => goDetail(stock.id)}
              onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); goDetail(stock.id); } }}>
              <div className="stock-id">
                <span className={"stock-logo s" + index}>{stock.name.slice(0, 1)}</span>
                <div><b>{stock.name}</b><small>{stock.ticker} · {stock.market}</small></div>
              </div>
              <div><b>{stock.price}</b><small className={stock.up ? "positive" : "negative"}>{stock.change} · {stock.quoteStatus === "UNAVAILABLE" ? "시세 없음" : "DEMO"}</small></div>
              <span>{stock.qty}</span><span>{stock.avg}</span>
              <div><b className={stock.pnl.startsWith("-") ? "negative" : "positive"}>{stock.pnl}</b><small>{stock.pnlRate}</small></div>
              <div><StatusPill kind={stock.signalKind}>{stock.signal}</StatusPill></div>
              <button aria-label={stock.name + " 데모 알림 상태 전환"} title="화면에만 적용되고 저장되지 않습니다"
                className={"toggle " + ((localAlerts[stock.id] ?? stock.alertsEnabled) ? "on" : "")}
                onClick={(event) => {
                  event.stopPropagation();
                  setLocalAlerts((old) => ({ ...old, [stock.id]: !(old[stock.id] ?? stock.alertsEnabled) }));
                }}><span /></button>
              <button className="icon-button" disabled title="실제 종목 수정은 Phase 1에서 지원"><Icon name="edit" size={16} /></button>
            </div>
          )) : (
            <div className="empty-state"><Icon name="search" size={28} /><b>조건에 맞는 종목이 없습니다</b><p>검색어나 시장 필터를 변경해 보세요.</p></div>
          )}
        </div>
      </Card>
      <div className="source-note"><Icon name="info" size={14} /> 마지막 API 데모 기준: {formatDateTime(data.as_of)} · 알림 토글은 저장되지 않습니다.</div>
      {modal && <Modal onClose={() => setModal(false)} />}
    </div>
  );
}



function PriceChart({ period }: { period: string }) {
  return (
    <div className="chart-wrap" role="img" aria-label="차트 시각적 예시, 실제 OHLCV 데이터 없음">
      <svg viewBox="0 0 800 300" preserveAspectRatio="none" className="main-chart" aria-hidden="true">
        {[40, 100, 160, 220, 280].map((y) => (
          <line key={y} x1="0" y1={y} x2="800" y2={y} className="grid-line" />
        ))}
        <path className="price-line" d="M0 245 C40 240 55 210 90 220 S150 150 190 175 S250 120 290 145 S350 165 390 120 S440 140 480 92 S550 112 590 65 S650 80 700 38 S755 62 800 28" />
      </svg>
      <div className="chart-tooltip">
        <small>{period} · 디자인 시각화</small>
        <b>과거 시세 미연동</b>
        <span>이 선은 실제 주가 데이터가 아닙니다</span>
      </div>
    </div>
  );
}

function DetailPage({
  data, selectedId, go,
}: {
  data: DemoOverview;
  selectedId: string | null;
  go: (page: Page) => void;
}) {
  const [period, setPeriod] = useState("1개월");
  const [indicators, setIndicators] = useState(["MA20", "MA60", "거래량"]);
  const toggle = (name: string) =>
    setIndicators((previous) => previous.includes(name)
      ? previous.filter((value) => value !== name) : [...previous, name]);
  const stock = stockViews(data).find((item) => item.id === selectedId) ??
    stockViews(data)[0];
  if (!stock) {
    return <div className="page-stack"><DemoBanner /><Card><div className="empty-state">선택한 종목이 없습니다.</div></Card></div>;
  }
  const tracked = data.tracked.find((item) => item.instrument.id === stock.id);
  const signal = data.signals.find((item) => item.instrument_id === stock.id);
  const badge = signalBadge(signal?.type ?? null);
  const relatedNews = data.news.filter((item) => item.instrument_id === stock.id);
  const rsi = signal?.evidence.find((item) => item.metric === "RSI14")?.observed ?? null;
  return (
    <div className="page-stack">
      <div className="breadcrumb">
        <button onClick={() => go("stocks")}>내 종목</button><Icon name="chevron" size={14} />
        <span>{stock.name} (데모 상세)</span>
      </div>
      <div className="detail-hero">
        <div className="detail-company">
          <span className="stock-logo large s0">{stock.name.slice(0, 1)}</span>
          <div>
            <div><h2>{stock.name}</h2><StatusPill kind={badge.kind}>{badge.label}</StatusPill></div>
            <p>{stock.ticker} · {stock.market} · {stock.currency} <span>{stock.kind === "HOLDING" ? "보유" : "관심"}</span></p>
          </div>
        </div>
        <div className="detail-price">
          <strong>{stock.price}</strong>
          <span className={stock.up ? "positive" : "negative"}>{stock.change} · {stock.quoteStatus === "UNAVAILABLE" ? "시세 없음" : "DEMO"}</span>
          <small>가상 기준 {stock.asOf}</small>
        </div>
        <div className="detail-actions">
          <button className="button secondary" disabled title="개인 알림 설정 API는 이후 구현"><Icon name="bell" /> 알림 설정 (미지원)</button>
        </div>
      </div>
      <DemoBanner />
      <div className="detail-grid">
        <Card className="chart-card">
          <div className="chart-toolbar">
            <div className="periods">
              {["1주", "1개월", "3개월", "6개월", "1년"].map((value) => (
                <button key={value} className={period === value ? "active" : ""} onClick={() => setPeriod(value)}>{value}</button>
              ))}
            </div>
            <div className="chart-indicators">
              {["MA20", "MA60", "MA120", "거래량"].map((value) => (
                <button key={value} className={indicators.includes(value) ? "active" : ""}
                  onClick={() => toggle(value)} title="디자인 선택 상태만 변경됩니다">
                  <i />{value}
                </button>
              ))}
            </div>
          </div>
          <div className="ohlc">
            <span>일봉 OHLCV <b>미연동</b></span>
            <span>차트 <b>디자인 예시</b></span>
            <span>API 시세 <b>{stock.quoteStatus === "UNAVAILABLE" ? "없음" : "DEMO"}</b></span>
          </div>
          <PriceChart period={period} />
          <div className="oscillators">
            <div><span>RSI(14) · 데모 근거</span><b>{rsi ?? "미제공"}</b><small>실제 계산되지 않음</small></div>
            <div><span>MACD</span><b>미제공</b><small>실제 지표는 추후 연동</small></div>
          </div>
        </Card>
        <div className="detail-side">
          <Card className="signal-analysis">
            <CardHeader title="기술적 분석 예시" desc="API가 반환한 가상 신호 근거" />
            {signal ? (
              <>
                <div className="signal-score">
                  <div><StatusPill kind={badge.kind}>{badge.label} · DEMO</StatusPill><strong>{signal.strategy_version}</strong></div>
                  <div className="score-ring"><span>DEMO</span></div>
                </div>
                <p>{signal.reason}</p>
                <ul>
                  {signal.evidence.map((item) => (
                    <li key={item.metric} className={item.met ? "pass" : ""}>
                      {item.met ? <Icon name="check" /> : <span>—</span>}
                      {item.condition} ({item.metric}: {item.observed ?? "—"}) <b>{item.met ? "충족" : "미충족"}</b>
                    </li>
                  ))}
                  {signal.evidence.length === 0 && <li>검증 가능한 지표 근거 없음 (데모)</li>}
                </ul>
              </>
            ) : <div className="empty-state">이 종목에 대한 신호가 없습니다.</div>}
            <div className="disclaimer"><Icon name="shield" size={17} />
              <span>실제 시세·기술적 분석이 아니며 매매 판단에 사용할 수 없습니다.</span>
            </div>
          </Card>
          <Card className="holding-card">
            <CardHeader title="내 보유 현황 (DEMO)" />
            {tracked?.kind === "HOLDING" ? (
              <>
                <div>
                  <span>보유 수량<b>{stock.qty}</b></span>
                  <span>평균 매수가<b>{stock.avg}</b></span>
                  <span>평가 금액<b>{formatMoney(tracked.market_value, stock.currency)}</b></span>
                  <span>평가 손익<b className={stock.pnl.startsWith("-") ? "negative" : "positive"}>{stock.pnl}</b></span>
                </div>
                <div className="return-box"><span>가상 수익률</span><strong>{stock.pnlRate}</strong></div>
              </>
            ) : <div className="empty-state">관심 종목에는 보유 수량과 평가액이 없습니다.</div>}
          </Card>
        </div>
      </div>
      <Card>
        <CardHeader title={stock.name + " 관련 뉴스"} desc="DEMO 뉴스 · 실제 원문 미제공" action={
          <button className="text-button" onClick={() => go("news")}>전체 뉴스 <Icon name="chevron" size={14} /></button>
        } />
        <div className="detail-news">
          {relatedNews.length === 0 && <div className="empty-state">이 종목과 관련된 뉴스가 없습니다.</div>}
          {relatedNews.map((news) => (
            <article key={news.id}>
              <div><span className="importance">DEMO</span><small>{news.publisher} · {formatDateTime(news.published_at)}</small></div>
              <h3>{news.title}</h3>
              <button disabled title="실제 원문 링크는 뉴스 공급자 연동 후 활성화">
                <Icon name="external" size={14} /> 원문 미제공 (DEMO)
              </button>
            </article>
          ))}
        </div>
      </Card>
      <div className="source-note"><Icon name="info" size={14} />
        데이터: {tracked?.quote.source ?? "시세 없음"} · {stock.asOf} · 가상 시세, 실제 시장 정보 아님
      </div>
    </div>
  );
}


function NewsPage() {
  const [region, setRegion] = useState("전체");
  const [query, setQuery] = useState("");
  const filtered = newsItems.filter(
    (n) => (region === "전체" || n.type === region) && n.title.includes(query),
  );
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <span className="eyebrow">MARKET INTELLIGENCE</span>
          <h2>뉴스</h2>
          <p>내 종목과 관련된 주요 뉴스를 중요도 순으로 확인하세요.</p>
        </div>
      </div>
      <DemoBanner />
      <Card className="news-page-card">
        <div className="toolbar">
          <div className="segmented large">
            {["전체", "국내", "해외"].map((r) => (
              <button className={region === r ? "active" : ""} onClick={() => setRegion(r)} key={r}>
                {r}
              </button>
            ))}
          </div>
          <div className="input-wrap search-small">
            <Icon name="search" />
            <input
              placeholder="뉴스 검색"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
        <div className="news-layout">
          <div className="news-feed">
            <div className="group-note">
              <Icon name="news" />
              <div>
                <b>유사 기사 3건을 하나로 묶었어요</b>
                <span>중복 기사는 대표 기사 중심으로 표시됩니다.</span>
              </div>
              <button disabled title="유사 기사 펼치기 기능은 이후 단계에서 구현합니다">펼쳐보기 (미지원)</button>
            </div>
            {filtered.map((n, i) => (
              <article className="news-row" key={n.title}>
                <div className={`news-thumb n${i}`}>
                  <span>{n.source[0]}</span>
                </div>
                <div className="news-body">
                  <div className="news-meta">
                    <span>{n.type}</span>
                    <b>{n.source}</b>
                    <small>{n.time}</small>
                  </div>
                  <h3>{n.title}</h3>
                  <p>{n.summary}</p>
                  <div>
                    {n.tags.map((t) => (
                      <span className="tag" key={t}>
                        {t}
                      </span>
                    ))}
                    <span className={n.importance === "높음" ? "importance" : "relevance"}>
                      중요도 {n.importance}
                    </span>
                    <span className="relevance">관련성 {i % 2 ? "92" : "98"}%</span>
                  </div>
                </div>
                <button className="icon-button" disabled title="가상 기사에는 원문 링크가 없습니다">
                  <Icon name="external" />
                </button>
              </article>
            ))}
          </div>
          <aside className="ai-summary">
            <div className="ai-head">
              <span>
                <Icon name="shield" />
              </span>
              <div>
                <b>AI 뉴스 브리핑</b>
                <small>오늘 15:30 업데이트</small>
              </div>
            </div>
            <h3>오늘의 핵심 요약</h3>
            <p>
              AI 반도체 수요 기대가 이어지며 관련 종목의 투자 심리가 견조합니다. 국내 시장은 외국인
              수급 개선이 주요 동력입니다.
            </p>
            <ul>
              <li>
                <i />
                반도체 공급 확대 및 업황 회복 기대
              </li>
              <li>
                <i />
                대형 기술주 단기 변동성 확대 가능성
              </li>
              <li>
                <i />
                연준 발언에 따른 금리 민감도 주의
              </li>
            </ul>
            <div className="disclaimer">
              <Icon name="info" />
              <span>AI가 데모 기사를 요약한 내용으로, 중요한 정보는 원문을 확인하세요.</span>
            </div>
          </aside>
        </div>
      </Card>
    </div>
  );
}

function SignalsPage() {
  const [selected, setSelected] = useState(0);
  const items = [
    {
      stock: "삼성전자",
      ticker: "005930",
      kind: "buy" as const,
      label: "매수 검토",
      time: "오늘 14:32",
      title: "단기 추세 전환 및 거래량 증가",
    },
    {
      stock: "NVIDIA",
      ticker: "NVDA",
      kind: "watch" as const,
      label: "관망",
      time: "오늘 11:08",
      title: "RSI 과열 구간 근접",
    },
    {
      stock: "삼성전자",
      ticker: "005930",
      kind: "risk" as const,
      label: "위험 경고",
      time: "2월 13일 10:05",
      title: "장중 변동성 급격히 확대",
    },
    {
      stock: "SPY",
      ticker: "SPY",
      kind: "sell" as const,
      label: "매도 검토",
      time: "2월 12일 23:42",
      title: "단기 지지선 하향 이탈",
    },
  ];
  const active = items[selected];
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <span className="eyebrow">SIGNAL HISTORY</span>
          <h2>신호 · 알림 이력</h2>
          <p>기술적 분석 신호와 알림 전송 상태를 확인하세요.</p>
        </div>
      </div>
      <DemoBanner />
      <div className="signal-layout">
        <Card className="history-card">
          <div className="history-filter">
            <div className="segmented">
              {["전체", "매수", "매도", "경고"].map((x, i) => (
                <button className={i === 0 ? "active" : ""} key={x}>
                  {x}
                </button>
              ))}
            </div>
            <button className="button secondary">
              <Icon name="filter" />
              최근 30일
            </button>
          </div>
          {items.map((x, i) => (
            <button
              className={`history-item ${selected === i ? "active" : ""}`}
              onClick={() => setSelected(i)}
              key={x.time}
            >
              <div className={`signal-symbol ${x.kind}`}>
                <Icon
                  name={
                    x.kind === "buy"
                      ? "arrowUp"
                      : x.kind === "sell"
                        ? "arrowDown"
                        : x.kind === "risk"
                          ? "info"
                          : "clock"
                  }
                />
              </div>
              <div className="history-info">
                <div>
                  <b>{x.stock}</b>
                  <small>{x.ticker}</small>
                </div>
                <h3>{x.title}</h3>
                <span>{x.time}</span>
              </div>
              <div className="history-status">
                <StatusPill kind={x.kind}>{x.label}</StatusPill>
                <small>
                  <i className="sent" /> 이메일 전송
                </small>
                <small>
                  <i className={i === 1 ? "failed" : "sent"} /> Push {i === 1 ? "실패" : "전송"}
                </small>
              </div>
              <Icon name="chevron" />
            </button>
          ))}
        </Card>
        <Card className="signal-detail-panel">
          <div className="panel-head">
            <div>
              <span>신호 상세</span>
              <h2>
                {active.stock} <small>{active.ticker}</small>
              </h2>
            </div>
            <StatusPill kind={active.kind}>{active.label}</StatusPill>
          </div>
          <div className="detail-timestamp">
            <Icon name="clock" />
            <span>발생 시각</span>
            <b>{active.time}</b>
          </div>
          <h3>판단 근거</h3>
          <p>
            {active.kind === "buy"
              ? "주가가 단기 이동평균선을 상향 돌파하고 거래량이 유의미하게 증가했습니다. 단기 추세 회복 가능성을 검토할 수 있습니다."
              : "최근 가격 흐름과 기술적 지표의 방향이 일치하지 않아 추가 관찰이 필요합니다."}
          </p>
          <div className="indicator-table">
            <div>
              <span>지표</span>
              <span>측정값</span>
              <span>판정</span>
            </div>
            <div>
              <b>MA20</b>
              <span>71,820원</span>
              <em className="positive">충족</em>
            </div>
            <div>
              <b>거래량</b>
              <span>평균 대비 1.8x</span>
              <em className="positive">충족</em>
            </div>
            <div>
              <b>RSI (14)</b>
              <span>58.4</span>
              <em>중립</em>
            </div>
            <div>
              <b>MACD</b>
              <span>+412</span>
              <em className="positive">충족</em>
            </div>
          </div>
          <h3>알림 전송</h3>
          <div className="delivery">
            <span>
              <Icon name="news" />
              <b>이메일</b>
              <small>14:32:08 전송 완료</small>
              <i className="sent" />
            </span>
            <span>
              <Icon name="bell" />
              <b>Push</b>
              <small>14:32:10 전송 완료</small>
              <i className="sent" />
            </span>
          </div>
          <div className="disclaimer">
            <Icon name="shield" />
            <span>
              이 신호는 기술적 지표 기반 참고 정보입니다. 실제 매수·매도 결정은 투자자 본인의 판단과
              책임입니다.
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
}

function Toggle({
  value,
  onChange,
  disabled = false,
}: {
  value: boolean;
  onChange: () => void;
  disabled?: boolean;
}) {
  return (
    <button disabled={disabled} className={`toggle ${value ? "on" : ""}`} onClick={onChange}>
      <span />
    </button>
  );
}

function SettingsPage({ dark, setDark }: { dark: boolean; setDark: (v: boolean) => void }) {
  const [settings, setSettings] = useState({
    kr: true,
    us: true,
    email: true,
    breaking: true,
    signals: true,
  });
  const flip = (k: keyof typeof settings) => setSettings({ ...settings, [k]: !settings[k] });
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <span className="eyebrow">PREFERENCES</span>
          <h2>설정</h2>
          <p>알림과 데이터, 화면 표시 방식을 관리하세요.</p>
        </div>
        <button className="button primary" disabled title="디자인 미리보기에서는 설정 저장을 지원하지 않습니다">변경사항 저장 (미지원)</button>
      </div>
      <DemoBanner />
      <div className="settings-layout">
        <div className="settings-main">
          <Card className="settings-card">
            <CardHeader title="시장별 알림" desc="시장 운영 시간과 주요 변동 알림을 설정합니다." />
            <SettingRow icon="KR" title="한국 시장 알림" desc="장 시작·마감 및 보유 종목 변동 알림">
              <Toggle value={settings.kr} onChange={() => flip("kr")} />
            </SettingRow>
            <SettingRow icon="US" title="미국 시장 알림" desc="프리마켓 포함 주요 시장 알림">
              <Toggle value={settings.us} onChange={() => flip("us")} />
            </SettingRow>
          </Card>
          <Card className="settings-card">
            <CardHeader title="알림 채널" desc="수신할 채널과 알림 유형을 선택합니다." />
            <SettingRow icon={<Icon name="news" />} title="이메일 알림" desc="설정되지 않음">
              <Toggle value={settings.email} onChange={() => flip("email")} />
            </SettingRow>
            <SettingRow
              icon={<Icon name="bell" />}
              title="Android Push 알림"
              desc="모바일 앱 출시 후 지원 예정"
              badge="추후 지원"
            >
              <Toggle value={false} onChange={() => {}} disabled />
            </SettingRow>
            <div className="sub-settings">
              <label>
                <input
                  type="checkbox"
                  checked={settings.signals}
                  onChange={() => flip("signals")}
                />
                <span>
                  <Icon name="check" />
                </span>
                매매 검토 신호
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={settings.breaking}
                  onChange={() => flip("breaking")}
                />
                <span>
                  <Icon name="check" />
                </span>
                중요 뉴스 속보
              </label>
            </div>
          </Card>
          <Card className="settings-card">
            <CardHeader title="뉴스 알림 빈도" desc="관련 뉴스 요약을 받아볼 주기를 설정합니다." />
            <div className="frequency-grid">
              {["실시간", "하루 1회", "주 1회", "받지 않음"].map((x, i) => (
                <button className={i === 1 ? "active" : ""} key={x}>
                  <span>{x}</span>
                  <small>
                    {["중요 뉴스 즉시", "매일 오후 6시", "매주 금요일", "앱에서만 확인"][i]}
                  </small>
                  {i === 1 && <Icon name="check" />}
                </button>
              ))}
            </div>
          </Card>
        </div>
        <aside className="settings-side">
          <Card>
            <CardHeader title="화면 테마" />
            <div className="theme-select">
              <button className={!dark ? "active" : ""} onClick={() => setDark(false)}>
                <div className="theme-preview light">
                  <span />
                  <i />
                  <i />
                  <i />
                </div>
                <span>
                  <Icon name="sun" />
                  라이트
                </span>
              </button>
              <button className={dark ? "active" : ""} onClick={() => setDark(true)}>
                <div className="theme-preview dark">
                  <span />
                  <i />
                  <i />
                  <i />
                </div>
                <span>
                  <Icon name="moon" />
                  다크
                </span>
              </button>
            </div>
          </Card>
          <Card>
            <CardHeader title="데이터 공급원" />
            <div className="provider">
              <span className="provider-logo">D</span>
              <div>
                <b>데모 마켓 데이터</b>
                <small>
                  <i className="status-dot live" /> 정상 연결
                </small>
              </div>
            </div>
            <div className="provider-detail">
              <span>
                마지막 동기화<b>3분 전</b>
              </span>
              <span>
                국내 시세<b>20분 지연</b>
              </span>
              <span>
                미국 시세<b>15분 지연</b>
              </span>
            </div>
            <button className="button secondary full">
              <Icon name="refresh" />
              연결 상태 확인
            </button>
          </Card>
          <div className="settings-note">
            <Icon name="shield" />
            <p>
              <b>개인정보 및 데이터 안내</b>
              <span>본 프로토타입은 실제 계좌 정보나 개인정보를 저장하지 않습니다.</span>
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

function SettingRow({
  icon,
  title,
  desc,
  badge,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="setting-row">
      <span className="setting-icon">{icon}</span>
      <div>
        <b>
          {title}
          {badge && <em>{badge}</em>}
        </b>
        <small>{desc}</small>
      </div>
      {children}
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [menu, setMenu] = useState(false);
  const [dark, setDark] = useState(false);
  const title = useMemo(() => navItems.find((n) => n.page === page)?.label || "대시보드", [page]);
  const go = (p: Page) => {
    setPage(p);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  return (
    <div className={dark ? "app dark" : "app"}>
      <Sidebar page={page} setPage={go} open={menu} setOpen={setMenu} />
      <main className="main">
        <Topbar title={title} setMenu={setMenu} dark={dark} setDark={setDark} />
        <div className="content">
          {page === "dashboard" && <Dashboard go={go} />}
          {page === "stocks" && <StocksPage go={go} />}
          {page === "detail" && <DetailPage go={go} />}
          {page === "news" && <NewsPage />}
          {page === "signals" && <SignalsPage />}
          {page === "settings" && <SettingsPage dark={dark} setDark={setDark} />}
        </div>
      </main>
    </div>
  );
}
