#!/usr/bin/env bash
# Roll out the ALREADY-BUILT FolioSentry Phase 1 images to an existing MiniPC.
# Explicitly approved Phase 1 deployment ONLY; never runs Alembic/db-init/publish.
set -Eeuo pipefail
umask 077

[[ "${1:-}" == "--confirm-phase1-app-deploy" && "$#" == 1 ]] || {
  echo "Usage: bash scripts/phase1-app-deploy.sh --confirm-phase1-app-deploy" >&2
  exit 2
}
cd "$(dirname "$0")/.."

OLD_BACKEND="sha256:e0b158cbf7010389d6f367fa910f48ed20aefbbb3a1c5fa044c75773125b4010"
OLD_FRONTEND="sha256:7371a872d862426eaa5c12d6bfe4900be6c6999009edede64ed33304ceb3e372"
EXPECTED_NEW_BACKEND="sha256:e2be1807608a1a9c5692df7fe20b506e43c7d338a6a2824fddc9a63a82cf4797"
PROJECT="foliosentry-prod"
DC=(
  docker compose --project-name "$PROJECT" --env-file .env.deploy
  -f compose.production.yml -f compose.traefik.yml
)
fail() { printf 'FOLIOSENTRY_PHASE1_DEPLOY_FAILED=%s\n' "$1" >&2; exit 1; }

