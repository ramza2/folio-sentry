# MD-03 격리 PostgreSQL 로컬 E2E 게이트 (2026-11-23)

## 상황
- 사용자 MiniPC에서 MD-02/MD-03 표준 라이브러리 합성 통합 테스트 10/10 PASS: FOLIOSENTRY_MD02_MD03_STDLIB_OFFLINE_GATE_PASS, FOLIOSENTRY_MD02_MD03_LOCAL_REVIEW_COMPLETE.
- 이번 단계는 PR #26의 실제 PostgreSQL 스키마와 PARTIAL/UNFINALIZED CHECK, 멱등 INSERT, 중간 충돌 SAVEPOINT, 전체 rollback 검증을 준비한다. 아직 실제 MiniPC Docker E2E PASS가 아니다.
- FolioSentry는 Private 유지. KIS 실 API/운영 DB/운영 Docker Compose/기존 백업/웹 UI/실 데이터/인증정보 불변.

## 운영 격리 정책
1. 실행 중인 foliosentry-prod Backend·PostgreSQL 컨테이너를 Docker label로 발견한 후 **이미지 ID만 inspect**한다. 운영 컨테이너 exec·stop·restart·실 환경변수·비밀파일·데이터베이스 접근 금지.
2. 현재 설치된 PostgreSQL 17 이미지로 별도 합성 DB 컨테이너를 생성한다. --network none, --tmpfs PGDATA, 영구 볼륨·published port 없음. 합성 DB/user=folio_ci, 합성 password.
3. 별도 Python 테스트 컨테이너는 운영 Backend의 로컬 이미지에서 의존성만 재사용한다. 격리 브랜치 backend/ 소스만 **읽기 전용**으로 마운트한다.
4. 이 Python 컨테이너는 일회용 PostgreSQL과 네트워크 namespace만 공유하므로 127.0.0.1:5432로 합성 DB에 접속할 수 있다. 외부 인터넷/Docker 기존 네트워크 및 KIS API 접근 불가.
5. Alembic upgrade head와 MD03 합성 PostgreSQL 저장 테스트를 일회용 DB에서만 실행한다. revision 20261120_pricebar01, price_bar 행수 0 확인.
6. 기존 이미지가 없거나 운영 컨테이너를 정확히 판별하지 못하면 fail-closed. Docker pull/build, pip install, sudo, compose down 없음.
7. --preflight 모드는 읽기 전용 Docker inspect만 수행. --run APPROVE_MD03_EPHEMERAL_DOCKER_ONLY는 새 컨테이너 2개 생성/정리하므로 Docker CPU/RAM을 짧게 사용한다.

## MiniPC 사용 절차
- GitHub review/md02-md03-stdlib-offline-gate-20261120 최신 커밋을 SHA 검증하여 git archive로 backend 및 scripts/ci/run-md03-isolated-docker.sh 를 /tmp 임시 위치에 추출한다.
- 임시 아카이브에서 bash -n scripts/ci/run-md03-isolated-docker.sh 실행.
- Python 표준 라이브러리 테스트 스크립트 scripts/ci/test_md03_isolated_docker_contract.py 의 unittest 실행.
- bash scripts/ci/run-md03-isolated-docker.sh --preflight 실행.
- 안전 검사가 PASS인 경우에만 bash scripts/ci/run-md03-isolated-docker.sh --run APPROVE_MD03_EPHEMERAL_DOCKER_ONLY 를 실행한다.

## 최종 성공 마커
- FOLIOSENTRY_MD03_ISOLATED_DOCKER_PREFLIGHT_PASS_NO_CONTAINERS_STARTED
- FOLIOSENTRY_MD03_BATCH_SAVEPOINT_ATOMICITY_PASS
- FOLIOSENTRY_MD03_ISOLATED_INSERT_DUPLICATE_CONFLICT_FINALITY_PASS
- FOLIOSENTRY_MD03_ISOLATED_ROLLBACK_PASS
- FOLIOSENTRY_MD03_ISOLATED_POSTGRES_REVISION_AND_EMPTY_PASS
- FOLIOSENTRY_MD03_ISOLATED_POSTGRES_INTEGRATION_PASS

## 미검증
- 이 스크립트를 MiniPC에서 실제 실행하지 않았으므로 PASS 선언 금지.
- GitHub hosted CI와 실 KIS 데이터 최종성, 사용자 DB 마이그레이션·운영 서비스 배포까지 보장하지 않는다.
- 전체 반영 전 PR #24/25/26/27과 CI 최적화 브랜치는 별도 미병합 상태, main 불변.

## 2026-11-23 1차 MiniPC Docker 실행과 Python import 보정
- 사용자 실행에서 Bash 구문 PASS, 격리 안전 계약 5/5 PASS, Docker 읽기 전용 사전검사 PASS, FOLIOSENTRY_MD03_EPHEMERAL_POSTGRES_READY_NETWORK_NONE PASS를 확인했다.
- 이후 실제 테스트에서 ModuleNotFoundError: No module named 'app.market_data'로 중단했다. 따라서 DB 저장·원자성·finality CHECK E2E는 실패/미완료이며 성공 기록을 남기지 않는다.
- 원인 추정: 운영 Backend 이미지가 보유한 이전 설치된 app 패키지가 새 격리 아카이브의 app 소스보다 먼저 검색됨. 수정: 오직 새로운 Python 테스트 컨테이너에 PYTHONPATH=/workspace/backend 지정, python -m scripts.test_price_bar_isolated_ci 방식 사용.
- 더 안전하게 Alembic 이전 app/market_data/price_models/price_repository 모듈의 __file__ 경로가 모두 /workspace/backend/app 아래인지 확인한다. 다른 경로가 섞이면 MD03_WRONG_BACKEND_SOURCE_IMPORT로 중단한다.
- 1차 실패 후 임시 컨테이너 잔존 여부는 별도 확인 필요. 원래 스크립트의 EXIT trap이 종료 중 docker rm -f -v 실행을 시도했지만 실제 삭제 성공은 독립적으로 확인되지 않았다. 운영 컨테이너·볼륨 정리 금지.
- 수정본은 새 커밋에서 로컬 무실행 테스트/사전점검/격리 E2E를 다시 확인한다. 이번 수정으로 운영 이미지/DB나 실 KIS 상태는 변경하지 않는다.
