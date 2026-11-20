# MD-03 — 국내·미국 일봉 보관 경계 (2026-11-20)

상태: **GitHub 개발·격리 CI 전용. 집 MiniPC 운영 DB 마이그레이션 금지.**

## 목표와 사전 결과
- 2026-11-20 사용자 승인하에 실전 KIS 토큰 1회, 국내 삼성전자·미국 애플 일봉 각각 1건 응답 및 구조 정규화 성공. 시세 가격/확정 여부는 아직 검증되지 않았다.
- PR #24(일회성 조회·비밀파일)와 PR #25(공유 토큰 상태)는 **둘 다 Draft 및 미병합**. MD-03은 main의 기존 순수 정규화 계약 위에 **독립 PR**로 작성한다. PR 간 코드를 결합하거나 MiniPC에 자동 반영하지 않는다.

## 국내·미국 세션 처리 (결정론적 최소 조건)
- 거래소 지역 날짜로 `session_date` 보존, `fetched_at`은 timezone-aware UTC. KRX 정규장 09:00–15:30 KST, 미국 거래소 표준 정규장 09:30–16:00 ET을 참고하되 **종료 + 2시간**은 단순 보수적 대기 조건일 뿐 확정가격의 증거가 아니다.
- 미국 DST는 Python `ZoneInfo("America/New_York")`로 계산. UTC를 임의로 매번 -5시간/-4시간 고정하지 않는다.
- 미래 거래일·주말 거래일·장마감+2시간 이전 취득·24시간 초과 오래된 수집·시간대 미지정·미래 수집시각(5초 오차 초과) 거부. 주중이어도 휴장일·조기종료일·이상 거래일일 수 있으므로 **공식 확인된 거래소 일정/제공자 관측시간·정산 조건이 없으면 `is_final=False` 유지**.
- 달력 API/장중 가격 API/외부 네트워크/AI 사용 없음. 날짜·출처·시점을 검증하는 함수는 순수 오프라인 코드.

