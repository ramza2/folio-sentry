# MD-04C5 — KIS 공식 문서 수동 검토 및 최종성 결손 게이트 (2026-11-23)

상태: **GitHub Draft / 순수 Backend 진단 / 운영 배포·실 KIS API 호출 없음**. 문서 확인과 최종 종가의 검증은 서로 다른 단계다.

## 검토 자료 (2026-11-23 확인)

KIS 공식 GitHub 저장소 koreainvestment/open-trading-api의 **upstream commit `74b0a082fa67a0be5bf53f561719c853890ed2df` (2026-11-16)** 에 고정된 파일/Blob을 검토했다. 각 링크는 공개 코드 예제다. **KIS API 개발자센터가 발행한 서명된 최종성 보증이나 개별 종목의 공급자 원천 관측시각 증명은 아니다.**

| 범위 | 확인한 자료/Blob SHA | 문서에서 확인 가능한 사실 | 아직 보증할 수 없는 부분 |
|---|---|---|---|
| KR `inquire-daily-itemchartprice` | [기간별 시세 공식 예제](https://github.com/koreainvestment/open-trading-api/blob/74b0a082fa67a0be5bf53f561719c853890ed2df/examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py) / `77f0eac28baba0c55a87ad05cc2aba67c12b73f6` | `FID_ORG_ADJ_PRC=0` 수정주가, `1` 원주가라는 *해당 엔드포인트 예제 설명* | 출력값 자체의 정확성·가격 조정 효과·원천 타임스탬프·사후 정정·공급자 최종성 |
| KR 해당 API 설정 | [공식 MCP 설정](https://github.com/koreainvestment/open-trading-api/blob/74b0a082fa67a0be5bf53f561719c853890ed2df/MCP/Kis%20Trading%20MCP/configs/domestic_stock.json) / `e82a0829ef519c64dfecb3e966ed217b4fcd3805` | `inquire_daily_itemchartprice`에도 `0` 수정/`1` 원주가로 명시 | 실수신 데이터·권리/정정 이력 확인 불가 |
| KR 다른 API `inquire-daily-price` | **위와 동일한 파일/Blob** | 같은 명칭의 `fid_org_adj_prc`가 `0` 미반영/`1` 반영으로 **반대로 설명된 문서 차이** 확인 | 이 설명을 `inquire-daily-itemchartprice`에 복사해서 쓰면 안 됨. API별 별도 검증 필요 |
| US `dailyprice` | [해외 기간별 시세 공식 예제](https://github.com/koreainvestment/open-trading-api/blob/74b0a082fa67a0be5bf53f561719c853890ed2df/examples_llm/overseas_stock/dailyprice/dailyprice.py) / `4c7a88370a485606c0d87990615ad6f1eafa95ce` | `MODP`는 수정주가 반영 여부라고 기술하며 호출 예제에 값 `0`이 나옴 | 예제 본문만으로 `0`/ `1` 각각의 보증된 의미·실제 가격 보정·원천관측시각/최종성을 알 수 없음 |
| US 백테스터 사용 | [KIS 공식 저장소의 백테스터](https://github.com/koreainvestment/open-trading-api/blob/74b0a082fa67a0be5bf53f561719c853890ed2df/backtester/kis_backtest/providers/kis/data.py) / `28bf9aca834e4abd7c0b4b63ab0b9be61678de13` | `MODP=1`을 수정주가로 주석 표기하는 *샘플 구현* | 공급자 보증 문서/가격 교정 규칙·실수신 확인에 해당하지 않음 |

**중요한 분리:** 기존 `backend/app/kis_readonly.py`의 요청 매핑은 KR RAW→1/ADJUSTED→0, US RAW→0/ADJUSTED→1이다. 이번 문서 비교는 이를 자동 수정하거나 실 호출해 보증하지 않는다. **같은 명칭의 파라미터를 다른 API로 일반화하지 말 것.**

## 수동 오프라인 검토 함수

`backend/app/md04c5_source_review.py`:
- 공개 공식 예제 5개 참고 항목을 **upstream commit·Blob SHA로 고정**해 카탈로그에 기록. 원격 URL/문서/이미지/가격 데이터 다운로드나 검증 실행은 없음
- `ManualSourceInspection`: `source_id`, `document_version`, `document_sha256`, `inspected_at`만 받으며 본문, 토큰, 가격, 개인 계좌, 출처 URL을 임의 입력받지 않는다
- `assess_offline_documentation(endpoint, inspections, now)`: 오프라인에서 API와 자료 ID의 상호 일치, 중복, 이상한 버전/해시/미래 시각을 검증
- 출력 `DocumentationGapReview`는 어느 문서의 메타정보가 검토 목록에 기재됐는지만 보여준다. 출처를 적었다는 뜻이지 **실제 파일 바이트를 검증하거나 문서 작성자·내용·서명을 확인했다는 뜻이 아님**
- KR는 해당 API 예제+설정 메타데이터 모두 입력 시 `KR_DOCUMENTED_EXAMPLE_ONLY`로 표시. 다른 KR API의 반대 설정은 `CROSS_ENDPOINT_CONTEXT`로 구분
- US는 `MODP` 설명 및 백테스터 예제를 확인해도 `US_EXAMPLE_WITHOUT_PROVIDER_ATTESTATION`까지만 표시; 공급자 확정된 가격조정 의미를 인정하지 않는다
- **양 시장 모두 MD-04B의 6개 결손 이유를 하나도 해제하지 않는다.** `EVIDENCE_INSUFFICIENT`, provider_observed_at=NULL, price_basis_attested=false, provider_finality_attested=false, is_final=false, promotion/publication/analysis/automatic_storage_allowed=false 고정
- Pydantic API/SQLAlchemy/기존 UI/스케줄러와 연결하지 않는다. DB에 MD-04C4 증빙 링크를 실제로 기록하지 않는 독립 순수 진단이다

## 추후 실제 검증이 필요한 사항 (모두 미확인)

1. KR/US **해당 조회 API별** 원주가·수정주가 값의 공식 계약, 배당·액면 분할·합병 등 기업행동 반영 범위, 정정 후 시계열 재조회 기준
2. 해외 `MODP` 0/1 의미 및 NQ/NYSE/AMEX 코드별 종목 지원 범위, 제공되는 일봉이 정규장/장외·프리마켓을 포함하는지
3. 제공자의 원천 관측시각 (수신 `fetched_at`와 구분), 확정 종가 확정/정정 완료 여부, 정정 창/재공표 절차/개별 종목 거래정지
4. 공식 휴장·조기 마감 달력의 기간별 출처와 특수일정 변경 기록, 원주가·수정주가 대비 일별 수정·보정 이력
5. 공급자 서명/독립 증빙을 어느 정도로 확보해야 `FINAL` 정책을 별도 승인할 수 있는지. **현행 MD03 price_bar의 CHECK를 해제하지 않으며** 다음 단계 승격도 별도 정책/DB PR 필요

실제 KIS 호출·신규 토큰·모의/실계좌 데이터 확인, MiniPC DB migration/백업/배포, 가격/손익·매매신호/알림 공개는 별도 명시적 승인 대상이다. 이번 Draft PR과 GitHub CI만으로 그 어떤 운용 권한도 부여되지 않는다.
