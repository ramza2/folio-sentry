# Phase 1 P1 — 개인 보유·관심 종목 CRUD (GitHub 구현 / 운영 미적용)

작성: 2026-11-19. 범위는 **수동 종목 등록 + 단일 소유자 보유/관심 목록 API**이며,
미니PC 운영 환경·공개 HTTPS·Frontend는 변경하지 않는다.

## 구현 파일과 보호 범위

- `backend/app/portfolio_models.py`: `instrument`, `tracked_instrument` 모델. `(exchange_mic, normalized_symbol)` 유니크; 각 종목은 HOLDING 또는 WATCH 중 하나만 등록.
- `backend/migrations/versions/20261119_portfolio01.py`: `20261119_auth01` 뒤에 추가되는 Alembic revision. **업그레이드 자동 실행 없음**. 운영 데이터 삭제를 유발하는 downgrade 거부.
- `backend/app/portfolio_api.py`: `/api/v1/instruments`, `/api/v1/tracked` API. 기존 미들웨어의 쿠키 세션/Origin/CSRF 보호를 그대로 적용.
- `backend/tests/test_portfolio.py`: 실 계정·데이터 없이 격리 SQLite 테스트, GitHub Actions 분리된 PostgreSQL 17 마이그레이션/SQL 회귀.
- MiniPC에서는 Git fetch/PR 병합만으로 테이블이나 API가 바뀌지 않는다. 운영 마이그레이션/Backend 배포는 **별도 승인·안전 점검 이후**에만 실행한다.

## 인증된 API (GitHub 코드에만 구현)

| 요청 | 경로 | 용도 |
|---|---|---|
| POST | `/api/v1/instruments` | 주식·ETF 종목 직접 등록(수동, 공급자 미검증) |
| GET | `/api/v1/instruments?q=&market=&asset_type=&cursor=&limit=` | 등록된 종목 검색 및 페이지 조회 |
| GET | `/api/v1/instruments/{id}` | 종목 조회 |
| GET | `/api/v1/tracked?kind=&cursor=&limit=` | 보유/관심 등록 조회 |
| POST | `/api/v1/tracked` | 등록 |
| PATCH | `/api/v1/tracked/{id}` | 분류/수량/평균단가/메모/알림 선호 수정 |
| DELETE | `/api/v1/tracked/{id}` | 추적 목록 레코드만 삭제(종목 카탈로그는 유지) |

예시(가상 식별자·가격이며 실 자산정보 아님):

```json
{
  "market": "KR",
  "exchange_mic": "XKRX",
  "symbol": "000001",
  "name": "예시 종목",
  "asset_type": "STOCK"
}
```

수동 등록은 사용자 입력 문자열만 기록한다. 실제 거래소 소속·회사명·거래 가능 상태를 확인하지 않으므로 `source: "MANUAL_UNVERIFIED"`를 반환한다. 공급자 API 또는 증권사 연결이 없는 현 단계에서 종목 자동 검색/실 시세를 제공한다고 표시하지 않는다. KR은 6자리 숫자 코드·`XKRX|XKOS`, US는 `XNAS|XNYS|XASE`의 영문/숫자/점/하이픈 심볼을 수동 입력받는다. 통화/타임존은 시장별로 서버에서 결정한다.

등록 예시:

```json
{
  "instrument_id": "10000000-0000-4000-8000-000000000001",
  "kind": "HOLDING",
  "quantity": "3.125",
  "average_cost": "75000.50",
  "alerts_enabled": true,
  "memo": null
}
```

- `HOLDING`: 수량 NULL 또는 양수, 평균단가 NULL 또는 0 이상(평균단가 지정에는 수량 필수).
- `WATCH`: 수량/평균단가는 반드시 NULL. `HOLDING → WATCH` 변경 시 보유 수치 삭제.
- 수량·평균단가는 **JSON 숫자가 아닌 문자열**만 허용. 소수 최대 8자리, `NUMERIC(24,8)`. 응답은 소수 8자리 문자열로 통일.
- 미연결 시세: 모든 등록 종목에 `quote.status="UNAVAILABLE"`, `close=null`, `market_value=null`, `unrealized_pnl=null`. DEMO 가격·손익과 섞지 않는다.
- 초기 `alerts_enabled`는 선호 설정 저장만 의미하며, 알림 발송은 아직 **미구현**.
- 목록은 `limit` 기본 20/최대 100, UUID 기반 `next_cursor`. 동일 종목 재등록은 409.
- 수동 데이터 입력에는 로그인 세션, 허용된 Origin, `X-CSRF-Token`이 필요. 인증 없는 읽기 401, Origin/CSRF 위반 403.

## 후속 우선순위

1. **UI-03**: 기존 DEMO 화면은 그대로 보존하면서 별도 '실제 등록 종목' 화면에 수동 등록·조회·수정·삭제 UI 연결. 오류/미등록/시세 없음 표현 검증.
2. 시세 제공자 비교/선택 후 검증된 종목 카탈로그 검색, 실제 KR·US 가격 조회, 휴장/지연/수정 주가 규칙 수립.
3. 실 데이터와 DEMO 데이터는 명시적 분리; 시세/뉴스/AI가 확보되기 전 임의 값 생성 금지.

## 운영 배포 안전

- 이 PR은 **DB 스키마를 추가하는 코드**일 뿐 운영 MiniPC의 DB/볼륨을 변경하지 않는다. 자동 Alembic 실행/테이블 생성/seed 금지.
- 실제 배포를 하려면 별도 승인 후 현재 운영 revision 조회 → 검증된 신규 additive revision만 격리 환경에서 검증 → 운영 마이그레이션과 Backend/Frontend 전환을 각각 구분.
- 운영 백업 자동화는 사용자가 **명시적으로 비활성화**했으며 이 PR에서 다시 enable/start 하지 않는다.
- 기존 Traefik, PickNext, 서버 시스템 설정 및 현재 인증 쿠키를 변경하지 않는다.
