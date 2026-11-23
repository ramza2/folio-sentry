# Phase 1A — REST API 계약 (설계, 2026-11-18)

## 적용 범위
이 문서는 **Phase 1 이후 구현할 정식 API 경로를 설계**한 계약이다. 실제 코드로 구현된 경로와 혼동하지 않는다.

**현재 구현된 경로**:
- `POST /api/v1/auth/login`: 소유자 비밀번호 확인, HttpOnly 세션 쿠키 발급 (Origin 필요)
- `GET /api/v1/auth/me`: 유효한 세션/CSRF 토큰 상태 확인
- `POST /api/v1/auth/logout`: Origin 및 X-CSRF-Token 검사 후 세션 폐기
- `/api/v1/*`는 **로그인 API 외 모두 인증 필수**, 데모 데이터 포함. 자동 OpenAPI/Swagger 외부 경로 비활성화.
- `GET /api/health/live`, `GET /api/health/ready`
- `GET /api/v1/demo/instruments` (Phase 0)
- `GET /api/v1/demo/overview` (Phase 1A: 시각화/디자인용 고정 가상 데이터)

**Phase 1 P1 GitHub 구현(운영 미적용)**: `POST/GET /api/v1/instruments`, `GET /api/v1/instruments/{id}`, `GET/POST /api/v1/tracked`, `PATCH/DELETE /api/v1/tracked/{id}` (직접 입력한 수동 종목 메타데이터, 전용 DB 마이그레이션은 미승인·미실행).

정식 `/api/v1/dashboard` 및 실 거래소 자동 종목 검색/시세 조회는 여전히 미구현이다. 상세: `docs/PHASE1_PORTFOLIO_CRUD.md`.

## 공통 규칙
- REST JSON; 경로 `/api/v1`; ISO 8601 UTC timestamp와 거래소 현지 `YYYY-MM-DD` 세션 날짜.
- 금액·수량·%는 손실 없는 **10진 문자열**(`"125000.00"`)로 반환. 프론트에서 통화별 형식화.
- 데이터 가용성은 `CURRENT / STALE / UNAVAILABLE / DEMO`로 분리. `as_of`, `source` 별도 제공.
- API는 개인 접근 통제 뒤에만 제공. 정식 개인 정보/보유 정보 엔드포인트의 비인증 노출 금지.
- 인증 완료 전 모든 개인 데이터 요청 차단; POST/PATCH/DELETE는 허용 출처 Origin + X-CSRF-Token 검사.
- 세션은 8시간 절대 만료·30분 미활동 만료. 네트워크/세션 오류 시 이전 수치로 자동 대체 금지.
- 목록 응답은 `items`와 `next_cursor`(없을 경우 null). 기본 20개/최대 100개. 신호·뉴스 시간 역순.
- 오류 응답: `{"error":{"code":"...","message":"...","request_id":"..."}}`; 대표 상태 400/401/403/404/409/422/429/503.
- `DELETE`는 데이터 파괴를 수반하는 작업은 요청하지 않으며, 대상 사용자 등록 레코드만 제거.
- 주식 주문 관련 POST/DELETE 경로 없음.

## 계획 API

| Method | Path | 목적 | Phase |
|---|---|---|---|
| GET | /api/v1/dashboard | 보유·관심 종목, 시그널/뉴스 요약 | 1 |
| GET | /api/v1/instruments?q=&market=&asset_type= | 심볼/회사명 검색 | 1 |
| GET | /api/v1/instruments/{id} | 종목 메타데이터 | 1 |
| GET | /api/v1/tracked?kind= | 보유·관심 등록 목록 | 1 |
| POST | /api/v1/tracked | 등록(종목ID + HOLDING/WATCH 등) | 1 |
| PATCH | /api/v1/tracked/{id} | 분류/수량/평균단가/알림 설정 변경 | 1 |
| DELETE | /api/v1/tracked/{id} | 사용자의 목록에서만 제거 | 1 |
| GET | /api/v1/instruments/{id}/price-bars?timeframe=1d&limit=180 | 일봉·수정 기준·시세 상태 | 1 |
| GET | /api/v1/instruments/{id}/indicators?strategy_version= | 지표 스냅샷 | 2 |
| GET | /api/v1/instruments/{id}/signals | 해당 종목 신호 이력 | 2 |
| GET | /api/v1/signals | 전체 종목 신호 이력 | 2 |
| GET | /api/v1/instruments/{id}/news | 관련 뉴스·중복 그룹 | 3 |
| GET | /api/v1/news | 모든 등록 종목 뉴스 | 3 |
| GET | /api/v1/alerts | 알림 발송 이력 | 3 |
| GET | /api/v1/settings | 개인 알림 설정 | 3 |
| PATCH | /api/v1/settings | 이메일/FCM 및 알림 수준 설정 | 3/4 |

