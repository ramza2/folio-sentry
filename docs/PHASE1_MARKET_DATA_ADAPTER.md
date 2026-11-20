# Phase 1 MD-01 — 국내·미국 시세 공급자 조사와 일봉 정규화 경계

기준: 2026-11-20. **코드·격리 테스트만 개발**, MiniPC 운영 DB·Backend·Frontend·스케줄러 변경 없음.

## 1. 현재 공급자 비교 (공식 자료 중심)

| 공급자 | KR (KRX/KOSDAQ) | US | 적용 조건 / 주의 |
|---|---|---|---|
| [한국투자증권 KIS Open API](https://apiportal.koreainvestment.com/about-howto) | 국내 시세·일봉 API 존재 | 해외 시세·일봉 API 존재 | 한국투자증권 계좌와 Open API 신청으로 APP Key·Secret 발급. 최초 실 호출, 데이터 사용 권한, 초당 호출 제한을 계정별로 확인할 것 |
| [Twelve Data](https://twelvedata.com/exchanges) | XKRX·XKOS EOD, **Pro 등 유료 플랜** | Basic 무료 플랜 미국 주식 실시간 데이터 | [가격](https://twelvedata.com/pricing): 무료 Basic 일 800 API 요청 안내. 미국 데이터가 거래소 전체 통합 호가와 같은 수준인지 별도 확인. 재배포/재전송 권한 별도 |
| [Alpha Vantage](https://www.alphavantage.co/support/) | 현 시점 KR 커버리지/가격 확정 불가 | 미국 주식 데이터 | API 키 기반, 무료 조건 및 KR 커버리지 추가 검증 필요 |

**추천 1순위: KIS (단일 개인 계좌 기반 KR+US)**. 계좌·APP 키 확보 가능 여부는 아직 모른다. KIS 사용이 어렵다면 Twelve Data 미국 무료 + 국내 별도 합법 공급원(또는 유료 플랜)으로 재검토한다. 어떤 공급자도 사용자 승인 없이 활성화하지 않는다.

KIS 공식 [Open API 포털](https://apiportal.koreainvestment.com/apiservice), [공식 예제 저장소](https://github.com/koreainvestment/open-trading-api):
- 국내 일봉 응답 키: `stck_bsop_date/stck_oprc/stck_hgpr/stck_lwpr/stck_clpr/acml_vol`
- 해외 일봉 응답 키: `xymd/open/high/low/clos/tvol`; 해외 시세 거래소 코드는 `XNAS → NAS`, `XNYS → NYS`, `XASE → AMS`.
- 위 키는 **오프라인 포맷 검증용**이며, KIS 일봉 실제 호출 파라미터·응답 변종/수정주가/라이선스/실시간 지연은 인증된 소유 계정으로 별도 검증해야 한다.
- 가격 데이터의 상업적 이용·재배포/제3자 공유는 상품·거래소 라이선스 확인 필요. FolioSentry는 개인 전용 접근을 유지한다.

## 2. 이번 PR: 데이터 공급자 교체 가능한 기반

`backend/app/market_data.py`는 `InstrumentIdentity`, `DailyBarProvider` Protocol, `DailyBarCandidate`, `DailyBarBatch`, KIS KR/US 일봉 응답 **순수 정규화 함수**만 제공한다.

- 종목 식별키는 `market + exchange_mic + symbol + currency`. 선행 0이 있는 국내 6자리 종목은 그대로 유지. 해외 `EXCD`는 조회 경로에만 사용하고 주문 코드와 혼동하지 않는다.
- 일자: 거래소 로컬 세션 날짜 `YYYYMMDD` → Python `date`. UTC 수집시각을 별도 기록하며 미국 서머타임은 `zoneinfo` 반영.
- 금액/수량: **원본 JSON decimal string**만 허용, Python `Decimal` 사용, OHLC(시·고·저·종) 유효성·중복·누락·미래 세션·음수·소수 8자리 초과/과도한 정밀도 거부. 단 하나의 불량 행도 전체 배치를 실패 처리하며 임의 0원·보정가·DEMO fallback 금지.
- `price_basis`는 RAW/ADJUSTED를 호출자가 반드시 **명시**. 반환된 각 바는 항상 `is_final=False`, `source_observed_at=None`이다. 조회 시각 `fetched_at`을 거래소 원천 갱신시각으로 오인하지 않는다.
- `availability=UNFINALIZED`는 **구조 검증을 통과했지만 최종 확정 시세가 아니라는 뜻**이며 기존 `quote.status=CURRENT`와 다르다. 이 값은 UI/신호에 공개하지 않는다.
- 코드에 네트워크/공급자 계정/키/토큰 처리, DB 쓰기, Alembic, 운영 Compose 변경, 예약 수집·자동 재시도, 실제 시세 API 활성화가 없다.
- CI 테스트는 가상 KR/US OHLCV fixture만 사용한다. 외부 요청 없이 순수 데이터 정규화 기능을 검증한다.

## 3. 안전한 후속 개발 게이트

1. **공급자 사용 가능성 확인**: 개인 KIS 계좌와 Open API 권한을 사용자가 확보할 수 있는지(비밀키 원문은 채팅/GitHub/로그로 전달하지 않음). 가격/호출 제한/휴장·장중 지연/미국 종목·거래소 범위/수정주가 정책을 공식 문서 및 실제 계정에서 검증한다.
2. **읽기 전용 운송 계층**: 오직 허용된 KIS 시세 URL만 호출하도록 allowlist, HTTPS 검증, 타임아웃, 고정 레이트리밋, 만료 토큰 refresh 제한, 자격증명 Docker secret(s) 또는 보호된 로컬 파일, 로그 비식별화. 발주/잔고/주문 API 경로·기능 없음.
3. **저장 단계는 별도 승인**: 기존 `docs/DATA_MODEL.md`의 price_bar 스키마와 일치시키되 KIS의 세션 확정·가격 조정 기준·관측시각 검증 전에는 `is_final=true` 지정 금지. idempotent UPSERT, 품질·추적 기록, KST/NY 정규장, 휴일/시간대/서머타임 검증.
4. **프론트 연결은 후속 단계**: 검증된 바만 시세/차트로 표시하고 `STALE/UNAVAILABLE` 상태, 원천·시각·RAW/ADJUSTED 기준을 함께 표시. 실 보유 수량/평단·KRW/USD를 공급자에 전달하지 않으며 통화간 무단 합산 금지.
5. 코드 변경과 실 MiniPC 환경변수/자격증명 주입, DB migration, 서비스 배포는 **각각 분리하여 승인**. 자동 백업 타이머는 비활성 유지.

## 4. Phase 1 운영 인수 상태

2026-11-20 사용자 제공 서버 배포 `FOLIOSENTRY_PHASE1_APP_DEPLOY_PASS`; 읽기 전용 Chrome 인수 **PASS 7 / FAIL 0 / N/A 2**. 실 종목 데이터 생성·수정·삭제 없음. 이번 MD-01은 이 배포에 아무 영향을 주지 않는다.
