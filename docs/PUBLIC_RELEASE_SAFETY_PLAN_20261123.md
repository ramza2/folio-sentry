# FolioSentry 공개 저장소 전환 사전 점검 — 2026-11-23

> **현재 상태: PRIVATE 유지 · 공개 전환 BLOCKED (보안 실사 미완료).** 이 문서는 공개 전 검토용이다. GitHub 저장소 Visibility 변경/이력 재작성/Actions 로그 삭제/로컬 파일 삭제를 실행한 것이 아니다.

## 사용자 요청
- Windows C: 공간 절약: WSL2 Local CI 중단 및 해당 전용 복제본/테스트 결과 정리.
- GitHub-hosted `ubuntu-latest` 무료 CI 사용: 공개 저장소 전환 검토.
- 개인 정보, 한국투자증권(KIS) 실계좌·토큰·API 키는 공개 저장소에 절대 포함하지 않으며 운영 MiniPC에만 저장.

## 1차 GitHub connector 조회 결과 (대상: 현재 Private `main@c156cfd9e094c747caf3f9c48ecf73eee5759699` 및 별도 검토 브랜치 일부)
- 저장소: `ramza2/folio-sentry` **Private**. PR 27개, Actions 실행 이력 다수(조회 시 346 run). 비공개→공개 전환 시 GitHub 공식 정책상 **소스 코드·Git 이력·Actions 과거 로그가 공개**된다. 기존 브랜치/PR/검토용 브랜치도 노출될 수 있다.
- `main/.gitignore`에 `.env`, `.env.*` 제외 및 `!.env.example` 존재함을 확인. 단, `.gitignore`는 과거 커밋·이미 tracking된 파일·액션 로그/Artifacts를 지워주지 않는다.
- 현재 `main`의 1차 파일 18여 개 중 여러 파일에 **집 운영 서버의 호스트·접속 도메인·내부 네트워크 단서 등**이 존재한다. 일부 문서는 WSL/Unix 로컬 사용자 경로와 배포 절차, 가정 내부 Docker·Traefik 네트워크 구조를 상세 기록한다.
- 특히 현재 `main`의 `README.md`, `AGENTS.md`, `docs/DEPLOYMENT_TARGET.md`, `docs/TRAEFIK_MINIPC_DEPLOYMENT.md` 및 일부 배포/진단 스크립트에서 접속환경·운영정보 플래그가 확인됨. 값 자체는 이 보고서에 기록하지 않는다.
- Local CI 검토 브랜치의 `docs/LOCAL_CI_WSL.md`에는 로컬 계정 경로 등이 포함. Local CI의 신규 코드는 `main`에 **아직 병합되지 않았음**.
- 일부 현재 파일에 대해 규칙 기반으로 장문 토큰 유사 패턴을 조회했으나 **그 범위에서는 탐지되지 않음**. 이 결과는 히스토리·비정형 키·로그·커밋 메시지·미검토 파일 전체가 안전하다는 뜻이 아니다.
- 원본 CI/PR #24/#25/#26은 Draft/독립 브랜치로 유지 중이며, 실제 KIS 연결/토큰 발급 및 운영 DB migration은 시행되지 않음.