공식 참고: [KRX 국내주식 거래시간](https://global.krx.co.kr/contents/GLB/06/0602/0602020204/GLB0602020204T1.jsp), [NYSE 거래시간 및 휴장·조기종료 일정](https://www.nyse.com/trade/hours-calendars). 거래소 정규장 시간이 맞더라도 KIS 값의 최종성을 증명하지는 않는다.

## 신규 price_bar 스키마 (운영 미적용)
- Alembic `20261120_pricebar01` → 부모 `20261119_portfolio01`의 **추가형 migration**. `instrument`·`tracked_instrument`와 인증 테이블 변경 없음. 기존 데이터에 seed/UPDATE/DELETE 없음. downgrade는 기록 손실 위험으로 기본 거부.
- `instrument_id` FK, `1d`, 로컬 세션 날짜, `RAW/ADJUSTED`, Decimal `NUMERIC(24,8)` OHLC, 거래량 `NUMERIC(28,0)`, 공급자 `KIS`, UTC fetched_at, 관측시각(nullable), is_final, quality_status.
- UNIQUE: `(instrument_id, timeframe, session_date, price_basis, source)`. FK는 instrument 삭제 시 RESTRICT.
- DB CHECK로 **`quality_status='PARTIAL'`, `is_final=false`, `source_observed_at IS NULL`**만 허용. OHLC·0 이상 거래량·price basis·source 역시 CHECK. 미래 단계에서 확정시세를 승인하려면 **새로운 검증 절차와 별도 schema migration**이 필요하다.

## 멱등 저장 정책
- `app.price_quality.validate_batch`: 장마감 보수조건·Decimal 정밀도/범위·OHLC 일관성/출처/시간대/중복 검증. 적합한 후보도 `UnverifiedPriceBar`로만 반환.
- `app.price_repository.insert_unverified_daily_batch`: 기본 `allow_write=False`. 주입된 SQLAlchemy Session으로만 실행, 자체 DB 연결/commit 없음, 단일 배치 선검증 후 PostgreSQL `INSERT ... ON CONFLICT DO NOTHING`.
- 동일 key + 동일 가격/거래량 재입력은 NOOP(기존 fetched_at 유지). 동일 key로 **달라진 가격/거래량은 오류로 중단**, 무단 수정주가 덮어쓰기 불가. 외부 트랜잭션에서 전체 롤백.
- `analysis_eligible`은 MD-03에서 항상 False. **신호·보유 손익·UI 표시·알림·실제 시세 제공에 사용 금지**. 기존 `quote.status=UNAVAILABLE` 유지.

## 격리 검증 및 운영 분리
- 백엔드 pytest는 합성 일봉과 결정론적 시간만 사용해 기간·DST·주말·미래·오래된 수집·OHLC·권한 차단 검사.
- GitHub Actions 별도 생성된 `folio_ci` PostgreSQL에서만 `alembic upgrade head` 및 `scripts/test_price_bar_isolated_ci.py` 실행. **전용 변수, host=127.0.0.1, DB/user=folio_ci** 동시 조건 불충족 시 즉시 중단. 인위적 종목/일봉 INSERT → 중복 NOOP → 충돌 차단 → DB CHECK 최종시세 차단 → ROLLBACK 후 테이블 건수 0 확인.
- 실제 MiniPC는 `20261119_portfolio01`에서 머무르도록 유지한다. `alembic upgrade head`를 MiniPC에서 실행하지 않는다. 기존 백업 타이머/Traefik/PickNext/Compose/운영 API/Frontend/실 KIS 토큰을 건드리지 않는다.

## 다음 단계로 넘어가는 게이트
1. PR #24/#25 병합 여부와 공유토큰 설계/권한 검토, 합성 CI 및 MD-03 코드 리뷰
2. 휴장·조기 종료·KIS 원주가/수정주가/정산 확정 정책을 공식 데이터로 재검증
3. 운영 DB 백업·별도 복원 검증 후 **사용자 명시 승인**으로 migration 및 배포
4. 가격 실제 표시·손익·신호 개방은 별도 승인 + 확정 검증 데이터 공급 이후

## MD-03B 거래일별 증빙 기반 일정 예외 — 2026-11-20
- **기존 결함 보정:** 2026-11-19 KRX 정규장 시각은 평소 09:00~15:30이 아닌 **10:00~16:30 KST**. 한국거래소 KIND 시장운영 안내에 근거하며, 종전 하드코딩 15:30을 제거했다.
  - KOSPI: https://kind.krx.co.kr/external/2026/11/05/000141/20261105000216/99303.htm
  - KOSDAQ: https://kind.krx.co.kr/external/2026/11/05/000145/20261104001218/70780.htm
- 미국 NYSE·Nasdaq 공식 일정에 따른 2026-11-26 Thanksgiving **휴장**, 2026-11-27·12-24 **13:00 ET 조기 종료**를 명시했다. NYSE: https://www.nyse.com/trade/hours-calendars / Nasdaq: https://www.nasdaq.com/market-activity/stock-market-holiday-schedule
- `backend/app/exchange_calendar.py`는 **공식 자료로 개별 확인한 일부 날짜에 대한 좁은 화이트리스트**만 제공한다. 전체 2026 거래일 달력이 아니며, 모르는 날짜는 `PRICE_SESSION_CALENDAR_UNVERIFIED`로 차단한다. 주중이라고 자동 개장으로 간주하지 않는다.
- 확인된 날짜도 장 종료 + 2h 뒤 수집이라는 최소 조건만 만족할 수 있다. KIS 최종 종가·원주가/수정주가·기업행동·출처 관측시간 증빙이 없어 `PARTIAL`만 유지한다. 휴장·조기종료 자료는 예고 없이 변경될 수 있으므로 운영시에는 증빙 갱신 정책이 필요하다.
- 적용 범위는 **MD-03 Draft PR 코드와 오프라인 합성 테스트**뿐. KIS 실제 조회/토큰 재발급/운영 DB 배포/스케줄러 사용 없음.
