# MD-04C1 — 실제 종목의 비가격 품질 상태 계약 (2026-11-23)

**상태: GitHub Draft / API·UI 안전 경계만 구현. 실제 시세 연결·운영 배포 아님.**

## 현재 동작과 이번 변경의 경계

- 기존 인증 API /api/v1/tracked는 **운영에서 계속 UNAVAILABLE만 반환**한다. 서버의 portfolio_api.tracked_json과 DB/API 라우터는 이 PR에서 변경하지 않는다.
- 새로운 backend/app/quote_visibility.py는 MD-04B FinalityGapReport를 받아 가격이 빠진 quote JSON을 만들어 주는 **순수 오프라인 계약 함수**다. 실제 라우터로 연결하지 않는다.
- 프론트 realPortfolioApi.ts는 미래에 서버가 상태만 전달하더라도 close/변동률/시점/출처와 손익이 모두 null인지 강제 검사한다.
- RealPortfolioPage.tsx는 기존 페이지 구성/입력 폼을 보존하고, 각 실제 종목 행에 서버 응답의 안전한 상태에 해당하는 한국어 문구만 표시한다. 현재는 기존과 동일한 '시세 없음 · 손익 미계산'.
- DEMO 화면과 API는 전혀 수정하지 않는다. 합성 가격·상태를 실제 UI에 주입하지 않는다.

## 인증된 실제 종목 목록의 quote 하위 계약 — MD-04C1

| status | 한국어 표시 | API 가격 및 손익 | 구현 단계 |
|---|---|---|---|
| UNAVAILABLE | 시세 없음 · 손익 미계산 | 전부 null | 운영 Backend 기존 응답 |
| UNFINALIZED | 종가 미확정 · 손익 미계산 | 전부 null | 순수 Backend 계약 / 프론트 지원 |
| STALE | 오래된 시세 · 손익 미계산 | 전부 null | 미래 응답의 UI 계약만 |
| ERROR | 시세 확인 실패 · 손익 미계산 | 전부 null | 미래 응답의 UI 계약만 |
| CURRENT/VALID/DEMO/알 수 없는 값 | **파서에서 오류로 차단** | 가격 표시 금지 | 아직 허용하지 않음 |

quote JSON 키는 정확히 status, close, change_pct, as_of, source의 다섯 개만 허용. 이 단계에서는 나머지 네 값이 반드시 null이어야 하며, 숫자/문자열 가격, 가짜 원천시각, KIS 출처, is_final 플래그 등 추가 키를 전부 거부한다.

현재 가격 공개 불가 계약 예시(합성):

~~~json
{
  "quote": {
    "status": "UNFINALIZED",
    "close": null,
    "change_pct": null,
    "as_of": null,
    "source": null
  },
  "market_value": null,
  "unrealized_pnl": null,
  "unrealized_pnl_percent": null
}
~~~

- 기존 보유 수량과 평균단가는 소유자가 직접 입력한 개인정보로, 시세나 손익으로 오인하지 않는다.
- 현재 서버는 UNFINALIZED를 보내지 않는다. 미래 가격 수집 결과를 기존 실 종목 API에 연결하려면 **별도 API 구현 PR**, 인증·DB·데이터 품질 검증 및 사용자 승인이 필요하다.
- 서버에 PARTIAL 가격이 저장되더라도 가격과 손익을 노출하지 않는다. fetched_at은 최종가 원천 관측시각으로 간주하지 않는다.
- API 401/403/503/Network 실패 시 DEMO 또는 임의 숫자로 fallback하지 않는다. **응답 파싱 실패 시 해당 목록 전체를 렌더링하지 않는 기존 차단 정책 유지**.
- STALE도 검증된 마지막 가격을 보여주도록 허용하지 않는다. 일반 Phase 1A의 과거 계획 문서보다 MD-04C1의 보수적 공개 정책을 우선한다.

## 코드 및 테스트

- backend/app/quote_visibility.py: finality 보고서가 None이면 UNAVAILABLE, 승인되지 않은 PARTIAL 보고서이면 UNFINALIZED, 위조·불일치 상태는 예외. 출력에는 금액·OHLCV·종목명 없음.
- backend/tests/test_quote_visibility.py: 합성 KIS 배치 → MD-04B 진단 → 마스킹 결과·권한 위조/불일치 차단.
- frontend/src/realQuoteStatus.ts: 허용 상태 4개, 다섯 키의 엄격한 구조 검증, 한국어 문구.
- frontend/src/realQuoteStatus.test.mjs: 비가격 상태 표기와 가격 주입/CURRENT/DEMO/추가 필드 전부 거부.
- frontend/src/realPortfolioApi.test.mjs: 실제 목록은 미래 품질 전용 상태를 통과시키되 가격·시점·출처·최종 상태 위조를 거부.
- Frontend typecheck/build/테스트와 Backend pytest/compile는 기존 GitHub Actions 영역별 검증을 이용한다.

## 여전히 금지되는 작업

운영 MiniPC의 KIS 비밀값·토큰 읽기/신규 발급/실호출, price_bar 마이그레이션, 자동 수집 스케줄러, API 경로 연결, 운영 Frontend/Backend 배포, 실제 가격/손익/신호/알림 발행, 합성 숫자를 실제 사용자 화면에 주입하는 것. Draft PR과 CI PASS는 운영 승인이나 main 병합 승인이 아니다.

다음 단계 MD-04C2는 **인증된 상태 전용 API에 실제 공급자 품질 상태를 어떻게 전달할지**를 분리해 검토한다. MD-04B에서 정리한 원천 관측·최종성·가격 조정/정정 정책이 마련되기 전 **실제 가격 표시**는 구현하지 않는다.