## 공개 전 필수 조치
1. **기존 Private repo를 그대로 Public로 바꾸지 않는다.** .env와 현재 HEAD만 정리해도 Git 과거 이력, 27개 PR, 346개 기존 Actions 실행 기록이 그대로 공개될 수 있다.
2. 기본 권고: **새 GitHub Public 저장소를 깨끗한 단일 초기 커밋으로 생성**. 소스는 필요한 운영 코드만 별도 검증된 사본에서 가져오고, 개인 운영 주소·호스트명·사용자명·실제 IP·실제 키·전용 배포 로그·내부 도구 링크·특정 직원/회사 시스템 정보를 치환/삭제. 기존 Private 저장소는 **비공개 보관**.
3. 새 공개 저장소 이름/기존 운영 원격 저장소 이전 방식은 사용자 결정이 필요. 기본은 `ramza2/folio-sentry-public` 별도 저장소를 우선 만들고, 현재 Private `ramza2/folio-sentry`와 운영 MiniPC 원격은 그대로 유지하는 **비파괴 방식**. 원래 공개 이름이 꼭 필요할 때만 Private repo rename→새 repo 원래 이름 생성 경로를 별도 승인 하에 진행.
4. 공개용 `README.md`, `AGENTS.md`, 예제 Compose 및 문서에서 개인 네트워크/동작 서버 상세 제거. 변수화: `FOLIOSENTRY_PUBLIC_HOSTNAME`, `FOLIOSENTRY_TRAEFIK_NETWORK`, DB 자격증명, Secret 파일 경로 등은 **실제값 없이** 예제 제공. 공개 CI는 synthetic fixture, 최소 `permissions: contents: read`, PR 등 외부 기여 코드에 credential 미제공.
5. `.env`/ `.env.*`/KIS API 키/개인 보유종목/자산 내역/DB 백업/SSL cert/운영 백업 및 실제 credential 파일이 **현재 트리 및 전체 공개할 Git 객체에 존재하지 않음**을 엄격 검사. 숨겨진 실제값을 `git history`, PR 첨부, 기존 Actions/Artifacts를 포함한 이전 Private 원본에서 절대 가져오지 않는다. **시크릿이 과거 커밋/CI 로그에 존재했다면 교체(rotate) 필수**.
6. 공개 사본에서 최종 전체 파일/커밋 히스토리 검증(`git rev-list --objects --all`, `git grep`, secret scanner, 개인정보/운영 endpoint 검수). `scripts/public-visibility-preflight.py`는 원본 CI 검토 브랜치에 있으며 키/operational 힌트를 찾는 용도; 해당 스캐너 자체도 실제 민감 값을 출력하지 않는다. Scanner PASS만으로 공개 안전 승인 불가.
7. 새 Public 저장소를 준비한 뒤 **공개용 GitHub Actions CI**를 synthetic 테스트로 확인하고, 기존 Private repo의 Draft PR #24~#26 이식은 새 공개 저장소에서 먼저 민감정보가 없는지 확인해 재구성한다. 실제 운영 배포와 연동하는 것은 별도 승인.
8. **Public 변경/새 공개 저장소 생성은 별도 최종 승인 이후에만** 실행한다.

## Windows C: / WSL2 저장소 정리
- 기존 사용자가 성공 실행한 WSL 테스트 repo `~/folio-sentry-localci`, 결과 `~/folio-sentry-local-ci-reports`, 추가 QA 경로 후보 `~/folio-sentry-four-stage-qa`만 대상. 다른 WSL 프로젝트 및 Ubuntu/Node 자체는 남겨둔다.
- 먼저 각 경로 `du -sh`로 크기, Git `status --porcelain`으로 추적/미추적 변경, 결과 보관 필요 여부를 확인. 이후 사용자 명시적 삭제 지시로 **이 세 경로만** 제거한다. `~/.npm`, `~/.cache/pip`는 다른 프로젝트와 공유 가능하므로 검토 없이 삭제하지 않는다.
- WSL2는 가상디스크 `ext4.vhdx`를 사용한다. Linux 파일 삭제 이후 Windows C:에서 사용된 VHDX 파일 크기가 바로 줄어들지 않을 수 있다. 필요한 경우 Microsoft 가이드를 따라 **백업 후 분리/압축**하되, Ubuntu 전체 `wsl --unregister` 금지.
- Local CI gate 파일은 원본 `main`에 없고 이전 review-only 브랜치에만 있으므로 **main에서 삭제할 파일 없음**. GitHub review 브랜치를 삭제하는 것은 과거 개별 검증 근거가 사라지므로 공개 저장소 전환의 필수 조건이 아니다.

## 공개 승인 요약
- [x] Public 표준 GitHub-hosted runner 무료 정책 확인
- [x] Private→Public 시 Actions 과거 실행/로그 공개 정책 확인
- [x] 현재 main과 검토 브랜치 일부 운영·사용자 경로 노출 가능성 발견
- [x] .gitignore가 .env를 제외하는지 확인
- [ ] 기존 모든 Git refs/이력/Actions logs/Artifacts 완전 전수검사
- [ ] 공개 대상만 담은 **새 깨끗한 Git 히스토리** 작성·정적 검사
- [ ] 새 공개 CI/Branch Protection/운영 프로세스와 키 보안 검증
- [ ] 사용자 공개 전환 방식 결정 + **명시적인 최종 승인**
