# OPS-LOCAL-CI01 — Windows(WSL2) Local CI Gate v1 (2026-11-23)

## 목적
FolioSentry Private 저장소에서 GitHub-hosted Actions 무료 할당량에 의존하지 않고 Windows 개발 PC의 **WSL2(Ubuntu/Linux)** 에서 Backend·Frontend·KIS 합성 테스트를 수행한다. Cursor Agent Windows **토큰 사용 없이** PowerShell 또는 WSL 터미널에서 실행한다.

**중요:** KIS 공유 상태 게이트 `backend/app/kis_shared_state.py` 는 Linux `fcntl.flock` 기반이다. Windows의 네이티브 Python으로 동등한 KIS 테스트를 수행했다고 표시하면 안 된다. 이 Local CI는 Linux(WSL2 포함) + Python **3.12 이상** 필수. Full Mode는 Node **22.17 이상**, npm 필요.

### 구현 파일
- `scripts/ci/local_gate.py`: SHA 검증, GitHub private origin allowlist, tracked 변경 거부, **Git archive 고정 스냅샷**을 Linux 임시 폴더에 추출하고 테스트 후 정리.
- `scripts/ci/local-gate.ps1`: Windows PowerShell에서 `wsl.exe` 호출, 선택한 SHA/모드 전달. Cursor AI 불필요.
- `scripts/ci/test_local_gate.py`: stdlib 안전 계약 7개. 별도 네트워크/실 KIS/DB 불필요.

### 안전 경계
- `git rev-parse HEAD`가 사용자가 지정한 **40자리 SHA**와 다르면 중단; tracked 변경 있으면 중단; 원격은 `ramza2/folio-sentry` 공식 GitHub SSH/HTTPS URL만 허용(자격증명 URL 거부).
- Git worktree에서 테스트를 직접 수행하지 않는다. `git archive`로 지정 SHA 소스를 별도 OS 임시 디렉터리에 추출한다. 임시 아카이브에 path traversal/symlink 발견 시 중단. `.git`와 로컬 `.env`는 포함하지 않음.
- 테스트 subprocess에는 시스템 경로/최소 언어 설정만 전달; OS에 설정된 KIS·DB·계좌/토큰/GitHub 인증 키/프록시 변수는 상속하지 않는다. DB HOST=127.0.0.1, PORT=1은 **의도된 불가 접속** 경계.
- 실 KIS API/token 발급·실계좌 잔고/주문, Docker, 운영 DB·Compose·Traefik, 외부 서비스/회사 Gateway, GitHub Actions 실행/PR 병합/배포 **없음**.
- `offline` 기본 모드는 패키지 설치/네트워크 사용 없음(단, 기존 source Git의 로컬 명령). `full` 모드에서는 사용자가 **`--install-deps`를 명시한 경우에만** pip, npm 레지스트리에서 다운로드. 의존성 설치·build output은 **임시 스냅샷 안에만** 생성.
- 일반 외부 네트워크 차단은 OS 방화벽/WSL 네트워크 격리 설정으로 별도 적용해야 한다. 본 스크립트는 `offline` 테스트에서 네트워크를 의도적으로 호출하지 않지만 OS 수준 네트워크 격리라고 주장하지 않는다.
- 로그는 `~/folio-sentry-local-ci-reports/<UTC시각>-<SHA 앞12자>/`에 로컬 파일(0600)로 저장하며 업로드하지 않는다. 결과 `report.json`에는 SHA, 작업명, PASS/FAIL, 실행 시간만 저장. 문제 발생 시 **로그 전체를 무심코 공유하지 말고 비밀정보 확인**.
- Full mode는 DB migration PostgreSQL 서비스 테스트, Docker E2E, 원격 Actions 실행, 실제 KIS 데이터를 **N/A**로 표시한다. 이전 MD03 일회용 PostgreSQL E2E PASS는 별도 증거로 유지하되 Full mode와 합산해 하나의 새로운 PASS라고 표현하지 않는다.
- 로컬 PASS는 GitHub Branch Protection의 required status check를 자동 충족시키지 않는다. 필요시 관리자가 정책을 검토하고 **사용자 별도 승인** 후 변경한다.

