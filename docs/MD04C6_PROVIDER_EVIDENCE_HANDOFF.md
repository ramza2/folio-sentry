# MD-04C6 — KIS 공급자 최종성 증빙 요청·수동 검토·별도 승인 게이트 (2026-11-23)

**상태:** GitHub Draft PR용 준비 문서 및 오프라인 합성 체크리스트. **현재 KIS 공급자가 최종 종가를 보증했다는 문서·개별 가격 관측시각·정정 정책의 검증된 자료는 없음**. 이 문서는 공급자에게 문의·검토할 항목을 정의하는 용도이며, 아직 누구에게도 실제 요청을 보내지 않았다. KIS 실조회/토큰 갱신/가격 공개/운영 배포/DB migration 금지.

## 기존 기준

- MD-04C5 PR #35 사용자 승인 병합: main `cae06956dc197ce7bdd3fc5297fb12ef755745e7`; Hosted CI `45150651288` PASS.
- `backend/app/md04c5_source_review.py`의 공식 KIS 예제는 upstream commit `74b0a082fa67a0be5bf53f561719c853890ed2df` 및 Blob SHA를 고정했다. KR itemchart의 `FID_ORG_ADJ_PRC` 문서상 0=수정/1=원주가와 다른 KR 일별 API의 설명 충돌, US dailyprice의 `MODP` 수정주가 반영 예제/주석이 구분된다.
- 위 문서는 API 코드 예시이지 **특정 일봉이 언제 공급자에 의해 확정됐는지**, 추후 정정이 끝났는지, 기업행동 반영이 동일한지 보증하지 않는다.
- MD-04B `UNVERIFIED_REASONS` 6개 유지. `price_bar`는 PARTIAL/is_final=false/source_observed_at NULL만 저장 가능. `price_quality_evidence`는 UNVERIFIED/UNATTESTED, `evidence_reference_revision`은 UNVERIFIED_REFERENCE만 저장. MD-04C2 quote GET은 UNAVAILABLE, 가격·손익 null.
- 공급자 문서 링크, SHA-256 문서 지문, 로컬 검토시각은 진위/최종성 증명이 아니며 권한 승인도 아니다.

## 1. KIS 공급자에 요청할 정확한 확인 항목

다음 항목은 **국내 `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice`와 해외 `/uapi/overseas-price/v1/quotations/dailyprice` 각각 별도**로 공식 답변, 문서 개정 번호, 적용 범위/일자를 요청한다. 해당 API의 TR ID 및 시장 코드는 기존 구현·공식 계약에 맞춰 개별 확인한다.

| 코드 | 공식 질의 | 필요한 근거 유형 |
|---|---|---|
| `PROVIDER_OBSERVATION_RULE` | 응답의 기준 가격 관측/작성/배포 시점은 어떤 필드 또는 규칙으로 확인하는가? 최종 확정시각과 `fetched_at`을 어떻게 구분하는가? | 공급자 정책·필드 정의 및 사례 |
| `PROVIDER_FINAL_CLOSE_RULE` | 정규장 종료 후 종가가 공식 최종으로 확정되는 기준은? 프리마켓/시간외/조기마감, 거래정지 시 어떤 상태를 반환하는가? | 공급자 확정성·거래구간 정의 |
| `ENDPOINT_BASIS_CONTRACT` | 이 API에 한해 KR `FID_ORG_ADJ_PRC` 및 US `MODP` 값 0/1의 원주가/수정주가 의미와 기준일은? 서로 다른 엔드포인트의 설명 차이는 어떻게 해석하는가? | 공급자 공식 파라미터 계약 |
| `PROVIDER_CORRECTION_POLICY` | 당일 종가 수정/정정/재공표가 가능한 시간창·버전/정정 알림·과거 시점 재조회 정책은? | 공급자 정정/재공표 기준 |
| `CORPORATE_ACTION_POLICY` | 액면분할/병합, 무상증자, 배당, 종목 변경 등 기업행동의 주가 조정·과거 시계열 재계산 범위와 적용·정정 정책은? | 공급자 권리·가격 조정 규칙 |
| `PROVIDER_SESSION_SCOPE` | 반환 일봉은 정규장만 포함하는가? 미국 장전/장후, 거래소별 예외·타임존·서머타임·시장 코드의 의미는? | 공급자 시장·세션 지원 정책 |
| `EXCHANGE_CALENDAR_EXCEPTION_POLICY` | KRX/NYSE/Nasdaq 등의 휴장, 조기 마감, 긴급 휴장, 개별 거래정지·특수일을 어떤 권위 있는 시장 일정으로 판정할 것인가? | 거래소 공지/거래일정 공식 문서 |

**시장 거래시간이 끝났다는 증명만으로는 KIS가 반환한 해당 종목/기준의 가격이 최종 확정됐다는 뜻이 아니다.** 특히 마지막 거래소 일정 증빙은 공급자 확정성·세션범위 증빙을 대체하지 않는다.

## 2. 수집 자료의 최소 안전 요건

