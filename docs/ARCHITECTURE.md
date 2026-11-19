# FolioSentry 아키텍처 (초기 초안)

## 원칙
집의 개인 MiniPC에 단일 배포·모노레포·최소 인프라. 확장성을 위해 데이터 공급자와 신호 알고리즘을 분리하되, 추상화를 과도하게 늘리지 않는다.

## 구성
```text
Market Data Adapter ─┐
                     ├── FastAPI + scheduler ── PostgreSQL
News Provider Adapter┘          │                    │
                               ├── Indicator/Signal Engine
                               ├── Alert Outbox ── Email (MVP) / FCM (later)
                               └── Read API ── React UI

AI News Explainer (later): optional external ModelOps Gateway API
  └── Gateway 미연결/장애 시 단순 뉴스 원문과 규칙 신호는 정상 제공
```

- `backend/`: FastAPI, SQLAlchemy, Alembic, 수집/스케줄링, 분석, 알림
- `frontend/`: React + TypeScript, 차트, 검색/등록, 종목/뉴스/신호 표시
- `infra/`: Docker Compose 및 설정 예시 (구현 단계에서 생성)
- `docs/`: 요구사항, 설계, 작업 순서
- PostgreSQL 하나로 MVP 데이터와 alert outbox를 관리; Redis 등 별도 브로커 보류
- 스케줄러는 단일 프로세스만 활성화하며 중복 실행 방지 잠금 사용
- 운영 실행 위치는 **개인 가정용 MiniPC**. 회사 GPU 서버에 이 서비스/DB를 올리지 않는다.
- 실제 LLM 추론은 필요 시 **외부 ModelOps Gateway API**로 호출. 개인 MiniPC에는 LLM 모델/GPU 의존성을 배치하지 않는다.
- Gateway는 adapter+timeout+제한적 재시도+호출량 예산+비활성화 스위치로 격리. AI 해설 실패가 규칙 신호·뉴스 원문 표시를 막아서는 안 된다.
- ModelOps Gateway가 회사 운영 자산인 경우 개인 사용 권한·개인정보/기사 전송 가능 여부를 반드시 사전 확인한다.

## 주요 엔티티 (개념)
- `instrument`: id, market, exchange, symbol, currency, name, active
- `watchlist_entry`: instrument_id, kind(HOLDING/WATCH), quantity?, avg_cost?, enabled
- `price_bar`: instrument_id, timeframe, session_date, OHLCV, adjusted?, source, captured_at, completeness
- `indicator_snapshot`: instrument_id, as_of_session, indicator_values, calculation_version
- `signal_event`: instrument_id, as_of_session, signal_type, severity, strategy_id/version, evidence, data_status, created_at
- `news_article`: source, source_article_id?, canonical_url, published_at, title, description?, language, fetched_at, dedup_key
- `news_instrument_link`: article_id, instrument_id, relevance, match_evidence
- `alert_delivery`: signal/event_key, channel, status, attempts, last_error, sent_at
- `provider_sync_run`: provider, scheduled_at, finished_at, status, error_code, data_watermark

## 데이터 규칙
- 종목 키: `(exchange, symbol)` 유니크, 시장/통화 분리. 심볼만으로 조인 금지.
- DB 타임스탬프 UTC; 세션 일자는 거래소 로컬 달력 기준. 한국/미국 정규장 및 DST 처리.
- 공급자별 canonical mapping, rate limit, 백오프, 중복 요청 캐시.
- 시세 누락·비정상·미확정·지연은 신호 계산 불가 상태로 표기.
- 일봉은 수정주가 정책을 일관되게 적용하고 원천 데이터 및 조정 여부 저장.
- 뉴스는 출처·원문 링크·발행 시각을 유지하고, 키워드 매칭 오탐(동명이인/기업명 중복)을 필터링.
- API 키, 뉴스 전문, 개인 보유 정보 등 불필요한 민감 데이터는 로그에 남기지 않음.

## 신호 엔진
1. 완결된 캔들/시세 최신성 확인
2. 동일 입력에 동일 지표를 산출하도록 버전 관리
3. 결정론적 규칙 평가 (상충 신호/관망 처리 포함)
4. `signal_event` 근거와 전략 버전 보관
5. 중복키 `instrument + strategy_version + signal_type + session_date`로 알림 멱등성 보장
6. 알림 전송 실패 시 제한된 재시도, 전송 이력 보존
7. AI 출력은 기록된 신호·뉴스에 대한 설명으로만 사용하며 규칙을 덮어쓰지 않음

## 데이터 공급자 — 후보, 미확정
- 시세: 한국투자증권 Open API를 국내·미국 통합 1순위 후보로 검증.
- 국내 뉴스: NAVER API HUB 검색 API 후보.
- 미국 뉴스: Alpha Vantage 또는 Finnhub 후보.
- 무료/조회 가능 범위, 과거 데이터, 라이선스, 레이트리밋을 실증하기 전 공급자 확정 금지.
- 공급자 장애를 다른 공급자로 전환하려면 동일 데이터 정의/품질을 검증한 뒤 허용.

## 보안과 접근
- 개인용이라도 인증을 생략해 인터넷에 노출하지 않는다. 로컬/LAN 또는 인증된 프록시 뒤에 제공.
- 비밀정보는 환경변수/비밀 저장소, 예시 파일에 실제 값 금지.
- 주식 주문 API 호출·주문 권한 저장 금지.
- 배포/마이그레이션 전 DB 백업·복구 확인.
- 뉴스/시세 이용약관 위반이 없도록 사용량과 출처를 기록.

## 가정 MiniPC 운영 설계
- Docker Compose 별도 프로젝트/볼륨/네트워크; 다른 홈 서비스와 리소스와 포트가 충돌하지 않도록 확인.
- API/웹 포트는 개발 단계와 마찬가지로 loopback에만 바인딩. 원격 접속은 VPN(예: Tailscale) 또는 인증된 프록시를 별도 검토한 뒤 개방.
- DB는 외부 포트로 노출하지 않음. API 비밀정보, 개인 보유 내역 및 Gateway 키를 로그/이미지/저장소에 저장하지 않음.
- PostgreSQL 백업·복원 점검, 컨테이너 재시작/헬스체크, 디스크 보존 정책, 간단한 자원 제한과 모니터링 도입.
- 가정용 MiniPC 사양·OS·기존 서비스·스토리지·접속 방식·사용 포트는 미확정이므로 **실제 배포 및 운영 파라미터 결정 전 확인**.
- 상세: `docs/DEPLOYMENT_TARGET.md`.

## 검증 및 결정 필요
- API 공급자 조사 이후 adapter 계약과 수집 주기 결정
- MiniPC 사양/OS/공존 서비스·실제 포트/접속 방식/알림 수신 채널 결정
- ModelOps Gateway의 개인 사용 허용 여부, endpoint/API 인증/데이터 전송 범위 및 장애시 fallback 검증
- 신호 평가 기준(단일 전략 vs 복수 전략) 및 가상 데이터 fixture 정의
- 사용자 로그인/접근 제어 방식 확정
