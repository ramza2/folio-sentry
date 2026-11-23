# OPS-CI03 — CI 최적화 × KIS MD-02/MD-03 사전 통합 스냅샷 (2026-11-23)

## 목적과 원본
- 운영 main `c156cfd9e094c747caf3f9c48ecf73eee5759699` 변경 없이 **검토 전용** 소스 조합 준비.
- 소스 A: `ci/usage-control-20261120` @ `684309266ebbb495958352b3902acedce51f7d18` (CI 라우터, CI gate, Browser 수동 실행, offline 검증)
- 소스 B: `review/md02-md03-stdlib-offline-gate-20261120` @ `20631a96f9aca9fda669b619714641fc15d8d492` (Draft PR #24/#25/#26 코드 통합본 + 합성 토큰/일봉 테스트 + 일회용 PostgreSQL 검사)
- CI A의 워크플로·라우터·unit test·감사 스크립트를 B에 **선별 적용**, AGENTS.md·ROADMAP.md는 B 내용을 유지하면서 별도 통합 결과 기록.
- 두 기존 소스 브랜치와 PR #24~#27, CI branch는 수정하지 않음. 별도 통합 검토 브랜치 `review/ci-kis-offline-integration-20261123`.

## 통합 시 자동 적용할 품질 게이트
1. `.github/workflows/ci.yml` 트리거: main PR / main push / 명시적 수동 실행만. feature 브랜치 push 중복 실행 중단. 이전 실행 concurrency 취소 및 stable `ci-gate`.
2. `changes` job: Python stdlib CI routing/최종 gate/보안검사/통합 계약 단위 테스트 수행. KIS 합성 검증 파일이 존재할 때만 `python3 -I -B scripts/ci/md02_md03_offline_acceptance.py` 실행 (**네트워크/실 키/DB 없음**).
3. MD-03 마이그레이션 파일과 격리 검사 스크립트 동시 존재 여부 확인. `20261120_pricebar01` 및 price_bar 스키마와 `backend/scripts/test_price_bar_isolated_ci.py` 합성 PostgreSQL 필수 검증 보존.
4. Backend `pytest`, Frontend npm test/typecheck/build, Compose, 배포 설정 및 백업 합성 검증 라우팅 유지.
5. AUTH Chrome/Playwright 브라우저 E2E는 수동 실행 전용.
6. 미확인 경로, CI 스크립트 또는 워크플로 변경은 **전체 필수 작업** 검사로 fail-closed.

## 오프라인 검증과 결과의 범위
- 기존 **단독 실행 결과**: CI 최적화 stdlib 28/28 PASS + YAML 파싱 PASS; KIS/가격 통합 stdlib 10/10 PASS; 임시 PostgreSQL 실 DB E2E SAVEPOINT·UNFINALIZED CHECK·롤백 PASS(모두 사용자 MiniPC 2026-11-23 이전 제공 로그).
- **2026-11-23 MiniPC 통합 코드 실행 완료**: Python unittest 38/38 PASS, 합성 KIS 10/10 PASS, YAML 파싱 PASS. hosted GitHub Actions/Runner는 여전히 미검증.
- 최종 결합 stdlib unittest **38/38 PASS** (기존 CI 28 + MD03 Docker 계약 6 + 통합 계약 4). 별도 KIS 순수 stdlib **10/10 PASS**.
- Github Actions 실제 runner, required checks, docker PostgreSQL runner가 연계된 최종 Actions는 무료 할당량 갱신 전 확인할 수 없음. MiniPC 운영 이미지/DB/서비스에도 **이 통합 버전을 적용하지 않음**.
- PR #24~#27 기능 자체는 Draft/미병합 상태를 유지하고, KIS 자동 수집·최종 가격/손익·알림·실전 주문/잔고 API를 연결하지 않음.

## 안전 실행
- GitHub SHA 검증 후 임시 `git archive`로 `.github/workflows`, `scripts/ci`, `scripts/public-visibility-preflight.py`, `backend`만 추출.
- `python3 -m unittest discover -s scripts/ci -p 'test_*.py'`, `python3 -I -B scripts/ci/md02_md03_offline_acceptance.py`.
- PyYAML이 설치되어 있으면 YAML 구조의 `jobs` 매핑이 8개인지 검사. optional YAML 파서는 GitHub-hosted Actions 실행 검증을 대체하지 않음.
- 이번 통합 테스트에서 `scripts/ci/run-md03-isolated-docker.sh --run`은 **호출하지 않음**. 기존 합성 PostgreSQL 검증 PASS를 재실행할 필요 없음.
- Private 유지. `main` 병합/운영 배포/DB migration/실 KIS 토큰 발급 및 실호출은 사용자 별도 승인 후 진행.

## MiniPC 전원 종료 기록
- 이전 테스트 즈음 MiniPC가 꺼지고 정상 부팅(2026-11-23 11:24 KST), journal에 unclean shutdown 기록 존재.
- 가족으로부터 **집 전원 스위치가 꺼져 있었고 다시 켰다는 메시지**를 받았으므로 외부 전원 차단이 가장 유력한 설명. 장비 하드웨어 장애와 Docker 테스트가 원인이라는 증거는 없음. 정확한 전원 이벤트와 메커니즘은 별도 실증 전까지 단정하지 않음.
- 복구 후 운영 FolioSentry Docker 3개 Healthy, 일회용 MD03 컨테이너 잔존 없음(사용자 확인).