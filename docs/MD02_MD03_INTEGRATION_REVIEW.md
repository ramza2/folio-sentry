# PR #24 / #25 / #26 일괄 사전 검토 (GitHub Draft 통합본)

목적: 독립 Draft PR 3개가 병합되기 전에 **순수 합성 CI만으로 함께 호환되는지** 검토한다. 최종 main 병합 승인이나 운영 배포를 의미하지 않는다.

## 구성
- PR #24: 일회성 KIS 비밀키 로컬 등록·점검 도구. 2026-11-20 사용자의 최초 실전 조회 3회 PASS는 과거 기록이며 **재실행 금지**.
- PR #25: 선택형 프로세스 공유 토큰 캐시/호출량 관리. 토큰 저장에는 평문 0600 파일 및 백업 보호가 필요. 기본 실전 토큰 발급 거부.
- PR #26: KIS 일봉 검증/추가형 price_bar 모델·격리 Alembic migration/멱등 INSERT. **시세 is_final=false·quality_status=PARTIAL 고정**.
- PR #26 추가 보정: 2026-11-19 KRX 수능일 10:00-16:30, 미국 11-26 휴장·11-27 및 12-24 13:00 ET 조기 종료. 확인되지 않은 평일도 자동 수집하지 않고 차단.

## 통합 회귀 점검
- 기존 FastAPI main 및 DEMO/포트폴리오 API에 KIS·price_bar import·라우트가 추가되지 않은 상태 확인.
- 합성 자격/전송: live_enabled=False 차단, 공유 상태 활성이나 토큰 발급 기본 거부 시 외부 요청 0회.
- 비확정 일봉 정규화 → 확인된 세션 판정 → 불확정 전용 저장 입구: 기본 allow_write=False 확인.
- CI 기존 6개 작업과 신규 격리 DB migration 체크. 실제 사용자 비밀정보·가격·토큰·운영 DB·Docker 볼륨·MiniPC 없이 수행.

## 리뷰/병합 경계
- 이 PR은 **검토 스냅샷**이다. 24→25→26 순차 병합 시 AGENTS.md/ROADMAP.md 충돌 가능성을 이 분리된 브랜치에서 사전 확인한다.
- PR 별도 코드 리뷰와 main 병합 허가 후에만 통합한다. migration은 main에 반영되더라도 운영 DB에서 자동 실행하지 않는다.
- 실제 KIS 신규 발급/GET, MiniPC 배포, 운영 백업/DB 업데이트는 별도 사용자 승인 없이는 하지 않는다.
- 캘린더는 검증된 몇 날짜만 지원. 전체 KRX·NYSE·Nasdaq 2026년 거래일로 확대하지 않았고 최종 시세 확정 조건도 미구현이다.


## 2026-11-20 코드 리뷰 추가 수정
- **R-01 (PR #25)**: 공유 토큰 상태 JSON을 실수로 삭제했을 때 마지막 발급시각이 사라져 24시간 발급 제한이 우회될 수 있다. 토큰 발급 시도 이전 독립 0600 마커를 생성하고, 발급 시도 기록이 있는데 state 파일이 사라졌다면 KIS_SHARED_STATE_LOST_AFTER_ISSUE로 거절. 테스트: 정상 발급/토큰 발급 실패 각각 상태 소실 후 재발급 시도 0회 확인.
- **R-02 (PR #26)**: 여러 가격 후보 저장 도중 뒤쪽 값 충돌로 예외가 발생하면 호출자가 잡은 뒤 외부 트랜잭션을 커밋할 가능성. 내부 SAVEPOINT로 각 배치를 원자화. 격리 PostgreSQL 합성 테스트에서 신규 ADJUSTED 후보 다음 기존 RAW 충돌 시 신규 후보가 롤백되는지 확인.
- 수정 검증 범위는 PR #27의 CI와 각각의 PR #25/#26 CI뿐. 취약점 진단은 이번 개발 코드에 한정되며 운영 서버나 기존 사용자 데이터를 검사하지 않았다.
- 수동 병합 계획: #24 먼저 리뷰·병합, #25·#26에는 main 최신을 반영하여 AGENTS/ROADMAP 중복 편집과 Alembic revision을 재검증. PR #27 자체는 리뷰 전용으로 **main에 병합하지 않는다**.


## 후속 stdlib 단독 검증(2026-11-20)
- GitHub Actions 차단 중에도 실제 계좌·실 DB에 접속하지 않는 `scripts/ci/md02_md03_offline_acceptance.py`(합성 KIS 응답→PARTIAL 검증, 10 tests) 작성. 검사 코드는 별도 review branch `review/md02-md03-stdlib-offline-gate-20261120`에만 추가, PR #27 자체는 변경하지 않는다.
- 실제 MiniPC 테스트 결과는 아직 수신 전이며 통합 PASS로 기록하지 않는다. 자세한 절차 `docs/MD02_MD03_STDLIB_OFFLINE_GATE.md` 참조.
