# Phase 1 운영 전환 계획 — 기존 HTTPS 서비스 유지

기준: 2026-11-19 `main@1f81e35416a9f29dc51a643c9dd16830fc61829b`에서 사용자가 읽기 전용 DB 검사 `FOLIOSENTRY_PHASE1_PREFLIGHT_PASS`, `DB_STATE=PHASE1_SCHEMA_PENDING_EXPECTED` 확인.

상태: **운영 마이그레이션·이미지 교체 미실행**. 이 문서는 실 운영 변경에 대한 자동 승인이 아니며, 각 단계는 사전 확인 및 사용자 별도 승인 후 실행해야 한다.

## 목표와 범위

- 기존 `foliosentry-prod` PostgreSQL, HTTP(s) 라우터와 세션, PickNext, Traefik, HomeVoice 보존.
- 신규 스키마 `instrument`, `tracked_instrument`를 사용자 승인한 경우에만 **additive** Alembic revision `20261119_portfolio01`로 적용.
- Backend 이미지를 새 코드로 변경, 이어서 Frontend를 UI-03로 변경.
- **자동 백업 없음**: 사용자가 `foliosentry-backup.timer`를 `inactive/disabled`로 설정했고 기능 개발 우선을 선택함. 타이머 재활성화·강제 백업·기존 백업 파일 삭제 금지.
- DEMO 화면과 실제 수동 등록 화면은 분리. 실제 등록 종목에 가짜 가격/손익 자동 생성 금지.
- 기존 `scripts/deploy.sh publish` / `db-init` **사용하지 않음**: 각각 신규 HTTPS 게시·최초 DB 초기화용이며, 이미 공개 중인 라우터 충돌과 불필요한 백업/재생성 위험이 있다.

## 0. 읽기 전용 사전검사 (승인 없이 가능)

```bash
cd ~/folio-sentry
# 아래 스크립트가 병합된 최신 main을 ff-only 동기화한 다음
bash -n scripts/phase1-live-preflight.sh
bash scripts/phase1-live-preflight.sh
```

기대: `FOLIOSENTRY_PHASE1_LIVE_READONLY_PREFLIGHT_PASS`, `DB_SCHEMA=AUTH01_PENDING_PHASE1`, `BACKUP_TIMER=INACTIVE_DISABLED`.

이 스크립트는 **현재 실제 컨테이너가 기동 중**인지, DB revision과 소유자 수, backend/frontend의 **현재 이미지 ID**를 확인한다. 이미지 ID는 별도 비공개 운영 메모에 보존하고 인증 값·DB 레코드는 기록하지 않는다. Docker/DB 변경 명령이 없다. 스크립트 실패 시 모든 후속 단계 중단.

## 1. 이미지 준비 (별도 명시 승인 필요)

미래 승인된 시점에만 아래를 시행하며, 실행 시 기존 이미지 태그가 새 빌드 이미지로 바뀔 수 있으나 **실행 중인 컨테이너를 자동 교체하지 않는다**.

```bash
cd ~/folio-sentry
DC=(docker compose --project-name foliosentry-prod --env-file .env.deploy -f compose.production.yml)
DE=(docker compose --project-name foliosentry-prod --env-file .env.deploy -f compose.production.yml -f compose.traefik.yml)

# 0단계의 현재 이미지 ID를 별도 기록한 뒤:
"${DE[@]}" build backend frontend
```

중요: 롤백을 위해 이전 Backend/Frontend 이미지 ID가 여전히 존재하는지 확인한다. `docker image prune` 금지.

## 2. DB 테이블 추가 (별도 명시 승인 필요)

운영 DB에서 `20261119_auth01`이 정확히 확인된 뒤 **딱 한 번** 실행한다.

```bash
"${DC[@]}" run --rm --no-deps backend alembic upgrade 20261119_portfolio01
```

그 다음 **읽기 전용 SQL**로 `alembic_version='20261119_portfolio01'`, `auth_owner=1`, 신규 두 테이블 존재, `instrument`와 `tracked_instrument` 0건을 확인한다.

새 테이블 추가는 기존 인증 구조를 건드리지 않지만 PostgreSQL DDL이므로 실제 DB 변경이다. 자동 rollback/downgrade를 수행하지 않는다. 실패 시 재실행 전에 migration 현재 상태 확인.

## 3. Backend만 교체 (별도 명시 승인 필요)

```bash
"${DC[@]}" up -d --no-deps --no-build backend
```