### 등록 요청 예시(계획)
```json
{
  "instrument_id": "10000000-0000-4000-8000-000000000001",
  "kind": "HOLDING",
  "quantity": "10",
  "average_cost": "70000",
  "alerts_enabled": true
}
```
- `kind=WATCH`인 경우 수량/평균단가는 null만 허용.
- `kind=HOLDING`은 수량/평균단가를 모를 경우 null 허용하되 수량이 양수일 때만 평가액 계산.
- 유니크 종목 1개에 등록 엔트리 1개. 이미 등록된 종목을 재등록하면 409.

## Design Preview API: /api/v1/demo/overview
- **실시세/실제 보유/실제 뉴스/매매 분석이 전혀 아닌 고정 예시 데이터**.
- 루트 `mode: "DEMO"`, `disclaimer`, `as_of` 포함.
- `summary`: registered_count, holding_count, watch_count, available_signal_count.
- `tracked`: instrument + kind + quantity + average_cost + quote + market_value + unrealized_pnl, unrealized_pnl_percent.
- `news`: title, publisher, published_at, url, instrument_id, category.
- `signals`: type, reason, status, evidence, strategy_id, strategy_version, as_of_session.
- 클라이언트에 DEMO 배지와 **"실제 시세·매매 신호가 아닙니다"** 경고 필수.
- Figma Make에는 응답 구조만 참고하고 자체 로컬 mock data로 디자인하도록 요청. 이 API를 실제 투자 분석 API로 취급 금지.

## 예외 및 화면 규칙
- 미국 시세는 거래소 기준 장 마감과 서머타임을 고려한다. 한국과 미국 거래일/현재 시각을 동일하게 취급하지 않는다.
- `quote.status=UNAVAILABLE`일 때 `close`, `change_pct`는 null. 화면에는 “시세 없음” 표시.
- stale이면 저장된 마지막 수치를 보여줄 수 있지만 **지연 상태/시각 강조**, 신규 매매 신호는 억제.
- 뉴스가 0건이라도 오류와 정상적인 기사 없음은 구분.
- `signal.state=SUPPRESSED`는 데이터 오류 등으로 신호 발행을 보류한 상태이며 실제 매매 권유가 아니다.
- 사용자의 보유 손익, 거래내역은 프로토타입에서만 허구의 값 사용. 생성형 AI가 임의 실거래 내역을 생성하지 않는다.

## 검증 기준
1. JSON schema에서 `market`, `exchange_mic`, `currency`, `asset_type` 구분.
2. Decimal 금액이 JSON number가 아닌 문자열로 응답.
3. 모의 데이터와 실데이터 분리, mock 배지 누락 금지.
4. STALE/UNAVAILABLE 시 상태 정확히 표기, 누락 수치를 0으로 변환 금지.
5. 모든 뉴스에는 출처/발행 시각/원문 URL.
6. 모든 신호에는 근거/평가시각/전략 버전, 순수 조건 규칙과 AI 해설 분리.
7. 후속 구현 PR에서 OpenAPI 스키마·테스트를 이 문서에 맞추고 위반 시 변경 이유를 기록.

