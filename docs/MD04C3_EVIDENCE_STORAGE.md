# MD-04C3 — 시세 품질 증빙 메타데이터의 버전드 격리 저장 (2026-11-23)

상태: **Draft PR / 합성 GitHub CI 격리 PostgreSQL 전용**. 운영 MiniPC DB에는 신규 테이블이 존재한다고 가정하지 않으며, 운영 migration/배포/실 KIS 토큰·시세 조회는 미승인.

## 설계 원칙

1. **거래소 세션 마감 ≠ KIS 제공자 최종 종가**. 기존 MD-03/04A/04B 품질검사를 통과해도 최종 종가 또는 공개 가능한 시세로 승격하지 않는다.
2. 기존 price_bar의 PARTIAL, is_final=false, source_observed_at IS NULL 강제 제약을 변경하지 않는다. 품질 증빙은 별도 price_quality_evidence 테이블에 가격 **없이** 저장한다.
3. fetched_at은 시스템이 수신한 시각이다. reviewed_at은 시스템이 정적 정책으로 검사한 시각이다. 두 시각 모두 공급자 원천 관측시각이 아니다. source_observed_at은 반드시 NULL.
4. 공급자 최종성, RAW/ADJUSTED 가격 기준의 검증, 사후 시세 정정 규정, 권리·기업행동 반영의 **외부 증빙이 없음**을 각기 다른 필드로 나타낸다. 보수적인 MD04C3_V1 정책은 상태 전이를 지원하지 않는다.
5. 저장은 외부 트랜잭션에서 명시적 allow_write=True인 경우에만 허용. 같은 price_bar/policy 재검사는 멱등 NOOP(최초 reviewed_at 보존), 모순된 이력은 검토 오류, 임의 덮어쓰기/커밋 금지.
6. 이 스키마는 운영 API/Frontend/신호/알림/스케줄러에 연결하지 않는다. MD-04C2 quote-status 조회도 계속 UNAVAILABLE/null.

## 신규 스키마 (선택적 운영 적용은 차후 별도 승인)

- Migration: backend/migrations/versions/20261123_quality01.py
- SQLAlchemy: backend/app/quality_evidence_models.py
- 저장소: backend/app/quality_evidence_repository.py
- 테이블: price_quality_evidence, FK price_bar.id ON DELETE RESTRICT
- UNIQUE(price_bar_id, policy_version), 정책 버전은 MD04C3_V1 고정
- reviewed_rows=1, evidence_status=UNVERIFIED, provider_finality=UNATTESTED
- source_observed_at=NULL, basis_attested=false, correction_attested=false, corporate_action_attested=false
- is_final=false, publication_allowed=false, analysis_allowed=false
- blocker_codes는 MD-04B가 산출한 고정 6개 결손 reason code만 저장 (가격·종목·계좌·인증정보·KIS 응답 원문 없음)
- **DB CHECK가 확정/검증/공개 허용 오염을 거부**. blocker_codes의 정확한 목록과 타입·순서는 repository에서 검증. 애플리케이션은 테이블의 데이터를 이용해 최종 시세를 산출할 수 없음.

이 설계는 증거 출처와 검증 규칙을 버전화하기 위한 **비확정 데이터 이력**이며, 독립된 공급자 서명/정정 이력, 원문 증빙을 저장하거나 증명하는 기능이 아니다. DB 사용자가 직접 UPDATE/DELETE할 수 있으므로 외부 운영 계정 권한 제어·감사 로깅/완전한 append-only 보장은 향후 별도 설계가 필요하다.

## CI 오프라인 검증

- Python pytest는 위조된 is_final, source_observed_at, publication_allowed, 보고서 가격/근거 누락, 잘못된 timestamp에 대해 저장 거부를 확인한다.
- auth-db-migration GitHub-hosted PostgreSQL은 합성 folio_ci/127.0.0.1 전용. CI Alembic HEAD가 20261123_quality01인지 검증하고 두 테이블의 초기 0행을 확인한다.
- backend/scripts/test_quality_evidence_isolated_ci.py는 전용 환경변수·호스트·DB명·계정 가드가 모두 일치할 때만 실행된다. 한국/미국 합성 일봉 -> MD-04B 비확정 검증 -> MD-03 PARTIAL 보관 -> 버전드 비가격 증빙 INSERT 및 idempotent NOOP -> DB CHECK 위조 승격 차단 -> 전체 ROLLBACK/0행 확인.
- GitHub Actions의 CI 선택 라우팅 및 마지막 CI gate 유지. 새 migration과 격리 테스트 파일은 반드시 함께 존재해야 하며 한쪽만 있으면 fail-closed.
- 운영 MiniPC의 price_bar migration 여부는 아직 확인되지 않았고 운영 데이터에 대한 스키마 변경은 이 PR의 승인 범위 밖이다.

## 후속 승인 게이트

1. **PR 병합 승인**: GitHub main에 코드만 병합. 운영 MiniPC에는 아무것도 적용하지 않음
2. **운영 DB 적용 승인**: MiniPC 현행 schema/백업/격리 복원/마이그레이션 비교 및 별도 운영자 확인. 실제 이전 revision의 적용 여부를 먼저 확인
3. **실 KIS 재조회 승인**: 토큰 공유/발급 빈도, 한국·미국 일봉 요청 정책 및 거래소별 수정주가 의미 확인. 이 단계와 별도
4. **최종성·증빙 v2 승인**: 공급자 원천 시각·정정/기업행동 이력을 신뢰할 수 있는 1차 근거로 확보한 뒤 버전드 검증 정책과 DB CHECK 변경을 별도 설계/검토
5. **공개/손익/신호·알림 승인**: 충분한 안전 검증 후 별도 기능 PR 및 인수검사. 미확정/STALE/오류 가격은 사용 금지

CI PASS 또는 이 PR 병합만으로 실제 시세를 표시하거나 운영 DB를 변경해서는 안 된다.
