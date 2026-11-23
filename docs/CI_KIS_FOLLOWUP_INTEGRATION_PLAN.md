# OPS-CI07 — CI/KIS 순차 병합 검증 PASS 및 후속 5파일 반영 계획 (2026-11-23)

## MiniPC 최종 증거
- 검토 스크립트 `review/ci-kis-merge-rehearsal-20261123@ca705b0fb73ac3b619fc480bc4e956585c3524bf`.
- 안전/회귀 unittest **14/14 PASS**, GitHub 원본 고정 SHA 및 Git root 사전검사 **PASS**, 23개 원본 핵심 코드 Git blob 일치.
- 순차 합성 3-way merge (임시 bare Git 저장소 내부 전용): `CI=0`, `PR #24=2`, `PR #25=2`, `PR #26=3`. **총 충돌 처리 7건**, 고유 파일은 `AGENTS.md`, `docs/ROADMAP.md`, `.github/workflows/ci.yml` **3개**.
- 모든 합성 충돌은 기존 통합 검토본 `review/ci-kis-offline-integration-20261123@0c1c22ada265a3607d0436f7b138b79356cf7f56`의 3개 해당 blob을 임시 Git index에서 대입해 해소. 최종 핵심 코드 **23/23 MATCH**, 관리 파일 **3/3 MATCH**.
- 후속 테스트 5개는 독립 CI→#24→#25→#26 순차 병합에는 **미포함**으로 정상 분류(`FOLIOSENTRY_SEQUENTIAL_FOLLOWUP_NOT_INCLUDED_COUNT=5`). 비정상 파일 조회 실패를 `git ls-tree --name-only`로 해결.
- 최종 `FOLIOSENTRY_SEQUENTIAL_NO_GITHUB_PUSH_OR_MERGE=YES`, `FOLIOSENTRY_SEQUENTIAL_REVIEW_COMPLETE_NOT_PRODUCTION_APPROVAL`, `FOLIOSENTRY_SEQUENTIAL_LOCAL_REVIEW_COMPLETE` 모두 확인.
- 별도 선행 검증: CI+KIS 통합 브랜치 오프라인 unittest **38/38 PASS**, KIS 합성 동작 **10/10 PASS**, YAML 파싱 PASS; MD03 일회용 PostgreSQL E2E PASS. 하지만 **이번 순차 병합 합성 결과 전체를 다시 pytest/CI Runner로 실행한 것은 아니다.**

## 원본의 후속 5파일 (내용을 GitHub 원본에서 재확인)
후속 파일은 검토 기준 브랜치의 복사본이므로 실제 반영은 독립 PR #24/#25/#26 병합과 GitHub Actions 런타임 검증 후 승인받아 별도의 회귀 테스트 PR로 수행한다. 핵심 기능 소스에 수정/실전 호출을 요구하지 않는다.

| 파일 | 검토본 Git blob SHA | 역할 및 주의 |
|---|---|---|
| `backend/tests/test_market_data_integration.py` | `23ea4133f333b3bae4f4a69f929c1cff50df862f` | pytest/SQLAlchemy 기반 KIS 토큰·시세 모듈 간 오프라인 통합 불변식 검증. 실제 KIS·운영 DB 금지 |
| `scripts/ci/md02_md03_offline_acceptance.py` | `d9bf9e01839b68c70fb8ab5f7ee7c491a326e784` | 순수 stdlib 10개 합성 transport/token/시세 품질 계약, 네트워크 차단 |
| `scripts/ci/test_ci_kis_combined_contract.py` | `e84d8ff167d5cea56bdd160c85a7967bbc204975` | CI workflow/운영 API 비연동/MD03 DB 계약 정적 unittest 4개 |
| `scripts/ci/run-md03-isolated-docker.sh` | `9c0ba98e76ee0c4d32ed96e8ff3f3face41cc955` | **운영 DB와 분리된** 일회용 PostgreSQL 수동 검증 스크립트. 기본 preflight only, `--run`은 별도 확인 문자열 필요 |
| `scripts/ci/test_md03_isolated_docker_contract.py` | `dbed27748eba0a5de312948f0a8b5bb96b0d866c` | 위 격리 Docker 스크립트의 실행 전 안전 계약 unittest 6개; 테스트 자체 Docker 미실행 |

## 향후 반영 순서 (현재는 수행하지 않음)
1. **GitHub Actions 무료 할당량/비용 재확인**. Private 유지, 무조건 Actions 실행하거나 재과금/공개 전환하지 않음.
2. CI 최적화 병합 검토 및 실제 Runner `ci-gate` 확인 → PR #24 → #25 → #26 각각 별도 승인·실제 hosted CI 검증 후 병합. 실제 충돌은 `AGENTS.md`, ROADMAP 및 CI Workflow의 개발 이력과 안전 검사들을 보존하도록 최신 main에서 단계별 재조정해야 한다.
3. #26 반영 후 별도 통합 회귀검증 PR에 우선 **통합 pytest 1개 + stdlib 오프라인 게이트 1개 + CI 결합 계약 1개**를 가져와 검토. 실제 소스 변경 여부와 주입 인터페이스를 비교해 당시 브랜치 기준 코드로 재검증할 것.
4. **격리 DB 검증 스크립트와 안전 계약 1쌍**은 별도 검토·추가한다. 이들은 기존 일회용 PostgreSQL E2E PASS를 근거로 준비된 파일이지만 운영 Docker/DB 환경을 변경하지 않는다. 재실행은 실제 이득이 있을 때만 명시적 승인받고 수행.
5. 통합 테스트를 자동 CI `changes` job에 추가했을 경우, 테스트 파일 이동/경로·마이그레이션 동기화 및 전체 CI YAML 구조를 다시 확인한다. **GitHub-hosted Actions CI 최종 성공 전 main 운영 배포 승인 불가**.
6. KIS 실전 수집, 실제 증권 계좌/시세/손익·신호 UI, 운영 DB migration·배포는 각각 별도 의사결정이다. 자동 연결 금지.

## 안전 경계
- 현재 완료 범위는 **충돌 없는 최종 코드 구성 가능성의 순차 합성 검증**까지다. 합성 Git commit은 리뷰용이며 실제 main에 재사용하거나 push하지 않는다.
- 원본 Draft PR #24~#27, CI 브랜치, GitHub Actions runner, MiniPC Docker/DB/토큰 및 `main` 불변. 저장소 Private 유지.
- 최신 소스/브랜치 SHA가 변하면 검증된 이전 결과를 새로운 코드에 그대로 적용하지 않는다.
