# MD-05A — KIS 실제 일봉 수동 조회 및 참고 종가 표시 (2026-11-23)

**범위:** 개인 보유·관심 목록에서 버튼을 누른 한 종목의 KIS 과거 일별 종가를 직접 읽고, **참고용·비확정**으로 표시하는 첫 번째 수직 기능. 실제 실시간 체결가와 평가손익, 매수/매도 신호·알림은 여전히 별개 기능이다.

현재 상태는 **GitHub Draft PR / 테스트는 합성 데이터 전용**. 소유자 별도 승인 전 main 병합, MiniPC 운영 서비스/DB 배포, 실 KIS 조회/토큰 발급, 운영 가격 공개 설정 변경을 하지 않는다.

## 이번 단계에서 실제로 구현한 경로

1. 로그인 소유자가 보유·관심 목록 화면을 조회한다. `GET /api/v1/market-data/capabilities`는 로그인 쿠키가 있어야 하며, 서버의 수동 조회 기능 활성 여부(불리언)만 보고한다. 계좌·KIS 비밀정보/시세를 읽지 않는다.
2. **수동 참고 종가 조회** 버튼은 기능이 활성화될 때만 눌릴 수 있다. `POST /api/v1/tracked/{tracked_id}/daily-reference` 요청에 세션 쿠키, Origin, CSRF 헤더가 필요하다. 수동 호출만 가능하며 페이지 표시·새로고침만으로 KIS 호출이 발생하지 않는다.
3. 서버는 등록된 실제 종목의 시장/거래소/코드/통화를 확인하고, 기존 `KisReadOnlyDailyProvider`를 사용해 **그 시장의 현지 날짜 기준 어제까지**, 최대 이전 14일 범위의 **RAW** 일봉을 1회 읽는다. 같은 KIS 실계좌로 실시간 잔고·주문·체결 API를 호출하지 않는다.
4. 기존 `KisSharedState`를 **반드시 사용**해 토큰 재발급 가능 여부, 전체 프로세스 간 쿼터·최소 간격, 안전한 소유자 전용 파일을 검사한다. 라이브 신규 토큰 발급은 별도의 플래그가 없으면 **기본 금지**, 자동 재시도도 금지.
5. 응답 DTO는 등록 ID와 참조 `{status, close, session_date, fetched_at, source, price_basis, currency, is_final:false}`만 포함한다. 응답의 `REFERENCE`는 KIS 일봉 응답에서 받은 **과거 일봉 참고 종가**라는 뜻이지 공급자가 검증한 FINAL가 아니다.
6. 주말·휴장으로 오래된 최신 일봉(최종 요청 기준일에서 5일 초과)은 `STALE`이며 금액 `close=null`. KIS가 해당 범위에서 데이터가 없으면 `UNAVAILABLE`과 null. HTTP 503/인증 오류·응답 이상은 무조건 에러로 표시하고 DEMO나 과거 숫자를 가짜로 대체하지 않는다.
7. Frontend는 가격을 `RealTracked.quote` 또는 `market_value/unrealized_pnl`에 병합하지 않고 브라우저 메모리의 **일시적 참조 결과로만** 표시한다. API에서 제공한 가격 Decimal **문자열을 그대로** 출력하고 JS Number로 손익을 계산하지 않는다.

## 운영 안전 설정 — 현재 모두 설정하지 않음

다음은 실제 MiniPC 배포 및 KIS 접근·가격 표시를 **각각 명시적으로 승인받아야** 검토할 변수 이름이다. 이 문서는 활성화/비밀값 작성/배포 명령이 아니다.

| 서버 환경변수 | 의도 / 기본값 |
|---|---|
| `FOLIOSENTRY_MD05_MANUAL_READ_ENABLED` | `yes` 일 때만 외부 수동 KIS 조회 시도 가능. 기본 비활성 |
| `FOLIOSENTRY_MD05_REFERENCE_DISPLAY_ENABLED` | `yes` 일 때만 참조 종가 표시 기능 가능. 기본 비활성 |
| `FOLIOSENTRY_MD05_NEW_TOKEN_ISSUE_ALLOWED` | `yes` 일 때만 기존 shared state 안전조건 아래 신규 토큰 발급 시도 가능. **기본 비활성** |
| `FOLIOSENTRY_KIS_APPKEY_FILE` | 별도 관리하는 절대경로, 동일 OS 소유자의 권한 0600 일반 파일 |
| `FOLIOSENTRY_KIS_APPSECRET_FILE` | 별도 권한 0600 비밀 파일, GitHub/로그에 직접 기록 금지 |
| `FOLIOSENTRY_KIS_SHARED_STATE_DIR` | 별도 0700 안전 디렉터리, 기존 0600 토큰 상태와 호출 예약 공유 |

