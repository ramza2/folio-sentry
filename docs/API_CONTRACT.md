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

정식 `/api/v1/dashboard`, `/api/v1/instruments` 등의 응답은 향후 구현 예정이다.

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