## Phase 1 P1 보충 계약 (2026-11-19, 구현/운영 분리)
- `POST /api/v1/instruments`: `market` KR/US, `exchange_mic` 수동 지정, `symbol`, `name`, `asset_type` 필요. `source="MANUAL_UNVERIFIED"`. 통화/시간대 서버 결정. 중복 MIC+심볼 409.
- `GET /api/v1/instruments`는 **자체 수동 카탈로그 검색**이며 거래소/브로커 종목 자동 검색이 아니다.
- `GET /api/v1/tracked`: 연결된 실제 가격 원천이 없어 모든 실 등록 종목의 `quote.status=UNAVAILABLE`, `market_value/unrealized_pnl=null`. DEMO 값 사용 금지.
- `POST/PATCH /api/v1/tracked`: 수량/평균 단가 JSON 문자열, 소수 최대 8자리. 응답 문자열 소수 8자리. `WATCH`로 변경 시 수량·평균단가 제거. `alerts_enabled`는 알림 전송 기능이 아닌 **희망 설정 저장**에 그침.
- 이 구현은 GitHub PR·격리 CI 단계이며 운영 DB에 `20261119_portfolio01` 마이그레이션을 자동 적용하지 않는다.


## MD-04C1 보완 계약 — 인증 실제 종목 비가격 품질 상태 (2026-11-23)
- Phase 1의 실제 종목 CRUD는 운영 배포 완료. 그러나 실 KIS 시세·price_bar 저장/조회/손익 계산은 **운영 미연결**이다. 위 표의 실가격/가격-bars API는 여전히 계획만 된 경로다.
- GET /api/v1/tracked의 **기존 운영 응답은 UNAVAILABLE/모든 quote 가격 필드 null/모든 손익 null**로 그대로 유지.
- 향후 상태 전용 확장에 대해 클라이언트는 UNAVAILABLE, UNFINALIZED, STALE, ERROR 네 상태만 잠정 지원. 모든 상태에서 quote는 정확히 status, close, change_pct, as_of, source 5개 키이며 마지막 네 값은 null. market_value, unrealized_pnl, unrealized_pnl_percent도 반드시 null.
- CURRENT, VALID, DEMO, 값이 있는 close/change_pct, null이 아닌 source/as_of, 추가적인 quote 키/승인 플래그 모두 **fail-closed**. STALE도 마지막 가격 수치 표시 금지. UI는 시세 없음/종가 미확정/오래된 시세/시세 확인 실패와 손익 미계산 텍스트만 출력.
- 기존의 'stale이면 수치 표시 가능' 문구는 장래의 최종 검증 가격 정책을 위한 과거 계획이므로 **현재 MD-04C1에서는 적용하지 않는다**.
- Backend 순수 masked_quote_from_finality 함수는 임의 출처 최종성 승인이 아니라 UNAVAILABLE/UNFINALIZED 상태 전용 규격 검사일 뿐, 현재 API 라우터에 미연결. 모든 실 API 호출은 기존 인증 게이트·캐시 금지 유지, DEMO fallback 금지.
- 운영 연동/price_bar migration/실제 시세 공개/알림은 별도 사용자 승인. 세부 docs/MD04C1_QUALITY_UI_CONTRACT.md.


## MD-04C2 인증 상태 전용 GET (2026-11-23 / 코드 준비, 미배포)
- GET /api/v1/tracked/{tracked_id}/quote-status: 기존 단일 소유자 로그인 세션 필수, 존재하는 활성 실제 종목에만 200.
- 응답은 tracked_id(요청한 UUID) 및 quote 2개 필드만 사용; quote는 status=UNAVAILABLE, close/change_pct/as_of/source=null. 경제적 값/보유량/매입가/원천시각/가격근거/DEMO 반환하지 않음.
- 401 비인증, 404 비존재, 422 UUID 잘못됨, 503 기존 종목 DB 접속 장애; error JSON은 기존 계약. Cache-Control no-store, Vary Cookie.
- 가격테이블 및 KIS 조회 없이 기존 instrument/tracked 테이블의 존재만 SELECT. 이전 Phase 1A의 STALE 가격 허용 계획은 이 구현에 적용되지 않는다.
- 프론트 개별 상태 확인 버튼은 클릭 시에만 이 GET을 호출하며, tracked_id 불일치/추가 필드/비null 가격/원천 등은 오류로 차단. 기존 실 종목 목록은 변화 없음.
- 현재 실제 백엔드 배포에는 포함되지 않았다. 코드 PR/CI PASS가 운영 API 존재 또는 live 시세를 의미하지 않음. 상세 docs/MD04C2_AUTH_QUOTE_STATUS.md.
