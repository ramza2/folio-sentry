# CI 사용량 최적화 및 GitHub 공개 전 안전 확인 (2026-11-20)

## 현재 상황
- GitHub Free 개인 계정의 Actions 포함 사용량: **$12/$12(100%)**. Private 저장소 FolioSentry 관련 사용량이 빠르게 증가한 상황으로 사용자 Billing 스크린샷 확인.
- 실 청구액 0 USD, 결제 수단 미등록. 과금 한도 증가나 카드 등록은 이번 작업에 포함되지 않음.
- 기존 `.github/workflows/ci.yml`: `feat/**` 브랜치 push 및 PR 생성/변경에서 **같은 커밋을 두 번 검사할 수 있음**, 항상 6개 Linux Hosted job, 새 Frontend 이미지 Docker build와 PostgreSQL 격리 마이그레이션/백업 E2E도 실행.
- `.github/workflows/auth-browser.yml`: 과거 `feat/auth01-*` push 때 Chromium+PostgreSQL+폰트 설치 검증. 인증/배포 점검이 필요할 때만 수동 실행하도록 변경.

## 이번 코드 변경 (GitHub만, 실행 미검증)
1. 자동 트리거를 `pull_request(main)` / `push(main)`으로 제한. PR 소스 브랜치에 push할 때 CI가 중복 생성되지 않는다.
2. `concurrency: cancel-in-progress: true`로 같은 PR의 오래된 작업 취소.
3. stdlib `scripts/ci/impact.py`: 변경 파일별로 6개 job 중 필요한 것만 선택. 기준 SHA가 없거나 알 수 없는 파일/워크플로 자체가 수정되면 **전부 실행(fail closed)**.
4. 항상 실행되는 단일 `CI gate`: 결과 JSON을 기반으로 선택된 job은 PASS, 생략한 job은 SKIPPED인지 검사. 변경선별/게이트의 unittest도 라우터 단계에서 실행.
5. Browser acceptance는 `workflow_dispatch` 수동만. 자동 전체 기능 E2E를 생략한 대신 릴리스 인수 때 명시적으로 수동 검사해야 한다.
6. `workflow_dispatch`로 CI 전체 6종 실행 가능. **수동 실행도 Private 상태에서는 월간 한도를 소모하므로 제한 소진 중에는 실행 금지.**

