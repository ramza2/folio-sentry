# MD-04C2 — 인증된 종목 시세 품질 상태 전용 GET (2026-11-23)

상태: **합성 데이터 전용 Draft PR / GitHub CI 검증 대상**. 신규 KIS 실조회, 가격/손익·시그널/알림 공개, MiniPC 운영 배포, 운영 DB migration, 자동 스케줄러 실행 **없음**.

## 목표 및 현재 제약

- MD-04C1 PR #31은 사용자 승인으로 main@9422bea에 병합, 후속 CI #45139488106 PASS.
- 현재 실제 종목 API는 사용자 수동 종목과 보유·관심 목록만 운영에서 관리한다. 실제 price_bar 테이블은 MiniPC 운영에 설치·연결되었다고 가정하지 않는다.
- MD-04C2가 *새로운 원천가격이나 최종 종가를 얻었다는 뜻이 아님*. 기존 등록 종목의 존재 여부를 확인하고, 독립적인 상태 전용 읽기 경로를 마련한다.
- 가격 상태를 자동으로 refresh, 예약 수집, DEMO 데이터 혼입하거나 정상적인 로그인·CSRF 보호를 완화하지 않는다.

## 추가 API

GET /api/v1/tracked/{tracked_id}/quote-status

- 운영에 이미 존재하는 글로벌 /api/* 인증 미들웨어 적용: 유효하지 않은 세션은 401, 비존재·비활성 종목은 404, 저장소 실패는 503, UUID 형식 오류는 422
- 소유자의 실제 등록 종목 여부만 기존 tracked_instrument 및 instrument 테이블에서 확인. price_bar, KIS API, 외부 서비스, 별도 캐시, 파일시스템·스케줄러 접근 금지
- read-only SELECT 이외에는 DB를 수정하지 않는다. 성공 응답은 200/no-store/Vary Cookie
- 성공 응답은 딱 두 최상위 필드(tracked_id 및 quote), 시세는 품질 미확인으로 항상 UNAVAILABLE
- Pydantic strict response model로 UNFINALIZED/STALE/ERROR/CURRENT/VALID 등의 상태를 이번 라우트에서 임의로 승격하는 것을 차단. 추후 실제 품질 근거 연계는 별도 승인·PR로 수행

합성 응답 예시(가격·거래원천 정보 없음):

~~~json
{
  "tracked_id": "11111111-1111-4111-8111-111111111111",
  "quote": {
    "status": "UNAVAILABLE",
    "close": null,
    "change_pct": null,
    "as_of": null,
    "source": null
  }
}
~~~

- 이 엔드포인트는 **holding quantity, average_cost, market_value, unrealized_pnl, instrument, price_basis, is_final, fetched_at** 등을 반환하지 않음
- existing GET /api/v1/tracked의 응답·라우터 계약은 변경하지 않음; 해당 API는 계속 quote UNAVAILABLE/손익 null
- 실패 시 DEMO/mock 숫자·오래된 시세 fallback 금지. 가격/손익·분석·자동 수집을 제어하는 기존 fail-closed 조건 유지

## Frontend 연계

- 기존 실제 종목 관리의 각 행에 '상태 확인' 버튼 추가. **명시적으로 눌렀을 때만** 위 API에 same-origin cookie, no-store GET 수행. N+1 자동 조회·백그라운드 갱신 없음
- 응답의 tracked_id는 요청한 종목 ID와 반드시 일치해야 하며, 최상위 JSON 필드 두 개만 허용. quote는 기존 MD-04C1 parseHiddenQuote를 통해 금액, 출처, 시간 및 가격/최종성 위조 전부 차단
- 응답 실패·서버 오동작 시 기존 상태 텍스트 유지, 사용자에게 오류 표시. 다른 종목의 상태를 변경하지 않음. 시세·손익 수치를 표시하지 않음
- UI는 실 API 배포 전까지 원격 GitHub 코드만 존재; 운영 MiniPC Frontend/Backend 배포는 별도 승인

## 테스트 및 승인 게이트

- Backend: 5거래소 합성 등록 / 인증 401 / 로그인·로그아웃 / 404, 422, 503 / 외부 가격 데이터 부재 / OpenAPI strict schema / 위조된 응답이 FastAPI response_model을 통과하지 못함
- Frontend: 클릭 전 자동 조회 없음, 상태 GET 경로·same-origin·no-store, tracked ID 상호 검증, quote 가격·통화·손익/추가 필드 전부 차단, 401/404/503 예외
- GitHub-hosted CI Backend/Frontend + 최종 CI gate 합격
- 사용자 **별도 병합 승인** 전 main 병합 금지. 병합 이후에도 별도 운영 배포, 운영 DB, KIS 호출/토큰, 가격·손익·매매신호/알림 공개 승인 필요
- 후속 MD-04C3는 provider quality metadata persistence/attestation 설계부터 검토하며, 공급자 확정종가 근거 확보 전 FINAL/CURRENT 노출은 금지
