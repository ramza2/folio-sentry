# MD-02/MD-03 통합용 Python 표준 라이브러리 오프라인 검사 (2026-11-20)

## 목적
GitHub Actions 무료 한도가 소진되어도 Draft PR #24/#25/#26의 **통합 코드**가 다음 보안 경계를 지키는지 MiniPC 로컬의 임시 Git 아카이브에서 재현한다.

- **절대로** KIS 실전 토큰 발급·실전 시세 호출·개인 비밀파일 읽기·실 DB 연결·테이블 생성/마이그레이션·실 포트폴리오 변경을 수행하지 않는다.
- Docker 컨테이너, 네트워크, `pip install`, `pytest`, `sqlalchemy` 없이 Python **3.12+ 표준 라이브러리만**으로 수행 가능. (Linux 시스템의 `fcntl` 파일 잠금 사용.)
- 모든 토큰·종목 가격은 명시적인 **합성값**, transport는 테스트 함수. 테스트 중 TCP socket connect도 강제 차단.
- 저장은 `tempfile.TemporaryDirectory`의 보호된 격리 경로에서만 테스트하고 종료 시 정리.
- 실행 범위: 실 KIS 호출이 아닌 token issue deny, 합성 발급→국내/미국 일봉 GET 재사용, 프로세스 공유 rate limit, quote 실패 할당량, 상태 소실 시 재발급 차단, PARTIAL 품질, 휴장/미확인 날짜, DB 저장 기본 거부·원자적 INSERT의 **AST/코드 계약**, Alembic schema CHECK의 **문자열 계약**, FastAPI 운영 라우터 미연결 확인.
- **실제 PostgreSQL 마이그레이션, DB CHECK 실행, KIS 실제 호출, GitHub Actions 호스티드 Runner**는 테스트하지 못한다. PR #26의 기존 합성 PostgreSQL 검증과 GitHub CI PASS 기록을 대신하는 검사는 아니다.

## 실행 방법 (MiniPC, 운영 변경 없음)
```bash
cd ~/folio-sentry
git fetch --no-tags origin refs/heads/review/md02-md03-stdlib-offline-gate-20261120
TARGET="<검증된 커밋 SHA>"
test "$(git rev-parse FETCH_HEAD)" = "$TARGET" || exit 1
TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
git archive "$TARGET" backend scripts/ci/md02_md03_offline_acceptance.py | tar -x -C "$TMP"
cd "$TMP"
PYTHONDONTWRITEBYTECODE=1 python3 scripts/ci/md02_md03_offline_acceptance.py
```
결과는 `FOLIOSENTRY_MD02_MD03_STDLIB_OFFLINE_GATE_PASS` 또는 FAIL. 코드 임포트가 실패하거나 테스트 예외가 생기면 PASS를 출력하지 않는다.

## 병합·운영 금지
- 이 브랜치는 PR #27(검토용 통합 Draft)의 스냅샷 `a8ec184`에서 독립 생성. PR #27·#24~#26의 병합/승인과 무관, main 미변경.
- CI 최적화 `ci/usage-control-20261120` 브랜치에도 자동 병합되지 않음. 장래 통합 시 해당 CI 라우터에서 `scripts/ci` 코드 변경은 **fail closed(6개 전체 검사)**.
- KIS 실전 App Key/Secret과 기존 MiniPC `kis-first-readonly-probe.attempted` 마커를 건드리지 않는다. **승인된 최초 실전 호출을 절대 재실행하지 않는다.**
- FolioSentry는 사용자 확정대로 **Private 유지**.