## 변경 영역별 실행 계획
| 변경 범위 | 필수 자동 job |
|---|---|
| 문서만(README/AGENTS/docs/*.md) | `changes` + `CI gate` |
| KIS/시세 수집 등 Backend 단위 코드 | `backend` |
| 인증·모델·가격 저장·Alembic | `backend` + `auth-db-migration` |
| 일반 Frontend UI | `frontend` |
| Frontend Dockerfile.prod / nginx.prod.conf / package 파일 | `frontend` + `deploy01-production-config` |
| compose.yaml | `compose-config` |
| production/traefik Compose | `compose-config` + `deploy01-production-config` + `deploy02-backup-e2e` |
| 백업/복원 스크립트 | `deploy02-backup-e2e` (+ backup-db.sh는 deploy01도) |
| CI 워크플로·라우팅 코드·알 수 없는 파일 | **전체 6종** |
| 수동 `workflow_dispatch` | **전체 6종** |

작업을 나누어 테스트할 뿐, 관련 기능의 단위·격리 DB 검증 자체를 제거하지 않는다. 경로 판단에 실패하면 모든 검사를 실행하며 최종 CI gate에서 선택된 검사의 실제 성공 여부를 확인한다.

## 검증과 병합 조건
- 저장소의 현재 Private Actions 예산이 소진되었으므로 이 브랜치(`ci/usage-control-20261120`)의 **실제 Actions 실행은 아직 PASS 아님**. 별도 환경에서 unittest/YAML 검사 가능한 경우 수행하고, 실행 가능 상태가 된 뒤 GitHub CI 실제 PASS 요구.
- 기존 PR #24~#27은 Draft 및 미병합. 특히 #26에도 `.github/workflows/ci.yml`의 격리 DB 테스트 단계가 추가돼 있어 **CI 최적화와 #26 병합 시 워크플로 충돌을 수동 통합**해야 한다. #26의 `20261120_pricebar01` 검사 절대 제거 금지.
- `CI gate`를 GitHub 필수 확인(required status)으로 사용하는 경우 저장소의 branch protection 설정과 일치시켜야 한다. 다만 문서 변경도 안정적으로 체크가 떠야 하므로 `paths-ignore`로 PR 전체를 생략하지 않는다.
- 이번 변경은 코드/문서만. 실제 KIS 호출, 실 키·개인 계좌 사용, MiniPC 운영 DB/서비스/배포 및 백업 타이머에 영향 없음.

## Public 전환에 관한 실제 영향 및 사전 점검
- GitHub 공식 정책상 **Public 저장소의 표준 GitHub-hosted Runner(ubuntu-latest 등)는 Actions 컴퓨팅 무료**. Private 표준 Runner는 포함 사용량을 소모. 단, Public 저장소의 Larger Runner 등 별도 요금 대상은 예외.
  - https://docs.github.com/en/actions/concepts/billing-and-usage
- GitHub **Private → Public**은 코드와 **모든 접근 가능한 Git 커밋 이력 및 Actions 실행 로그**를 누구나 볼 수 있게 한다. 공개 사용자가 fork/복사할 수 있고 일부 push rulesets 적용에도 변화가 생길 수 있다.
  - https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility
- 현재 FolioSentry GitHub 자료에는 집 MiniPC 사용자명/OS/리소스, 개인 DuckDNS/FQDN, Traefik 라우팅, 서비스 포트, 백업·인증 운영 절차 등 민감할 수 있는 운영 구조가 포함되어 있다. **비밀키가 없어도 보안 노출 범위가 증가**한다.
- `.gitignore`의 `.env` 제외는 새 커밋 보호에만 도움이 된다. **과거 커밋/Actions 로그에 민감정보가 없다는 보증이 아님**. GitHub 최신 트리의 이름만 확인하는 검사는 충분하지 않다.
- 공개 전 적어도 `git log --all`의 전체 파일 이력과 비밀 스캔, GitHub Actions 과거 로그/아티팩트, 개인정보·주택 네트워크 설정·하드코딩된 계좌/도메인 확인이 필요. 비밀이 발견되면 먼저 키 폐기·교체 후 이력 정리. **전체 이력 검증이 끝나기 전에는 Public 변경 권하지 않음**.
- 대안: Private 유지 및 `scripts/ci/impact.py` 기반 경량 CI, 또는 MiniPC와 분리된 독립 실행 환경의 self-hosted runner(보안 격리·유지관리 비용 발생, 개인 운영 MiniPC에 무방비 Runner 설치 비권장).
- Public로 바꿀 때 변경은 사용자 직접 GitHub `Settings → General → Danger Zone → Change repository visibility`에서 실행하며 GitHub에 한 번 게시된 기록은 이후 Private로 되돌려도 사본 회수가 어렵다.

## 추가: Git 전체 이력 사전검사 도구
- `scripts/public-visibility-preflight.py`는 **읽기 전용·표준 Python만 사용**. `git rev-list --objects --all`로 **해당 로컬 클론에 존재하는 참조의 역사적 Git 객체**를 검사한다. 비밀키 헤더/일부 접근 토큰 패턴/비밀번호 할당/운영 접속 주소/민감한 파일 경로의 **건수만 출력**하며 매칭된 값·파일 원문은 출력하지 않는다.
- 사용법: MiniPC에서 `cd ~/folio-sentry` 후 올바른 스크립트를 가져와 `python3 scripts/public-visibility-preflight.py --self-test`, 이후 `python3 scripts/public-visibility-preflight.py` 실행. 단 이번 브랜치는 아직 main 미병합이므로 **git show로 스크립트를 임시 추출**해야 한다. 기존 운영 서비스/DB/KIS API 호출 없음.
- 완전성을 위해 검사 직전 원격 모든 브랜치 및 PR 참조를 안전하게 가져왔는지 확인해야 한다. 이 스크립트는 GitHub 서버에만 있는 과거·닫힌 PR ref, GitHub Actions 로그·아티팩트, LFS, 키의 비표준 인코딩/암호화 내역을 **검증하지 못한다**. 결과에 문제 0건이라고 표시되어도 Public 승인 마커가 아니다.
- 오류나 의심 발견 시 **키 값/매칭 문자열은 절대 채팅에 공유하지 말고**, 의심 항목의 건수·유형만 사용해 안전하게 판단한다.

## 개인키 헤더 2건의 상세 위치 확인 (사용자 검사 후 추가)
- 이전 감사에서 `PRIVATE_KEY_HEADER=2`가 나왔으며 실제 키인지 아직 확인하지 않았다. `scripts/public-visibility-preflight.py --locate-key-headers`는 Git 객체 SHA·파일 경로·해당 행·끝 마커 존재 여부만 출력하고 **키/PEM 원문은 출력하지 않는다**.
- 검사 후 이 메타데이터만 공유한다. `.pem` 파일 내용, 인증키, 토큰 원문을 채팅에 붙여넣지 않는다. 단순 문자열 패턴(가짜 테스트 데이터 포함)인지 실제 키인지는 후속 별도 검토.

## 운영 정보 노출 파일 경로 집계 (2026-11-20)
- MiniPC 읽기 전용 기존 감사에서 운영 엔드포인트 관련 패턴 `OPERATIONAL_ENDPOINT_EXPOSURE=76`건(중복 Git 버전 기준). 아직 Public 공개 범위 검토 미완료.
- `scripts/public-visibility-preflight.py --locate-operational-paths`는 과거 Git 참조의 운영 호스트·내부 IP 패턴이 포함된 **파일 경로 및 Git Blob 버전 수만** 출력한다. IP/호스트명/행 내용/키/비밀번호를 출력하지 않음.
- 원격 전체 ref나 과거 Actions 로그·아티팩트를 보장해서 검사하지는 못한다. 기존 운영 주소·Traefik 경로·개인 홈 구성 공개의 적정성은 사용자가 결정해야 한다.

## 2026-11-20 MiniPC 공개 전 Git 이력 감사 결과 (사용자 제공 로그)
- `python3 scripts/public-visibility-preflight.py --self-test`: `FOLIOSENTRY_PREPUBLIC_SCANNER_SYNTHETIC_SELFTEST_PASS`.
- 전체 로컬 참조에서 첫 감사: reachable 객체 1,195, 텍스트 blob 339, 개인키 헤더 2, GitHub 토큰 패턴 0, AWS 키 패턴 0, Bearer 패턴 0, credential assignment 패턴 0, 민감 파일 경로 0, 운영 엔드포인트 패턴 포함 blob 버전 76.
- **개인키 헤더 2건은 모두 검사기 합성 코드의 테스트 문자열로 확인**:
  - `scripts/ci/test_public_audit.py` blob `086b21d168a7d1ccac213e52643b4703e1ec7a26` line 14.
  - `scripts/public-visibility-preflight.py` blob `b5514b0ecf8bd35dd13a06b26bbb31621e6fa222` line 86.
  - 종료 마커 없음, 각각 직접 GitHub blob 검토 및 테스트 코드 확인. 현재 검출된 2건은 실제 PEM 개인키로 판정하지 않음. 다만 모든 기록·Actions 로그에 비밀이 없다는 증명은 아니다.
- 운영 위치 검사(추가 커밋 포함, 사용자 제공 로그): scanned blob 345, 운영 패턴 포함 blob 버전 **79**, 고유 파일 경로 **12**. 이 수치는 비밀번호 79개도 고유 URL 79개도 아니며 **서로 다른 Git blob 버전 수**.
- 경로/버전 수: `AGENTS.md` 33, `.github/workflows/ci.yml` 14, `docs/TRAEFIK_MINIPC_DEPLOYMENT.md` 8, `scripts/deploy.sh` 8, `scripts/public-visibility-preflight.py` 4, `README.md` 3, `docs/DEPLOYMENT_TARGET.md` 3, `scripts/ci/test_public_audit.py` 2, `scripts/check-duckdns-route.sh` 1, `scripts/check-existing-tls.py` 1, `scripts/phase1-app-deploy.sh` 1, `scripts/verify-public-https.py` 1.
- 검사기 코드 및 테스트 2개는 운영 주소 관련 패턴을 일부러 포함하여 경로 집계에 잡힌다. 나머지 운영 문서·배포·CI는 GitHub main에서도 운영 호스트명이나 라우팅 주소 등의 문구가 실제 확인된다. **해당 문자열의 존재가 곧 자격증명 유출은 아니다.**
- **잔여 미검증**: GitHub Actions 전체 과거 로그/아티팩트, 서버 전용 refs, repo history에 숨어 있는 비정형 인코딩 키, 외부 출판에 적합한 네트워크/인증 설계 공개 범위.
- **결론: FolioSentry는 Private 그대로 유지. Public로 바로 바꾸지 않는다.** 공개가 개발 비용상 꼭 필요하면 운영 코드·역사·Actions 로그를 노출하지 않는 **새 Public 저장소(새 Git 이력, 샘플 도메인·샘플 구성만)**를 별도로 설계·검수. 그렇지 않으면 Private 경량 CI를 먼저 활성화하는 방향.
- CI 최적화 브랜치 `ci/usage-control-20261120`는 단일 branch SHA 코드로만 보관, CI 실행 0회; PR/main 병합이나 visibility 변경은 미승인·미수행.


## 2026-11-20 로컬 CI 단위 테스트 재실행 PASS
- MiniPC에서 사용자 직접 실행: `TARGET=239f5c2716f3866b2072c6d5dad22ea8382ed15e`, `git archive scripts/ci scripts/public-visibility-preflight.py`로 임시 디렉터리에 코드 추출, `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/ci -p 'test_*.py'` 실행.
- **Ran 21 tests / OK**, `FOLIOSENTRY_PREPUBLIC_SCANNER_SYNTHETIC_SELFTEST_PASS`, `FOLIOSENTRY_CI_LOCAL_UNIT_TESTS_PASS`.
- 이전 커밋의 가짜 Git 함수명 오류(`fake` → `fake_git`)는 해당 커밋에서 고쳤다. GitHub Actions 6개 job/최종 gate의 hosted runner 실제 실행은 **아직 검증되지 않았고 PASS로 주장하면 안 된다**.
- 남은 게이트: YAML/Actions 구문 별도 검사와 정상 GitHub hosted 실행 가능해진 후 실제 job/PR 게이트 확인. `main` 병합·운영 배포·Public 전환은 별도 승인 절차.


## Private 최종 결정 및 MD-03 CI 통합 계약 (2026-11-20)
- 사용자가 **Private 유지**를 명시 확정. 기존 Public 전환 검토 자료는 기록 보관용으로만 유지한다. Public 미러 생성도 진행하지 않는다.
- 최적화 CI는 현재 `20261119_portfolio01`만 있으면 종전 격리 PostgreSQL 검증을 수행한다. 추후 PR #26의 `20261120_pricebar01.py`가 포함되면 `price_bar` 존재와 개정판 migration revision을 자동 확인하고 `backend/scripts/test_price_bar_isolated_ci.py`를 격리 합성 DB에 실행한다.
- **PR #26 일부만 병합된 경우 거부**: schema migration과 테스트 스크립트 존재 불일치 시 `MD03_PARTIAL_INTEGRATION_BLOCKED`. 검증에서 `quality_status=PARTIAL` / 최종 확정 금지 / 중복 삽입 처리 검사를 삭제하지 않는다.
- `scripts/ci/test_workflow_contract.py`는 pure Python stdlib로 workflow 트리거·조건·최종 게이트·중요 단계·embedded Python heredoc 구문을 검사한다. **완전한 YAML 파서나 GitHub hosted workflow 검증을 대체하지 않는다.** 실제 Actions가 허용된 다음 CI 검증이 여전히 필요하다.
- 변경 영역 검사기 `scripts/ci/impact.py`는 `scripts/public-visibility-preflight.py` 변경만으로 무거운 테스트를 실행하지 않고, `changes`의 보안 합성 unit test + `ci-gate`를 실행한다. 기타 알 수 없는 scripts 파일/CI 파일 변경은 여전히 전체 6종 검사다.
- 변경 워크플로를 사용자 동의 없이 `main`에 병합하거나 운영 배포/시세 수집/토큰 재발급을 활성화하지 않는다.


## OPS-CI02 최종 오프라인 테스트 사용자 실행 결과 (2026-11-20)
- 검증 대상 커밋: `11f6c508e712fd6f83fa73d25d2e69a86425b7ee`. 사용자 MiniPC에서 `git archive`로 Actions 워크플로/CI 스크립트만 임시 디렉터리에 추출해 읽기 전용·오프라인 검증.
- `python3 -m unittest discover -s scripts/ci -p 'test_*.py' -v`: **Ran 28 tests in 0.006s / OK**. 변화 영역 분류/CI gate/보안 감사/워크플로 불변조건/MD-03 schema+격리 테스트 보존을 확인.
- `FOLIOSENTRY_PREPUBLIC_SCANNER_SYNTHETIC_SELFTEST_PASS`, `FOLIOSENTRY_YAML_PARSE_PASS`, `FOLIOSENTRY_CI_OFFLINE_GATE_PASS` 모두 수신.
- PyYAML 성공은 YAML 구조 파싱 검증만 의미하며 **실제 GitHub Actions Runner 동작, PR 이벤트/required checks, Docker/PostgreSQL E2E 수행을 보증하지 않는다**.
- 검증 이후 문서만 갱신하는 커밋은 검증 코드와 분리. GitHub Actions 사용량/결제 제한 해소 전 신규 Actions 실행, 임의 병합, 운영 MiniPC 배포, KIS 추가 실호출은 하지 않는다.
- 사용자 결론: FolioSentry GitHub 저장소 **Private 유지**.


## 2026-11-23 저장소 공개 전환 완료 — 이전 Private 정책 최신화
- 사용자 직접 `ramza2/folio-sentry`를 **Public**으로 변경. GitHub API `private=false`, `visibility=public` 확인. 본 문서 위의 'Private 유지/전환 금지'는 2026-11-20 당시 결정 기록으로서 **현재 정책이 아님**.
- FolioSentry WSL2 Local CI 전용 경로는 사용자 정리 완료. 앞으로 Private 예산 회복 대기 대신 표준 GitHub-hosted Ubuntu Actions를 CI 기본으로 사용. `pull_request(main)` 한 번, `push(main)` 사후 검사, 브라우저 수동 실행 등 기존 비용·중복 방지 구조 유지.
- 공개용 repo는 `.env`, `.env.*`, `kis_appkey`, `kis_appsecret`, `.secrets/`, 개인 키/백업 파일을 Git에서 제외한다. 실제 키·DB·계좌 정보는 MiniPC의 저장소 외부에만 보관. GitHub Actions는 synthetic credential만 사용.
- 공개 전 과거 Git 이력/Actions logs를 완전히 감사한 적은 없으며 운영 주소/호스트 관련 문서가 이미 공개됨. `.gitignore`는 기존 이력을 지우지 않는다. 실제 민감키가 유출됐다면 즉시 폐기·교체.
- 다음 증빙은 이 변경 브랜치의 신규 Draft PR에 대한 GitHub-hosted CI PASS로 확보하고, 그 후 별도 사용자 승인 없이 `main`/원본 PR #24~#26을 병합하지 않는다.


## 2026-11-23 Public GitHub Runner 최초 실행: 합성 PostgreSQL 초기화 경쟁 보완
- Draft PR #28 Public CI 첫 run `45124193477`: `changes`, `backend`, `frontend`, `compose-config`, `auth-db-migration`, `deploy01-production-config` **6개 PASS**. `deploy02-backup-e2e`만 합성 PostgreSQL의 `database "folio" does not exist`로 FAIL, 이에 따라 `CI gate`도 FAIL.
- 해당 CI 백업 스크립트는 `pg_isready`의 `healthy` 판정 직후 `POSTGRES_DB=folio` 생성이 완료됐다고 가정했으나, PostgreSQL 초기화 과정에서 잠시 불일치할 수 있음. **원인 추정은 로그와 코드에 근거한 초기화 경쟁 조건**이며 실 MiniPC DB 장애라는 증거는 없음.
- 보완: CI 전용 `scripts/test-backup-ci.sh`에서 `SELECT 1` SQL 성공을 최대 40초 대기한 뒤 DDL/합성 백업/격리 복원 테스트 시작. 오류 시 자격증명/DB 데이터 로그를 내보내지 않으며 기존 일회용 Docker 정리 유지.
- `scripts/ci/test_workflow_contract.py`에 SQL-ready 가드 순서 검증 1개 추가. 재실행은 새로운 PR SHA에서 실제 Runner 결과로 확인하며, 수정 전 테스트의 FAIL을 PASS라 표기하지 않음.
