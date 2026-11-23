# OPS-CI08 — 4단계 병합 파일 스냅샷 검토본 (2026-11-23)

> **REVIEW ONLY — 실제 GitHub merge commit, PR 병합 또는 배포로 사용하지 말 것.**
> 이 브랜치는 GitHub Git data API로 구성한 **파일 스냅샷 리허설**이다. 합성 순차 `git merge-tree` 완료는 이전 MiniPC 별도 테스트에서 확인했고, 여기서는 이미 검증된 원본 Git blob을 단계별로 구성한 결과를 확인했다. 두 검증을 혼동하면 안 된다.

## 불변 기준과 4단계 스냅샷
- 출발점 `main@c156cfd9e094c747caf3f9c48ecf73eee5759699`.
- 1단계 `141da8412bd2861656838494262742a045b161a1`: CI `684309266ebbb495958352b3902acedce51f7d18`에서 변경된 12개 파일. **전체 Git tree SHA가 원본 CI tree와 완전히 동일**: `343a0cc089343974707d0f698bce96f24fb8e068`. 이 단계는 원본 CI branch 파일과 동등한 재구성이다.
- 2단계 `d7db77ab76e961a224793ca2296aaed1d37e4301`: PR #24 `88a77b27990c7f23bc0a26917a0c99090fb2776d`의 기존 CI와 충돌하지 않는 실 파일 5개(키 초기 준비 및 read-only probe). 공유 `AGENTS.md`와 `docs/ROADMAP.md`는 이 중간 단계에서 **미반영**.
- 3단계 `8b38b3cc221814e68deca4e2c399579357f4904d`: PR #25 `b8bcbc5bd23613fcecf1117df7e0443fa729d550`의 비충돌 파일 4개(공유 token/state/쿼터/테스트/문서). 공유 문서 변경은 최종 단계로 **유예**.
- 4단계 `50e7e1c742e533ca37c59d6dee292c5ec09a9e48`: PR #26 `9947c90bc5801f42db2891961c95ffbd3e96398a`의 비충돌 실 파일 10개(가격 스키마·캘린더·DB migration·테스트·문서)와 공통 충돌 3파일 최종 교체. `AGENTS.md`, `docs/ROADMAP.md`, `.github/workflows/ci.yml`은 **기존 검토본** `review/ci-kis-offline-integration-20261123@0c1c22ada265a3607d0436f7b138b79356cf7f56`의 blobs를 사용.
- 원본 브랜치 4개의 Git HEAD SHA는 작성 시 모두 고정된 기존 값과 동일함을 확인. 신규 검토 브랜치 외 **main/원본 PR/CI 브랜치 변경 없음**.

## 파일 검증 결과
- 병합될 핵심 코드 파일 **23/23 Git blob SHA 동일**: CI 8 + #24 4 + #25 3 + #26 8. 검토본과 불일치 **0건**.
- 충돌 처리 대상 **3/3 Git blob 동일**: `AGENTS.md`, `docs/ROADMAP.md`, `.github/workflows/ci.yml`. 불일치 **0건**.
- 후속 QA 5파일은 이 **4단계 코드 후보에 미포함**(정상): `backend/tests/test_market_data_integration.py`, `scripts/ci/md02_md03_offline_acceptance.py`, `scripts/ci/test_ci_kis_combined_contract.py`, `scripts/ci/run-md03-isolated-docker.sh`, `scripts/ci/test_md03_isolated_docker_contract.py`.
- `docs/CI_USAGE_CONTROL.md`은 원본 CI 브랜치의 Git blob을 그대로 사용하여, 후속 통합 검토 중 문구가 수정된 리뷰 버전과 **의도적으로 다름**. 원본 CI 이력을 보존한다. 그 외 비교 대상 중 원본·통합 검토본에서 서로 다른 파일은 발견되지 않음.
- 파일 수: 최종 소스 Git tree에서 **118개 regular blobs**, 코드/관리 파일 및 기존 프로젝트 포함.

## 이전 실제 Local CI와 현재 후보의 차이
- 사용자 Windows WSL2의 이전 Full CI **10/10 PASS**는 `review/local-ci-wsl-gate-20261123@2f322e4b8da7d2ac0aa66502d3d398fd87a69b39`에서 수행한 것이다. **이번 스냅샷 전체 커밋에서 아직 Full 실행하지 않음**.
- 이 후보에는 의도적으로 후속 5 QA 파일과 Local CI gate가 없다. QA 파일과 Local CI gate를 추가한 **별도 검토 브랜치**를 준비해 WSL2에서 Full Gate를 실행하는 것이 다음 확인 대상.
- 단계별 검증은 코드 Git blob 일치까지이며 실제 GitHub Actions required check·PR 충돌을 GitHub 자체 병합 처리기로 성공시켰다는 증거가 아님. 중간 단계의 공통 문서 미반영 상태를 실제 main에 병합 금지.

## 안전·향후 의사결정
- 전체 작업은 private GitHub 검토 브랜치에만 적용. 4개 stage commit은 Review 용도로만 사용하고 **fast-forward/merge/squash 방식의 main 반영은 금지**.
- 실제 병합은 원본 CI 브랜치부터 각 단계별로 사용자 **명시 승인**, 최신 main 재검토, required checks 정책 확인, PR 리뷰, PostgreSQL 격리 검증 범위를 분리해 진행.
- 실제 KIS token / account / 계좌 잔고 / 운영 Docker / 운영 DB migration / 실 시세 수집 / UI 배포는 별도 승인 없이는 진행하지 않음.
