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

## 5. MD-02: KIS 국내·미국 일봉 **조회 전용 HTTPS 어댑터** (2026-11-20)

사용자가 **한국투자증권 계좌 보유를 확인**했다. 단, 계좌 보유만으로 Open API 서비스 신청/APP Key·Secret이 발급됐다는 뜻은 아니다. 실 API 호출 전 공식 [이용안내](https://apiportal.koreainvestment.com/about-howto)에서 서비스 신청·발급 상태 확인 필요.

구현: `backend/app/kis_readonly.py`와 `backend/tests/test_kis_readonly.py`. 서비스 앱 라우터/자동 스케줄러/DB/Frontend 연결 없음. **명시적으로 `live_enabled=True`를 부여하지 않으면 절대 네트워크 연결 불가**, 그리고 자격증명 파일이 없으면 연결 불가. CI에서는 KIS 네트워크에 접속하지 않고 테스트 FakeTransport를 사용한다.

### KIS 공식 예제와 대조된 실제 읽기 전용 호출 계약

| 용도 | HTTP | 경로 | TR ID |
|---|---|---|---|
| 앱 접근 토큰 | POST | `/oauth2/tokenP` | 해당 없음 |
| 국내 일봉 | GET | `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` | `FHKST03010100` |
| 해외 일봉 | GET | `/uapi/overseas-price/v1/quotations/dailyprice` | `HHDFS76240000` |

KIS 공식 예제: [국내](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py), [해외](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/dailyprice/dailyprice.py). 고정 도메인은 실전용 `https://openapi.koreainvestment.com:9443`이며 다른 주소나 주문/잔고 경로를 코드에서 허용하지 않는다.

- 국내: `FID_COND_MRKT_DIV_CODE=J` (한국), `FID_INPUT_ISCD=6자리`, 시작/종료 일자, `FID_PERIOD_DIV_CODE=D`, `FID_ORG_ADJ_PRC=0` 수정주가 / `1` 원주가.
- 해외: `AUTH=""`, `EXCD=NAS/NYS/AMS`, `SYMB`, `GUBN=0` 일봉, `BYMD=종료일자`, `MODP=1` 수정주가 / `0` 원주가.
- 해외 API는 조회 종료일 기준 과거 데이터를 반환할 수 있어 요청 시작일 이전 데이터는 필터링. **반환 행 수가 적다고 휴장/정상 갱신/전체 기간 커버리지를 보장하지 않는다.** 응답 품질/장 마감 확정 정책이 미검증이므로 `is_final=False` 및 `source_observed_at=None` 고정.
- 요청 1회 최대 100일 날짜 구간, 한 인스턴스당 총 최대 60 HTTP 요청(토큰 포함), 일봉 조회 사이 최소 1초, 자동 재시도 없음. OAuth 토큰은 객체 내 일시 메모리 캐시; 새 토큰 재발급은 단일 프로세스에서 최소 6시간 간격. **여러 프로세스/재시작 간 발급·초당 제한을 보장하지 못하므로 지금은 스케줄러를 연결하지 않는다.**
- HTTP 요청 실패/리다이렉트/비JSON/너무 큰 본문/토큰 이상 시 짧은 비민감 오류 코드만 반환. TLS 검증은 Python 기본 신뢰 저장소. 주문·잔고/계좌 조회 API는 allowlist 밖.
- App Key/Secret은 **사용자 MiniPC에 별도 보관한 같은 소유자·0600 권한 일반 파일**에서 명시적으로 읽고 심볼릭 링크는 거부. 비밀값을 GitHub·채팅·테스트 로그에 붙이지 않는다. 계좌번호는 설계상 필요 없다. 운영 Compose에 자격증명 주입/서버 설정 변경 없음.
- 공급자 실제 첫 호출을 통한 실측, 실시간 지연·수정주가·상장종목 정합성, 생산 차트/시세 UI 연동은 모두 별도 게이트. 이번 PR의 CI PASS는 운영 KIS 연동 성공을 뜻하지 않는다.

### 사용자 진행 순서 (비밀값 공유 불필요)

1. [한국투자증권 KIS Developers 이용안내](https://apiportal.koreainvestment.com/about-howto)에서 Open API 사용 신청·APP Key/Secret 발급 가능 여부 확인.
2. 계좌 보유 사실만 확인된 상태. **APP Key·Secret·토큰·계좌번호를 ChatGPT에 보내지 않는다.** 발급 상태는 “신청 완료/미신청”만 전달.
3. 발급 완료 및 사용자 명시적 외부 시세 호출 승인 후에만 MiniPC 로컬 비밀 파일 설정/읽기 전용 최초 호출 절차 제시. 이후 가격·장마감·품질 검증 후 DB 모델/배포 단계 별도 승인.