- 각 API별 공식 제공처/문서·답변의 고정 버전, 변경일, 적용 시장/계약, 참조 코드 및 SHA-256을 기록하고 실제 문서 원본/서명을 **독립된 담당자가 수동 대조**해야 한다.
- GitHub 공개 저장소에는 자료 원문, 개인·계좌·계약·토큰 정보, 실제 응답/가격이나 비공개 공급자 답변을 올리지 않는다. 비공개 원문이 필요한 경우 별도 암호화된 접근제어 저장소/보존 정책부터 승인.
- MD-04C4 이력 DB 및 MiniPC에 임의 자료를 기록하지 않는다. 운영 DB에는 신규 migration가 아직 적용됐는지도 확인되지 않았다.
- 동일 참고자료가 여러 항목을 설명하더라도 항목별 **적용 범위와 일치하는지 별도로 평가**한다. SHA-256 지문만 있거나 GitHub 공식 예제 주석이 있다는 이유로 provider finality를 승인하지 않는다.
- 공급자 답변이 없거나, 응답 간 옵션 설명이 충돌하거나, 정책의 적용 일자·시장범위가 불명확하면 해당 항목은 결손으로 유지한다. 철회된 참고 문서는 증빙 후보에서 제외한다.

## 3. MD-04C6 오프라인 진단 함수

`backend/app/md04c6_evidence_handoff.py`:
- `CandidatePointer(endpoint, requirement, reference_class, reference_code, version_code, document_sha256, recorded_at, lifecycle)`: 사람이 기록한 **참조 후보 메타데이터만** 받는다. 문서 URL·바이트/가격/인증키 입력, 네트워크 접근, 실제 공급자 인증을 수행하지 않는다.
- `EVIDENCE_REQUIREMENTS`의 필수 7개 항목별 `PROVIDER_POLICY_POINTER` 또는 `EXCHANGE_NOTICE_POINTER` 분류를 강제하며, API 간 혼동, 중복 요구사항, 잘못된 식별자·지문·미래시각을 거부.
- `RETRACTED` 기록은 수집 충족으로 세지 않는다. 철회/정정 이력 자체의 타당성 검증은 MD-04C4 독립 검토와 향후 승인 작업의 범위.
- `inspect_supplier_evidence_handoff(endpoint, md04c5_documentation_review, pointers, now)`는 MD-04C5에서 넘어온 `EVIDENCE_INSUFFICIENT`와 6개 결손 플래그를 재검사. 모든 참조가 모이지 않으면 `MISSING_CANDIDATE_REFERENCES`, 모두 모이면 **`METADATA_COMPLETE_HUMAN_REVIEW_REQUIRED`**만 보고.
- **두 경우 모두** `HOLD_UNVERIFIED`, `source_observed_at=None`, `is_final=False`, `promotion_allowed/publication_allowed/analysis_allowed/automatic_storage_allowed=False`, 공급자 진위·사람 승인·정책 승인 모두 false. MD-04B의 여섯 결손 코드는 제거하지 않는다.
- 완성된 후보 목록은 사람에게 제출할 **검토 요청 패킷** 준비 상태만 뜻한다. 신규 가격 기준 승인, 최종 종가 확정 판정, 실제 서비스 API나 거래 전략의 입력값이 아니다.

## 4. 사람 검토 및 실제 승인 절차 (아직 구현/승인되지 않음)

1. **공급자 공식 원문 수령:** 엔드포인트·시장·가격기준별 공식 담당자/포털을 통해 7개 질문의 적용 일자 및 문서 버전/개정 기록 확보. KIS 실 API 호출 없이 문서만 요청할 수 있는 범위부터 진행.
2. **기술 독립 검토:** 담당 개발자가 파라미터·필드·시간대/휴장·원주가/수정주가를 실제 계약과 매핑. 문서 충돌·누락, 비공개 정보/권리 제한을 기록하고 결론을 추정하지 않음.
3. **데이터 정책 독립 검토:** 별도 검토자가 공급자 문서 출처, 최종 확정/정정/기업행동 정책, 허용 목적과 저장·표시 권한을 검토. **동일인 자동 승인 금지**. 현재 코드에는 신원 검증/실제 결재 기능이 없음.
4. **결손별 판단:** MD-04B의 6개 blocker 해소 근거가 각각 충족되는지 별도 이슈/회의록으로 판단. MD-04C6 패킷의 후보 수는 해소 근거가 아님.
5. **별도 구현 PR과 재설계:** 실제 최종성 검증 정책 v2, 기존 PARTIAL-only DB CHECK 변경의 안전성, 정정/권리 이력·롤백, 원본 보존, 조회 허용 범위를 **새로 설계·테스트**. 기존 DB 제약을 이 PR에서 변경하지 않음.
6. **운영 변경 승인 분리:** 소유자 별도 명시 승인 아래 MiniPC 마이그레이션/격리복원, 실 KIS API 호출/토큰, 서비스 배포, 가격·손익 공개 및 알림/신호 기능을 각각 검증하고 승인.
7. **실패 시 HOLD 유지:** 근거 불충분, 서로 다른 문서 설명, 승인 누락, 범위 불일치, 데이터 변조·철회 또는 부정확한 원천 관측시각이면 UI는 계속 UNAVAILABLE, 시세·손익 미계산.

## 5. 이번 단계 제외

- 신규 DB 테이블/마이그레이션, 외부 메일 발송, 공급자 문서 다운로드, 실 KIS 호출/토큰 발급, 자동 스케줄러, 가격·손익/시그널·알림 연계, 기존 API/Frontend 수정, MiniPC 운영 배포·브라우저 인수검사 없음.
- API 인증·운영 계정 승인/출처 진위 검증·서명 검증·2인 결재 UI는 이 문서의 **향후 요구사항**이다.
- GitHub-hosted Backend pytest 및 변경 영향 분석/CI 최종 게이트만 실행. PR 병합도 사용자 별도 승인 필요.

**핵심:** 참조 후보 7개를 입력해도 공급자의 확정 종가가 인증되는 것은 아니며, **최종가 승격과 실제 서비스 공개는 불가능**하다.