**주의:** 운영 서비스 도커 환경의 비밀 파일 mount 및 shared-state volume 보존은 이 PR에서 추가하지 않았다. 별도 배포 설계와 소유자의 사용 승인·KIS 조회 권한 확인이 필요하다. 실행 권한을 부여하지 않으면 GET capability는 false, POST는 DB/secret 조회 전에 503으로 끝난다. 실 KIS API로 연결되는 경로는 코드로만 마련했고 이번 단계에서 실제 네트워크 호출은 수행하지 않았다.

## 엄격한 구분

- **실시간 현재가**: 미구현. 이번 값은 일별 역사 가격. 장중 마지막 체결가, 스트리밍, 호가를 의미하지 않는다.
- **미확정 종가**: 표시되는 KIS 수신값은 사후 정정될 수 있다. `fetched_at`은 앱 수신 시각이며 공급자 원천 관측시각이 아니다. `source_observed_at`을 임의 생성하거나 `FINAL`이라고 표시하지 않는다.
- **환율/평가손익**: 계산하지 않는다. 등록 수량·평균단가와 KIS 가격을 곱하지 않는다. 달러/원 가격은 통화 코드를 붙여 혼동을 막는다.
- **데이터 저장**: 기존 price_bar PARTIAL-only, quality_evidence UNVERIFIED, reference_revision UNVERIFIED_REFERENCE 제약은 변경 없음. 별도 새 migration, 데이터 저장, API에 따른 DB 수정 없음.
- **신호·알림**: 어떤 `REFERENCE`도 규칙 엔진이나 알림에 연결하지 않는다.
- **DEMO**: 실제 등록 종목 API는 DEMO 포트폴리오로 가격을 보완하지 않는다.

## 신규 API

`GET /api/v1/market-data/capabilities` (로그인 필수, no-store):

```json
{"manual_daily_reference_enabled":false}
```

`POST /api/v1/tracked/{tracked_id}/daily-reference` (로그인+정확한 Origin+CSRF, 운영 2중 게이트, no-store) 응답의 **합성 예시**:

```json
{
  "tracked_id": "22222222-2222-4222-8222-222222222222",
  "reference": {
    "status": "REFERENCE",
    "close": "105.25",
    "session_date": "2026-11-20",
    "fetched_at": "2026-11-23T01:03:00Z",
    "source": "KIS",
    "price_basis": "RAW",
    "currency": "KRW",
    "is_final": false
  }
}
```

`STALE` 응답은 `close:null`, `UNAVAILABLE`이면 `close/session_date/fetched_at/source/price_basis` 모두 null. 오류 시 민감 원문·토큰/계좌를 응답·로그에 포함하지 않으며 HTTP error. 기존 `GET /api/v1/tracked/{tracked_id}/quote-status`는 여전히 UNAVAILABLE 및 금액 null을 유지한다.

## 테스트 및 후속 개발

- Backend 테스트: 운영 2중 게이트 실패 시 비밀정보/DB/공급자 **접근 0회**, 인증·CSRF·Origin 차단, 한국/미국 5개 거래소, 실제 등록 종목 ID, 전일 이하 참고일봉, stale/empty null, 위조 FINAL/DEMO/수정주가·비정상 가격/원천 시각, upstream 에러 비노출.
- Frontend 테스트: 기능 상태 파서, CSRF POST만 허용, 수동 API 정상·STALE·UNAVAILABLE, 응답 스키마 위조·DEMO/손익 값 삽입 차단, 실제 등록 종목 상태와 분리.
- 기존 GitHub CI 변경 영향 라우터와 backend/frontend tests/build/typecheck/gate로 검증.
- **MD-05B**: KIS **현재가 전용 엔드포인트**의 계약·시장 코드·시간대·장중 신선도·조회 제한을 별도 검증하고 수동 현재가 화면을 구현한다. 그 후 별도 승인 아래 **MD-05C** 평가손익(통화별·기준시각 명시) 및 알림 진입.
- 배포/실 KIS 활성 전 검토: 기존 KIS 토큰 상태와 shared-state 토큰 발급 차단, 0600/0700 파일 마운트, 과금/권한, 호출 빈도 및 에러, 운영 DB 현행 스키마/백업, 소유자 승인. **단순 코드 병합은 실조회/배포 승인 아님.**
