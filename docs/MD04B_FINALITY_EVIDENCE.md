# MD-04B — 최종 종가 판정 전 증빙 결손 게이트 (2026-11-23)

상태: **GitHub Draft / 합성 테스트 전용**. KIS 실호출·토큰 발급·운영 DB migration·배포·스케줄러·UI 가격/손익 표시 금지.

## 이번 단계의 결정

**거래소 세션 종료와 KIS 일봉의 최종 확정은 서로 다른 사실이다.**
- MD-03/04A는 거래소별 공식 확인 일정, 종료+2시간, 시점/가격/종목 일치만 확인한다.
- 현재 KIS 일봉 정규화 응답은 원천 제공자의 개별 시세 관측시각이나 최종 확정/정정 완료를 증명하지 않는다. fetched_at은 **우리의 수신 시각**이지 원천 관측시각이 아니다.
- 원주가와 수정주가를 같은 시계열로 섞지 않는다. KIS 응답이 어떤 가격 기준인지는 요청 파라미터와 실증 가능한 API 문서/공급자 계약으로 별도 확인해야 한다. 액면분할·병합/배당 등 권리·기업행동과 추후 정정은 이 코드로 처리하지 않는다.
- **최종성 판단·VALID 저장·손익/신호/알림/실시세 공개는 이번 단계에서 일체 구현하지 않는다.** price_bar의 PARTIAL 전용 DB CHECK 유지.

## 공식 자료와 코드 차이 검토

| 항목 | 확인된 사실 | 미해결 |
|---|---|---|
| 국내 inquire-daily-itemchartprice | KIS 공식 예제: FID_ORG_ADJ_PRC=0 수정주가, 1 원주가. 기존 kis_readonly.py는 RAW→1, ADJUSTED→0 | 실 응답 기준/과거 권리 반영과 변경 이력 확인 불가 |
| 해외 dailyprice | KIS 공식 예제는 MODP를 수정주가 반영 여부로 설명. 기존 구현은 RAW→0, ADJUSTED→1 | 값별 의미와 조정 이력의 공급자 확정 증빙 부족. 실 시세 노출 금지 |
| KRX 정규 주식시장 | KRX 공식 자료: 통상 09:00~15:30(KST). 2026-11-19 수능일 10:00~16:30 예외는 제한 목록에 반영 | 전체 2026년 달력이나 개별 종목 중단·정정 자료 미포함 |
| NYSE/Nasdaq 2026 | 11/26 휴장, 11/27·12/24 13:00(ET) 조기 마감. 미국 DST 포함 로컬 세션 처리 | 달력만으로 KIS 값의 원천 관측·최종 정정 여부는 증명 불가 |

공식 근거:
- KIS 국내 기간별 시세 공식 예제: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py
- KIS 해외 기간별 시세 공식 예제: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/dailyprice/dailyprice.py
- KIS API 개발자센터: https://apiportal.koreainvestment.com/apiservice
- KRX 정규 거래시간: https://global.krx.co.kr/contents/GLB/06/0602/0602010201/GLB0602010201T1.jsp
- KRX 2026-11-19 예외 공지: https://kind.krx.co.kr/external/2026/11/05/000141/20261105000216/99303.htm
- NYSE 공식 거래/휴장시간: https://www.nyse.com/trade/hours-calendars
- Nasdaq 공식 시장 휴장/조기종료: https://www.nasdaq.com/market-activity/stock-market-holiday-schedule

**주의:** 다른 KIS 일별 API의 같은 이름 파라미터나 인터넷 예제를 섞어 단일 보편 값으로 추정하지 않는다. 특히 inquire-daily-price와 inquire-daily-itemchartprice의 문서를 구분한다.

## 구현

- backend/app/md04_finality.py: 기존 MD-04A inspect_unverified_intake를 재사용하는 순수 진단 함수
- review_daily_finality_gaps(identity, batch, requested_basis, now):
  - 종목 4요소/거래일/지연·가격 검증 실패 시 기존 fail-closed 오류 전달
  - 호출자 요청 RAW/ADJUSTED와 각 일봉 기준이 다르면 MD04B_REQUESTED_BASIS_MISMATCH 차단
  - 빈 배치는 UNAVAILABLE / MD04B_NO_DAILY_BARS
  - 형식·시점이 맞는 배치조차 UNFINALIZED / PARTIAL로만 보고
  - 원천 관측시각, 공급자 확정 종가, 가격 기준, 정정 가능 기간, 기업행동 수정 정책, 승인된 최종화 로직의 **6개 결손**을 고정 reason code로 보고
  - 결과에 OHLCV, 실종목, 토큰, 계좌, 매입가를 포함하지 않음
  - is_final=False, promotion_allowed=False, publication_allowed=False, analysis_allowed=False, automatic_storage_allowed=False 고정
- backend/tests/test_md04_finality.py: 5개 거래소 × RAW/ADJUSTED 합성 검증, 빈 배치, 다른 요청 기준, 원천 final/관측시각 위조, 미증빙 세션, 오래된 응답, 불변 진단 객체 검증.
- 새 migration, API route, 배포 설정, 기존 CI 워크플로, MiniPC, 실 KIS 접근 없음.

## 후속 개발 승인 게이트

1. KIS **정확한 엔드포인트별** 원주가·수정주가 옵션과 미국 거래소 시세 범위/권리 반영, 관측시각/정정·최종성에 관한 1차 근거 및 권한 검증
2. 공식 시장 일정의 버전/증빙·특수일정 반영·개별 종목 거래정지 처리, 동일 날짜 재조회 시 변경 감지 및 원본 보존 정책
3. 독립적인 공급자 최종 종가 증빙 확보 시에만 새로운 **버전드 finality 규칙과 DB migration을 별도 PR로 설계**; 기존 MD-03 CHECK 무단 제거 불가
4. 합성 DB와 브라우저에서 미확정 가격·오래된 가격·잘못된 기업행동 처리 시 손익/신호/알림 차단 검증
5. 최종성 승인 전 대안으로 **명시적 비확정 참고가격** 별도 UI를 설계할지는 사용자 별도 결정 (현재 금지)

CI PASS와 PR 병합은 MiniPC 운영 배포, 실 KIS 호출, price_bar schema 적용, 최종가격/손익 공개 승인이 아니다.
