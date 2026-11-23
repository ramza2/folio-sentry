# OPS-CI09 — CI→#24→#25→#26 파일 스냅샷의 WSL Full CI 테스트 전용 브랜치 (2026-11-23)

> **Review/QA ONLY: main 병합·원본 PR 변경·운영 배포 금지.**

## 생성 목적
- `review/ci-kis-four-stage-candidate-20261123`는 GitHub 4단계 파일 스냅샷을 재구성한 것이며, 합성 순차 실제 merge commit을 main에 병합한 것이 아니다.
- QA 브랜치는 해당 후보의 **동일 핵심 코드 23개 + 충돌 해소 관리 파일 3개** 위에 테스트 전용 파일만 얹었다.
- 5개 후속 통합 검사 파일은 여기서 **테스트 목적으로만 임시 포함**, 실제 CI/PR #24/#25/#26 병합에 자동 포함되지 않는다. 나중에 별도 후속 PR 필요.

## 근거
- 네 단계 기준: `main c156cfd` → CI `141da84` → #24 `d7db77a` → #25 `8b38b3c` → #26 `50e7e1c`. 공통 문서 해소본은 선행 검토본 `0c1c22ada265a3607d0436f7b138b79356cf7f56`.
- 본 QA 초기 소스 commit: `e70618338b584869a26115cafe179193d5e2148c`. 검증 도구·테스트 파일 12개를 `review/local-ci-wsl-gate-20261123@bb6739ac8a360c48bba9ee1aac98cd1ae86bfd44`에서 변경 없이 가져왔다.
- QA 5파일: `backend/tests/test_market_data_integration.py`, `scripts/ci/md02_md03_offline_acceptance.py`, `scripts/ci/test_ci_kis_combined_contract.py`, `scripts/ci/run-md03-isolated-docker.sh`, `scripts/ci/test_md03_isolated_docker_contract.py`.
- Local CI gate 및 순차 rehearsal 등 보조 스크립트 7개는 기능 코드에 영향 주지 않는 별도 QA 도구. 이 브랜치는 **병합용이 아님**.
- 새 문서 커밋 이후 정확한 HEAD SHA를 GitHub에서 다시 확인하여 테스트에 사용해야 한다.

## WSL Full CI 실행
- Windows의 기존 Git 인증으로 해당 Private 브랜치를 임시 clone + git bundle 생성하고, **별도 WSL 폴더** `~/folio-sentry-four-stage-qa`에 복제한다. WSL GitHub 인증 필요 없음.
- 기존 WSL Ubuntu: Python 3.14.4 + python3.14-venv, Linux node 22.17.0/npm 10.9.2 이미 확인됨.
- WSL QA 별도 clone에서 `source ~/.nvm/nvm.sh` 한 뒤 `python3 -B scripts/ci/local_gate.py --expected-sha <QA_BRANCH_EXACT_HEAD_SHA> --mode full --install-deps` 실행한다.
- `stdlib_contracts`, `kis_synthetic`, 임시 venv/pip/Backend pytest/compileall, npm ci/Frontend test/typecheck/build 총 10단계 PASS·exit 0 요구.
- 기본 Local CI는 운영 Docker·DB migration·KIS 실 API·Actions runner를 실행하지 않음. `run-md03-isolated-docker.sh` 스크립트가 소스에 존재하지만 **자동 실행되지 않음**.
- 기존 QA가 아닌 통합 검토 브랜치 `2f322e4`에서 10/10 PASS가 확인돼 있으나 **이번 QA 브랜치는 별도 실 실행 전까지 PASS 아님**.

## 충돌 및 병합 정책
- 원본 Draft PR #24/#25/#26, CI 브랜치, PR #27 및 main의 원본 SHA에 변경 없음.
- github-hosted Actions 및 required statuses는 실행/검증하지 않음. branch rules API는 현재 연결 권한으로 403이므로 정책 확인을 생략하거나 임의 변경하면 안 됨.
- CI 개선 병합 및 각 PR의 실제 병합에는 사용자 별도 명시 승인 필요. 시험 후에도 이 QA 브랜치 자체는 main에 병합 금지.