## Windows 준비
1. Windows PowerShell에서 `wsl --list --verbose`를 실행하여 Ubuntu/WSL2 설치를 확인한다. 미설치라면 WSL2 준비에 대한 사용자 결정이 필요하며, **현재 작업이 자동 설치하지 않는다**.
2. Windows PC에 FolioSentry의 **별도 개발용 Private clone**을 둔다. 운영 MiniPC `~/folio-sentry`가 아닌 Windows 전용 clone을 사용한다. 저장소 실 `.env`, 한국투자증권 비밀 키 파일을 로컬 CI clone에 복사하지 않는다.
3. GitHub 검토 브랜치로 checkout하고 **Git HEAD SHA 일치**, `git status --porcelain --untracked-files=no` 비어있음 확인. 소스에 실비밀은 추가하지 않는다.
4. PowerShell에서 기본 오프라인 실행:
   ```powershell
   .\scripts\ci\local-gate.ps1 -ExpectedSha "<실제 검증 대상 커밋의 40자리 SHA>" -Mode offline
   ```
5. WSL Ubuntu 터미널을 이미 사용한다면 직접 실행:
   ```bash
   python3 -B scripts/ci/local_gate.py --expected-sha "<40자리 HEAD SHA>" --mode offline
   ```
6. 의존성 다운로드를 허용하고 전체 Backend·Frontend 정적/단위 테스트를 실행할 때만:
   ```powershell
   .\scripts\ci\local-gate.ps1 -ExpectedSha "<40자리 HEAD SHA>" -Mode full -InstallDeps
   ```

## 모드별 검증
| 모드 | 실행 작업 | 별도 미검증 |
|---|---|---|
| `offline` | `scripts/ci/test_*.py` unittest (CI/병합/KIS 계약) + KIS MD02/03 합성 `md02_md03_offline_acceptance.py` | Backend 의존성 pytest/Frontend 빌드/PostgreSQL/ACTIONS |
| `full -InstallDeps` | `offline` 전체 + 임시 venv 설치 + Backend pytest + compileall + 임시 frontend npm ci + npm test/typecheck/build | Docker/PG migration/E2E/운영 KIS/원격 Actions |

안전 계약 테스트의 Git fixture는 `TemporaryDirectory` 안에서만 생성된다. 위 작업의 모든 출력/종료 코드는 JSON 보고서와 `FOLIOSENTRY_LOCAL_CI_...(PASS/FAIL)` 마커로 확인한다. 필수 검사가 하나라도 FAIL이면 전체 FAIL로 종료한다.

## 첫 실행 이후
- GitHub 검토 브랜치 HEAD를 확인한 후 **Windows WSL2에 동일 SHA**를 checkout해 검사한다. 검사 결과가 정상이어도 이 스냅샷을 main에 바로 병합하지 않는다.
- Local CI Gate가 검증되면 PR #24, #25, #26 병합 준비 단계에서 GitHub-hosted Actions 대신 사용자가 승인한 **동일 SHA 로컬 검증 증거**를 제출할 수 있다.
- 병합 직전 새 HEAD SHA로 동일 Gate 반복(필요 시 PostgreSQL 격리 검사 별도), 결과 보고 및 사용자의 명시적 승인 필수.

## 완료 조건
- [x] Local CI Gate Python·PowerShell·순수 unittest 코드 작성
- [ ] Linux/WSL2에서 오프라인 안전 계약·KIS 합성 Gate 실제 실행 PASS
- [ ] WSL2에 Python/Node/npm/네트워크 연결 확인 후 Full Mode 테스트 PASS
- [ ] 전체 GitHub Actions required checks 충족 여부는 별도 확인
- [ ] main/운영 DB/실제 KIS/배포는 별도 명시 승인
