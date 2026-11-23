# MD-04A — KIS 일봉 수집·격리 저장 합성 통합 계약 (2026-11-23)

**상태: GitHub Draft 개발 전용.** 실제 KIS 재조회, 운영 DB migration, 자동 수집, UI 가격 노출 및 계좌/주문 기능 없음.

## 기준

- Public GitHub main 7ced35d: PR #28(경량 CI), #24(일회성 KIS 조회 도구), #25(공유 토큰 보호), #26(MD-03 PARTIAL 저장 스키마) 병합 및 사후 CI PASS.
- 2026-11-20 실전 KIS OAuth 1회 및 한국/미국 일봉 각 1건의 형태만 사용자 승인으로 확인했다. 실전 호출 마커를 보존하며 재조회하지 않는다. 가격 최종성/원주가·수정주가/관측시간 증빙은 미확인.
- MiniPC 운영 DB는 새 price_bar migration이 적용됐다고 가정하지 않는다.

## 완전 합성 경로

~~~text
CI synthetic_transport (KIS 인터넷 접속 없음)
 → KisReadOnlyDailyProvider: token POST 1, KR/US daily GET 각 1
 → normalize_kis_daily_response: DailyBarBatch / is_final=False
 → inspect_unverified_intake: 요청한 종목 4요소 일치와 validate_batch 품질 검사
 → IntakeReadiness: count / UNFINALIZED / PARTIAL / publication_allowed=False
 → insert_unverified_daily_batch: CI 전용 folio_ci DB / 명시적 allow_write=True
 → PARTIAL-only DB CHECK / 멱등성 / SAVEPOINT 보호
 → rollback: DB 잔존 행 0 / API·화면·알림 영향 0
~~~

backend/app/md04_intake.py 는 인증정보/네트워크/DB/API/스케줄러가 없는 **순수 진단 계약**이다. market, exchange_mic, symbol, currency가 요청 종목과 모두 일치해야 한다. 정규화 성공이나 장마감+2시간 경과만으로 시세를 최종 종가로 판단하지 않는다. IntakeReadiness는 OHLCV·키·토큰·계좌·보유 정보 없이 count 및 UNAVAILABLE/UNFINALIZED, PARTIAL, 발행 금지 여부만 반환한다. 빈 데이터는 UNAVAILABLE이다.

backend/tests/test_md04_intake.py 는 한국·미국 정상 합성 일봉, 종목/거래소 불일치, 빈 응답, 공급자 불일치, 위조된 final, 미검증 세션, 오래된 응답, 결과 객체 불변성과 실제 종목 API의 손익·시세 NULL을 검사한다.

backend/scripts/test_price_bar_isolated_ci.py 후단은 기존 **GitHub Actions 전용 folio_ci 가드**를 재사용한다. 가짜 transport 함수만 주입하여 KIS 실 호출을 원천 차단한다. KR/US 합성 행을 저장하고 전량 롤백하며 다음 마커를 출력한다.
- FOLIOSENTRY_MD04A_SYNTHETIC_KIS_TO_ISOLATED_DB_PASS
- FOLIOSENTRY_MD04A_ROLLBACK_AND_NONPUBLICATION_PASS

기존 Public CI는 변경된 backend/scripts 파일을 Backend + auth-db-migration으로 자동 분류하며, 최종 CI gate가 검증한다. Actions 설정 파일과 Frontend·API·운영 Docker 설정은 변경하지 않는다.

## 시세 노출 정책

| 대상 | 현재 처리 | 사용자 화면 |
|---|---|---|
| KIS 응답 없음/빈 배치 | UNAVAILABLE | 시세 없음 |
| 정규화 성공, 일봉 세션·가격 검사 성공 | UNFINALIZED / PARTIAL | 시세 없음, 손익 미계산 |
| 거래소 장마감 + 2시간 충족 | 최소 관찰 지연 조건만 충족 | 여전히 시세 없음 |
| 미검증 휴장·조기 종료·관측시각·기업행동 | fail-closed | 시세 없음 |
| MD-03 PARTIAL 일봉 저장 | is_final=false, source_observed_at=NULL DB CHECK | 시세·신호·알림 금지 |
| 향후 실 가격 공개 | **별도 MD-04B/04C 승인 후** | 미구현 |

현재 portfolio_api.tracked_json은 quote.status=UNAVAILABLE, 가격·평가손익은 NULL 고정이다. Frontend realPortfolioApi.ts도 이 응답만 받아들이며 MD-04A는 이 계약을 변경하지 않는다. fetched_at을 거래소 확정시각 또는 원천 제공자 관측시각으로 대체하면 안 된다.

## 다음 승인 게이트

1. KIS 시세 조회 약관/최종 종가 증빙, 유효 토큰 관리, 해외 거래소 코드·시세 권한 및 RAW/ADJUSTED와 기업행동 정책 검증
2. KRX/NYSE/Nasdaq 공식 휴장·조기종료와 거래 시간표의 버전 관리, 갱신/출처/서머타임, 시세 지연·정정·중복 검증 (공식 캘린더만으로 finality를 인정하지 않음)
3. 별도 versioned schema/품질검증으로 VALID 전환 가능성을 심사. 기존 MD-03의 PARTIAL DB 제약을 무단 제거하지 않음
4. 합성 PostgreSQL, 인증 API, Frontend DEMO 분리 및 불확정/미확인 시세/오류 발생 시 손익·신호 차단 E2E
5. 사용자 개별 승인이 있을 때만 main 병합, 운영 DB 백업·격리 복원/마이그레이션, MiniPC 배포, 실제 KIS 호출, 시세/손익 표시 연결 실시

## 공식 자료

- 한국투자증권 Open API 개발자센터: https://apiportal.koreainvestment.com/apiservice-summary (국내·해외 주식 기간별 시세 API 존재 여부 근거일 뿐 최종 종가 증명은 아님)
- KRX KOSPI 수능일 2026-11-19 정규시장 10:00~16:30 공지: https://kind.krx.co.kr/external/2026/11/05/000141/20261105000216/99303.htm
- KRX KOSDAQ 동일 예외 공지: https://kind.krx.co.kr/external/2026/11/05/000145/20261104001218/70780.htm
- NYSE 공식 일정: https://www.nyse.com/trade/hours-calendars
- Nasdaq 공식 일정: https://www.nasdaq.com/market-activity/stock-market-holiday-schedule

**이번 GitHub Actions PASS는 운영 DB migration, 실 KIS 조회, 시세/손익 UI 공개 및 main 병합에 대한 승인이 아니다.**
