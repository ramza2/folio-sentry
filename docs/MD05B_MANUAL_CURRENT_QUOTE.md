# MD-05B — 한국·미국 주식 KIS 현재가 수동 조회 (2026-11-24)

**상태:** GitHub Draft PR / 합성 테스트 전용. **실 KIS API·OAuth 발급, MiniPC 배포, 운영 DB 변경, 실제 시세 표시 기능 활성화는 모두 별도 사용자 승인 대상**이다. 본 PR에서 외부 KIS 호출은 하지 않는다.

## 목표 및 사용자가 보는 정보

- 보유/관심 종목에서 **현재가 조회** 버튼을 눌렀을 때, KIS REST API가 최근에 제공한 종목 가격을 한 번 조회한다. 자동 폴링/백그라운드 스케줄러/재시도/선행 토큰 발급은 없다.
- 수신 결과는 **KIS 제공 현재가**, 앱 수신 시각(UTC 저장/KST 표시), 통화(KRW/USD), 실시간·지연 여부 미확인이라는 별도 UI에 나타난다.
- **수신 시각은 공급자 가격의 체결시각이 아니다.** REST 현재가 응답의 실제 원천시각, 시장 개장 상태, 지연 여부/장외 거래 포함 여부를 증명하지 못한다. 한국 공식 예제는 진짜 실시간 시세에는 WebSocket을 사용하라고 명시한다. 해외 가격은 데이터 이용 조건에 따라 지연될 수 있다. **실시간 스트리밍/매매용 확정 시세라고 주장하지 않는다.**
- 이전 MD-05A 과거 일봉 참고 종가와 완전 분리: MD05A의 `/daily-reference`와 `REFERENCE/STALE` 응답, 등록 종목 `quote=UNAVAILABLE` 및 `market_value/unrealized_pnl` null 유지.
- OHLCV DB 보관, 추정 원가·손익, 시장 지연시간 측정, 매수·매도 신호·알림·주문 기능 추가 없음.

## 공식 소스 검토

2026-11-24 KIS 공식 공개 예제 저장소 `koreainvestment/open-trading-api`의 upstream `b0a0d33b7e5f863a8f3c6790f50adb840829c806` 커밋 기준:

| 범위 | REST 조회 경로 / TR ID | 파라미터 | 가격 필드 |
|---|---|---|---|
| 국내 주식 현재가 | `GET /uapi/domestic-stock/v1/quotations/inquire-price`, `FHKST01010100` | `FID_COND_MRKT_DIV_CODE=J`, `FID_INPUT_ISCD` (6자리) | `output.stck_prpr` |
| 해외주식 현재체결가 | `GET /uapi/overseas-price/v1/quotations/price`, `HHDFS00000300` | `AUTH=""`, `EXCD=NAS/NYS/AMS`, `SYMB` | `output.last` |