one_running() {
  local service="$1"
  local -a ids=()
  mapfile -t ids < <(docker ps -q \
    --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=$service")
  [[ "${#ids[@]}" == 1 ]] || return 1
  printf '%s\n' "${ids[0]}"
}

wait_backend() {
  local cid health
  for _ in $(seq 1 30); do
    cid="$(one_running backend)" || { sleep 2; continue; }
    health="$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || true)"
    [[ "$health" == healthy ]] && return 0
    sleep 2
  done
  return 1
}

PHASE=preflight
rollback_on_exit() {
  local rc=$?
  trap - EXIT
  if (( rc != 0 )) && [[ "$PHASE" == deploying ]]; then
    echo "===== FOLIOSENTRY_PHASE1_AUTO_ROLLBACK_BEGIN ====="
    if docker tag foliosentry-rollback/backend:pre-phase1 foliosentry-prod-backend:latest \
      && docker tag foliosentry-rollback/frontend:pre-phase1 foliosentry-prod-frontend:latest \
      && "${DC[@]}" up -d --no-deps --no-build --force-recreate backend \
      && wait_backend \
      && "${DC[@]}" up -d --no-deps --no-build --force-recreate frontend
    then
      local b f
      b="$(one_running backend)" || b=""
      f="$(one_running frontend)" || f=""
      if [[ -n "$b" && -n "$f" ]] \
        && [[ "$(docker inspect -f '{{.Image}}' "$b")" == "$OLD_BACKEND" ]] \
        && [[ "$(docker inspect -f '{{.Image}}' "$f")" == "$OLD_FRONTEND" ]] \
        && python3 scripts/verify-public-https.py >/dev/null
      then
        echo "FOLIOSENTRY_PHASE1_ROLLBACK_PASS"
      else
        echo "FOLIOSENTRY_PHASE1_ROLLBACK_MANUAL_REVIEW_REQUIRED"
      fi
    else
      echo "FOLIOSENTRY_PHASE1_ROLLBACK_MANUAL_REVIEW_REQUIRED"
    fi
    echo "DATABASE_DOWNGRADE_ATTEMPTED=NO"
    echo "PICKNEXT_TRAEFIK_MODIFIED=NO"
  fi
  exit "$rc"
}
trap rollback_on_exit EXIT

echo "===== 1. 운영 배포 전 필수 검사 ====="
[[ "$(git branch --show-current)" == main ]] || fail NOT_MAIN
[[ -z "$(git status --porcelain)" ]] || fail DIRTY_WORKTREE
REMOTE="$(git ls-remote origin refs/heads/main | awk 'NR==1 {print $1}')"
[[ -n "$REMOTE" && "$(git rev-parse HEAD)" == "$REMOTE" ]] || fail MAIN_OUT_OF_SYNC
"${DC[@]}" config -q || fail COMPOSE_INVALID

DB_BEFORE="$(one_running db)" || fail DATABASE_CONTAINER_NOT_UNIQUE
B_BEFORE="$(one_running backend)" || fail BACKEND_CONTAINER_NOT_UNIQUE
F_BEFORE="$(one_running frontend)" || fail FRONTEND_CONTAINER_NOT_UNIQUE
[[ "$(docker inspect -f '{{.State.Health.Status}}' "$DB_BEFORE")" == healthy ]] || fail DATABASE_NOT_HEALTHY
[[ "$(docker inspect -f '{{.State.Health.Status}}' "$B_BEFORE")" == healthy ]] || fail BACKEND_NOT_HEALTHY
[[ "$(docker inspect -f '{{.Image}}' "$B_BEFORE")" == "$OLD_BACKEND" ]] || fail BACKEND_BASE_MISMATCH
[[ "$(docker inspect -f '{{.Image}}' "$F_BEFORE")" == "$OLD_FRONTEND" ]] || fail FRONTEND_BASE_MISMATCH
[[ "$(docker image inspect -f '{{.Id}}' foliosentry-rollback/backend:pre-phase1)" == "$OLD_BACKEND" ]] || fail BACKEND_ROLLBACK_MISSING
[[ "$(docker image inspect -f '{{.Id}}' foliosentry-rollback/frontend:pre-phase1)" == "$OLD_FRONTEND" ]] || fail FRONTEND_ROLLBACK_MISSING

timer="$(systemctl --user show foliosentry-backup.timer -p ActiveState -p UnitFileState --no-pager)"
grep -qx 'ActiveState=inactive' <<< "$timer" || fail BACKUP_TIMER_ACTIVE
grep -qx 'UnitFileState=disabled' <<< "$timer" || fail BACKUP_TIMER_ENABLED

NEW_BACKEND="$(docker image inspect -f '{{.Id}}' foliosentry-prod-backend:latest)"
NEW_FRONTEND="$(docker image inspect -f '{{.Id}}' foliosentry-prod-frontend:latest)"
[[ "$NEW_BACKEND" == "$EXPECTED_NEW_BACKEND" ]] || fail NEW_BACKEND_IMAGE_CHANGED
[[ "$NEW_FRONTEND" != "$OLD_FRONTEND" ]] || fail NEW_FRONTEND_IMAGE_MISSING

# Both extra image tags are non-disruptive and keep new artifacts available
# even if a rollback reassigns the 'latest' image names.
docker tag "$NEW_BACKEND" foliosentry-release/backend:phase1
docker tag "$NEW_FRONTEND" foliosentry-release/frontend:phase1

schema="$(docker exec -i "$DB_BEFORE" psql -X -w -q -At -v ON_ERROR_STOP=1 \
  -U folio -d folio <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '10s';
SELECT CASE WHEN
  (SELECT COUNT(*) FROM alembic_version) = 1
  AND (SELECT version_num FROM alembic_version LIMIT 1) = '20261119_portfolio01'
  AND (SELECT COUNT(*) FROM auth_owner) = 1
  AND to_regclass('public.auth_session') IS NOT NULL
  AND to_regclass('public.instrument') IS NOT NULL
  AND to_regclass('public.tracked_instrument') IS NOT NULL
THEN 'PHASE1_SCHEMA_READY' ELSE 'REVIEW_REQUIRED' END;
ROLLBACK;
SQL
)" || fail DB_INSPECTION_ERROR
[[ "$schema" == PHASE1_SCHEMA_READY ]] || fail DB_REVISION_NOT_READY
echo "DB_SCHEMA=PHASE1_SCHEMA_READY"

echo "===== 2. FastAPI 신규 중첩 라우터 검증 ====="
# FastAPI >= 0.137 nests include_router() under _IncludedRouter.
# app.routes is NOT a flat APIRoute list. FastAPI's own get_openapi()
# correctly resolves the nested route tree without enabling public docs.
docker run --rm --network none -i --entrypoint python "$NEW_BACKEND" - <<'PY'
from fastapi.openapi.utils import get_openapi
from app.main import app

