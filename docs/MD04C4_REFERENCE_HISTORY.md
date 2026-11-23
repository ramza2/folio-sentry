# MD-04C4 — 참고자료 출처·버전·정정·철회 이력 (2026-11-23)

상태: **GitHub Draft / 합성 PostgreSQL CI 전용**. 실제 KIS 데이터의 진위·확정 종가·정정 완료를 증명하거나 실제 가격을 공개하는 기능이 아니다.

## 변경 범위

- MD-04C3의 price_quality_evidence (UNVERIFIED/UNATTESTED)에 가격 없는 참조 이벤트 이력 evidence_reference_revision을 추가한다.
- 신규 추가형 Alembic migration: backend/migrations/versions/20261123_quality02.py (기존 quality01 후속). 기존 price_bar의 PARTIAL/is_final=false/원천관측시각 NULL 제약은 변경하지 않는다.
- 기록 필드: quality_evidence_id, revision_no, event_type, source_kind, reference_url, document_version, document_sha256, recorded_at, previous_event_sha256, event_sha256, verification_status=UNVERIFIED_REFERENCE, publication_allowed=false.
- RECORDED → CORRECTED → RETRACTED. 정정은 **참고자료 링크·버전/지문에 대한 메타데이터 정정**으로 주가 OHLCV 정정 이력이 아니다. 철회 후 추가 이력은 불허.
- 1차 기록은 1/RECORDED, 후속은 2,3,... 순서대로 CORRECTED/RETRACTED. 같은 내용 재시도는 NOOP, 같은 revision 번호에 다른 내용은 충돌, 순서 누락이나 철회 후 이력은 거부.
- SHA-256 이벤트 해시는 정규화된 메타데이터와 바로 이전 이벤트 해시를 연결한다. **공급자 서명·원문 진위/최종성 인증이 아닌 로컬 무결성 비교**다. 문서 원문·가격·계좌·보유 정보·토큰은 저장하지 않는다.
- recorded_at은 서버 기록시각이지 공급자 원천 관측시각이 아니다. document_version은 식별 문자열이고 document_sha256은 제공받은 바이트의 지문이므로 독립 공급자 증빙이 아니다.

## 참고 URL 허용 정책

- KIS_DOCUMENT: apiportal.koreainvestment.com 또는 github.com/koreainvestment/open-trading-api/ 하위 HTTPS 경로
- EXCHANGE_NOTICE: global.krx.co.kr, kind.krx.co.kr, www.nyse.com, www.nasdaq.com의 HTTPS
- 사용자정보, 포트, query/fragment, 공백, 인코딩 경로/상위 경로 탐색 등은 거부해 민감한 URL 노출을 방지한다. 도메인 허용은 공식 자료 내용·변경시각·가격 기준 검증이나 외부 접근 권한 확인이 아니다.
- 외부 URL을 코드에서 다운로드하거나 조회하지 않는다. 리다이렉트·원문 수정·공식 공급자 증명은 별도 절차가 필요하다.

## DB 및 애플리케이션 게이트

- backend/app/evidence_reference_repository.py: 호출자 Session/트랜잭션 및 명시적 allow_write=True 필수, 자체 commit/네트워크/DB 엔진 생성 없음. 부모 비확정 증빙 행을 SELECT FOR UPDATE로 잠그고 savepoint 내 insert. 중복 멱등, 다르면 거부.
- DB CHECK: revision_no·event_type·source_kind·SHA 길이·이전해시 유무·UNVERIFIED_REFERENCE·publication_allowed=false 고정.
- PostgreSQL UPDATE/DELETE 차단 트리거를 신규 테이블에만 설치해 일반 작업자의 기록 변경을 거부한다. DB 소유자/관리자는 트리거를 제거할 수 있어 독립적인 불변 원장이라고 주장할 수 없다. 임의 직접 INSERT의 해시 진위를 DB가 보장하는 것도 아니므로 앱의 verify_reference_chain에서 검증한다.
- MD-04C2 인증 GET 상태는 UNAVAILABLE, 가격 및 손익은 null 유지. KIS/실 API/스케줄러/알림 연계 금지.

## 검증

- backend pytest: URL 위장·비밀 파라미터, 잘못된 해시/시간/버전, 해시 연결 및 철회, 체인 조작 차단
- GitHub 격리 folio_ci PostgreSQL: Alembic HEAD=20261123_quality02, MD03/MD04C3 회귀 유지. MD04C4 합성 이력 INSERT/재시도/정정/철회, DB UPDATE·DELETE·공개 승격 시도 차단, 전 행 롤백
- 신규 테스트 스크립트는 FOLIOSENTRY_MD04C4_ISOLATED_DB_TEST=yes 와 loopback/folio_ci 전용 DB/user 일치시에만 실행. 사용자 서버에는 적용 금지.

## 별도 승인 사항

GitHub PR 병합, MiniPC 운영 DB 적용 및 백업·복원, KIS 실조회/토큰, 자료 원문 확보·정정 확인, 가격/손익·신호·알림 공개, 스케줄러는 각각 독립적인 승인 대상이다. MD-04C4에서 FINAL 승격은 불가능하며 외부 근거 확인은 후속 수동 읽기 전용 절차를 통해 검토한다.