고정 공식 예제:
- [국내 주식 현재가 소스](https://github.com/koreainvestment/open-trading-api/blob/b0a0d33b7e5f863a8f3c6790f50adb840829c806/examples_llm/domestic_stock/inquire_price/inquire_price.py) (Blob `bb6ab22df57b1a5d14fab861f6c1d29272872a84`)
- [국내 현재가 응답 필드 설명](https://github.com/koreainvestment/open-trading-api/blob/b0a0d33b7e5f863a8f3c6790f50adb840829c806/examples_llm/domestic_stock/inquire_price/chk_inquire_price.py) (Blob `ad79be53fe43e667db13748799458ca66e3ab9d7`)
- [해외 현재체결가 소스](https://github.com/koreainvestment/open-trading-api/blob/b0a0d33b7e5f863a8f3c6790f50adb840829c806/examples_llm/overseas_stock/price/price.py) (Blob `5c316f0d21531b323ca4b12667d9802d167720ea`)
- [해외 현재체결가 응답 필드 설명](https://github.com/koreainvestment/open-trading-api/blob/b0a0d33b7e5f863a8f3c6790f50adb840829c806/examples_llm/overseas_stock/price/chk_price.py) (Blob `48489126509d54b42391676f787219878a70c794`)

국내 API의 `J`는 KRX 기준 시세다. 공식 예제에는 `NX`/통합시장 조회의 선택지도 있으나 **현재 프로젝트의 XKRX/XKOS는 기존 식별자와의 호환을 위해 J로 제한**한다. NYSE/NYSE American/Nasdaq도 기존 InstrumentIdentity의 시장 코드 매핑을 그대로 사용한다. KIS의 해외 시세 제공 범위·유료/무료 지연 권한은 운영 승인 전 별도 확인한다.

## 구현 및 보호 장치

- 신규 `backend/app/kis_current.py`: 고정 KIS 도메인/GET 경로 + TR ID, strict `rt_cd="0"`, `output.stck_prpr/last` 문자열 Decimal(양수/유한/<=8자리 소수) 정규화. 빈 값은 `UNAVAILABLE`. 선택적 종목 코드 필드가 모순될 경우 거부. `provider_observed_at=None`, `realtime_verified=False`, `is_final=False`.
- `backend/app/kis_readonly.py` 기존 allowlist에 **현재가 조회 경로 두 개만** 추가. `backend/app/kis_shared_state.py`의 `EXPECTED_TR`에 TR ID 두 개 추가. 기존 24시간 전체 호출량 60회/토큰 발급 간격·최소 1.25초 예약과 교차 프로세스 락을 **MD05A 일봉과 MD05B 현재가가 공동 사용**. 주문·잔고·시세 외 임의 경로는 불허.
- 신규 `backend/app/md05_current_quote.py`: 인증 소유자 `GET /api/v1/market-data/current-capabilities`는 단순 boolean만 보고하고 KIS/비밀정보/DB를 호출하지 않는다. `POST /api/v1/tracked/{tracked_id}/current-quote`는 Origin+CSRF+세션을 필수로 하며 조회 기능 비활성 시 DB/자격증명에 접근하기 전 503. 등록·활성 종목 ID 확인, 읽기 전용 호출 **1회**만.
- 응답 `{"tracked_id", "current_quote"}`: `{"status":"RECEIVED","price":"251.2300","fetched_at":"2026-11-24T01:00:00Z","currency":"USD","source":"KIS","provider_time_status":"UNKNOWN","delay_status":"UNKNOWN","market_session":"UNKNOWN","realtime_verified":false,"is_final":false}` (모두 합성 예시). `UNAVAILABLE`에는 price/fetched_at/source=null.
- 앱 수신 시각이 **조회 응답 직전 최대 2분 범위**를 벗어나거나 미래 5초를 넘으면 거부한다. 이것은 **앱 수신 기록의 타당성 검사**일 뿐 시세 자체의 최신성 보증은 아니다.
- Frontend `frontend/src/realPortfolioApi.ts`는 price 문자열/출처/시간·Unknown flags·허용 key 집합을 엄격 검증한다. `RealPortfolioPage.tsx`는 수동 조회 시 별도 메모리 상태에만 보관하며 페이지 새로고침·목록 갱신 시 사라지고, PnL/hidden quote/DEMO 데이터에 병합하지 않는다.
- 실 KIS 연결이 잘못되거나 파일 권한·토큰·공유 호출 제한을 통과하지 못하면 **일반적인 503 오류**만 반환하며 토큰/쿼리/원문/가격을 로그·에러에서 노출하지 않는다.

## 기본 비활성 운영 설정 (새로 자동 설정하지 않음)

| 서버 환경변수 | 설명 |
|---|---|
| `FOLIOSENTRY_MD05_CURRENT_READ_ENABLED` | `yes` 설정 시 현재가 수동 조회 읽기 허용 후보 |
| `FOLIOSENTRY_MD05_CURRENT_DISPLAY_ENABLED` | `yes` 설정 시 현재가 화면 출력 허용 후보 |
| `FOLIOSENTRY_MD05_NEW_TOKEN_ISSUE_ALLOWED` | `yes` 없으면 **새 OAuth 토큰 발급 금지** |
| `FOLIOSENTRY_KIS_APPKEY_FILE` / `FOLIOSENTRY_KIS_APPSECRET_FILE` | 0600, 동일 OS 소유자·심볼릭 링크 불허, GitHub 저장 금지 |
| `FOLIOSENTRY_KIS_SHARED_STATE_DIR` | 0700 소유자만 접근 가능한 영속 상태 경로; MD05A와 **동일** 경로를 써야 상호 호출 제한 공유 |

현재 코드의 두 개 MD05B 기능 플래그는 기본 **OFF**. 이 PR은 운영 Compose/비밀파일 볼륨/스케줄러/DB 마이그레이션을 변경하지 않는다. GitHub merge 자체는 운영 시세 활성화 권한이 아니며, 실계좌 KIS API 이용·비밀 파일 접근·MiniPC 배포·실시세 화면 노출은 모두 별도 명시 승인.

## 검증과 다음 범위

- 합성 Backend 테스트: KR/US 다섯 거래소, 공식 TR/파라미터, 빈 가격/위조 응답/최종성 플래그/잘못된 값, shared quota/token issue 기본 차단, HTTP 세션/CSRF/Origin, 이전 MD05A 및 quote-status 회귀, 에러 비노출.
- 합성 Frontend 테스트: 수동 POST·capability, 정확한 스키마, 출처·시각·지연 UNKNOWN 검증, 가짜 FINAL/REALTIME/DEMO/손익·시장상태 필드 삽입 차단, PnL null 유지.
- CI Backend + Frontend/tsc/Vite 및 fail-closed gate로 검증. **실 KIS 응답 필드·가격/시간/권한은 아직 테스트하지 않음**.
- 다음 MD-05C에서 수량·매입단가와 KIS 실제 가격을 연결한 손익 표시를 검토하되, 데이터 지연/통화별 차이, 예외 처리, 1인 인증·데이터 보관 및 원화 환산을 별도 승인할 것.