spec = get_openapi(title="Private Phase 1 Inspection", version="1", routes=app.routes)
paths = spec.get("paths") or {}
expected = {
    "/api/v1/instruments": {"get", "post"},
    "/api/v1/instruments/{instrument_id}": {"get"},
    "/api/v1/tracked": {"get", "post"},
    "/api/v1/tracked/{tracked_id}": {"patch", "delete"},
}
for path, verbs in expected.items():
    if not verbs.issubset(paths.get(path, {}).keys()):
        raise RuntimeError("MISSING_PHASE1_ROUTE: " + path)
assert all(not getattr(r, "path", None) == "/openapi.json" for r in app.routes)
print("FOLIOSENTRY_PHASE1_NESTED_ROUTER_SCHEMA_PASS")
PY
echo "===== 3. Backend 교체 ====="
PHASE=deploying
"${DC[@]}" up -d --no-deps --no-build --force-recreate backend
wait_backend || fail NEW_BACKEND_NOT_HEALTHY

echo "===== 4. Frontend 교체 ====="
"${DC[@]}" up -d --no-deps --no-build --force-recreate frontend

B_AFTER="$(one_running backend)" || fail BACKEND_NOT_RUNNING
F_AFTER="$(one_running frontend)" || fail FRONTEND_NOT_RUNNING
D_AFTER="$(one_running db)" || fail DATABASE_NOT_RUNNING
[[ "$D_AFTER" == "$DB_BEFORE" ]] || fail DATABASE_CONTAINER_CHANGED
[[ "$(docker inspect -f '{{.Image}}' "$B_AFTER")" == "$NEW_BACKEND" ]] || fail NEW_BACKEND_NOT_ACTIVE
[[ "$(docker inspect -f '{{.Image}}' "$F_AFTER")" == "$NEW_FRONTEND" ]] || fail NEW_FRONTEND_NOT_ACTIVE
[[ "$(docker inspect -f '{{.State.Health.Status}}' "$B_AFTER")" == healthy ]] || fail BACKEND_HEALTH
[[ "$(docker inspect -f '{{.State.Status}}' "$F_AFTER")" == running ]] || fail FRONTEND_NOT_RUNNING

echo "===== 5. HTTPS·익명 인증 회귀검사 ====="
python3 scripts/verify-public-https.py || fail HTTPS_REGRESSION

# Two additional anonymous Phase 1 endpoint checks. Never send user credentials.
python3 - <<'PY'
from urllib.error import HTTPError
from urllib.request import Request, urlopen

for path in ("/api/v1/instruments", "/api/v1/tracked"):
    req = Request("https://foliosentry.ramza.duckdns.org" + path,
                  headers={"Accept": "application/json", "User-Agent": "FolioSentry-Phase1-Smoke"})
    try:
        with urlopen(req, timeout=10):
            raise RuntimeError("Anonymous endpoint unexpectedly accessible: " + path)
    except HTTPError as err:
        assert err.code == 401, (path, err.code)
        assert "no-store" in err.headers.get("Cache-Control", "").lower()
print("FOLIOSENTRY_PHASE1_ANONYMOUS_API_DENY_PASS")
PY
timer="$(systemctl --user show foliosentry-backup.timer -p ActiveState -p UnitFileState --no-pager)"
grep -qx 'ActiveState=inactive' <<< "$timer" || fail BACKUP_TIMER_ACTIVE_AFTER_DEPLOY
grep -qx 'UnitFileState=disabled' <<< "$timer" || fail BACKUP_TIMER_ENABLED_AFTER_DEPLOY

PHASE=completed
echo "===== 최종 결과 ====="
echo "FOLIOSENTRY_PHASE1_APP_DEPLOY_PASS"
echo "DATABASE_MIGRATION_REPEATED=NO"
echo "POSTGRES_CONTAINER_REPLACED=NO"
echo "BACKUP_TIMER=INACTIVE_DISABLED"
echo "PICKNEXT_TRAEFIK_MODIFIED=NO"