- `foliosentry-prod-backend`만 대상으로 하며 DB/Frontend/다른 프로젝트는 업데이트하지 않는다.
- 새 Backend 컨테이너 `healthy` 및 앱 라우터(`/api/v1/tracked`, `/api/v1/instruments`) 존재 여부를 내부에서 확인한다.
- Nginx는 백엔드 호스트명을 정적으로 해석하므로 Backend 컨테이너 교체 후 **Frontend 교체 전까지 API가 일시적으로 502가 될 수 있다**. 테스트/전환 시간은 이용자가 없는 때로 잡고 다음 단계를 준비한다. 무중단을 보장하지 않는다.
- 문제 발생 시 이전 Backend 이미지 ID로 **Backend만** 되돌리는 별도 승인/검증 경로를 사용한다. 추가된 DB 테이블은 파괴적 삭제 없이 유지할 수 있다.

## 4. Frontend만 교체 (별도 명시 승인 필요)

```bash
"${DE[@]}" up -d --no-deps --no-build frontend
python3 scripts/verify-public-https.py
```

- 기존 `proxy`, `websecure`, `myresolver`, DuckDNS/Traefik/라우터/공유기를 수정하지 않는다. Docker Compose는 FolioSentry frontend 컨테이너만 갱신한다.
- HTTPS TLS/정적 HTML/Backend health/익명 `auth/me`·DEMO 401/Origin 없는 login 403/기존 PickNext TLS 확인.
- 기존 브라우저 소유자 로그인 후 DEMO 대시보드, 신규 **실제 종목 관리** 페이지 진입, 빈 목록, 수동 등록 폼·기본 입력/삭제 등의 인수검사를 합성 종목으로만 시행.
- Backend/Frontend 변경에서 오류가 발생하면 현재 증거 확보 후 중지. 실 운영 데이터 DB downgrade/volume 삭제/전체 compose down 금지.

## 5. 남은 게이트

- 사용자 명시적 운영 DB migration/Backend/Frontend 교체 승인
- MiniPC 기동 중인 이전 컨테이너 이미지 ID·별도 compose 네트워크 확인
- 신형 Backend/Frontend 이미지 CI 통과, production compose config PASS
- 마이그레이션 후 DB revision 및 익명 API 401, 로그인/세션 유효성 확인
- 브라우저 수동 인수, 기존 PickNext 동작 확인
- 자동 백업 타이머는 **계속 비활성화** (백업 정책을 임의로 선행 조건으로 만들지 않음)

## 2026-11-20 Phase 1 마이그레이션 PASS / 운영 배포 준비

- MiniPC 실 검증: `FOLIOSENTRY_PHASE1_DB_MIGRATION_PASS`, `DB_RESULT=PHASE1_DB_SCHEMA_PASS`, 인증 계정/세션 보존, 두 신규 테이블 0건. DB 재마이그레이션 금지.
- 준비된 Backend/Frontend 신규 이미지 빌드 PASS, 현재 운영 실행 중인 것은 계속 기존 이미지. 기존 롤백 태그 보존.
- 최초 운영 앱 배포 커맨드는 `app.routes`를 평면 목록으로 전제해 새 API가 누락됐다고 판단하여 사전검사 단계에서 AssertionError로 중단. 실 배포는 일어나지 않음.
- 원인: FastAPI 0.137+는 `include_router()`를 `_IncludedRouter`로 중첩 등록. `app.routes` 직접 평면 순회는 잘못된 검사. 해당 라우트는 Backend 소스 및 이미지의 `portfolio.router.routes=7`에 정상 등록.
- 수정된 GitHub 배포 스크립트 `scripts/phase1-app-deploy.sh`는 FastAPI 제공 `get_openapi(title, version, routes=app.routes)`로 중첩 경로를 검증하고, 기존 운영 이미지·DB Revision·자동 백업 비활성 상태 확인 후 Backend → Frontend만 교체한다.
- 2026-11-19의 사전 검사 스크립트 `phase1-live-preflight.sh`는 AUTH01 전용이므로 **마이그레이션 완료 후에는 재실행하면 실패하는 것이 정상**. 이제 앱 전환 전용 스크립트를 사용한다.
- 사용자가 직접 실행: `bash scripts/phase1-app-deploy.sh --confirm-phase1-app-deploy`. 실행 전 main 동기화 필요. 사전검사 실패면 컨테이너 변경 없음; 교체 이후 오류면 기존 이미지 롤백 시도. DB downgrade/backup timer enable/Traefik 변경 없음.
