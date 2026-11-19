#!/usr/bin/env bash
# READ-ONLY check for an ALREADY-PUBLISHED FolioSentry Phase 1 upgrade.
# Never deploys, migrates, makes backups or touches Traefik/PickNext.
set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PROJECT=foliosentry-prod
ENV_FILE="$ROOT/.env.deploy"
fail() { echo "PHASE1_LIVE_PREFLIGHT_FAIL=$1" >&2; exit 1; }
command -v docker >/dev/null || fail DOCKER_MISSING
command -v git >/dev/null || fail GIT_MISSING
command -v systemctl >/dev/null || fail SYSTEMD_MISSING
[[ "$(id -u)" != 0 ]] || fail MUST_BE_NONROOT
[[ "$(git branch --show-current)" == main ]] || fail EXPECTED_MAIN
[[ -z "$(git status --porcelain)" ]] || fail WORKTREE_NOT_CLEAN
REMOTE="$(git ls-remote origin refs/heads/main | awk 'NR==1 {print $1}')"
[[ -n "$REMOTE" && "$(git rev-parse HEAD)" == "$REMOTE" ]] || fail MAIN_NOT_SYNCED
[[ -f "$ENV_FILE" && ! -L "$ENV_FILE" &&
   "$(stat -c '%a' "$ENV_FILE")" == 600 ]] || fail DEPLOY_ENV_NOT_PRIVATE

EDGE=(
  docker compose --project-name "$PROJECT" --env-file "$ENV_FILE"
  -f "$ROOT/compose.production.yml" -f "$ROOT/compose.traefik.yml"
)
"${EDGE[@]}" config -q >/dev/null || fail COMPOSE_CONFIG_INVALID

db_cid="" backend_cid="" frontend_cid=""
for service in db backend frontend; do
  mapfile -t all < <(docker ps -aq \
    --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=$service")
  mapfile -t running < <(docker ps -q \
    --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=$service")
  [[ "${#all[@]}" == 1 && "${#running[@]}" == 1 &&
     "${all[0]}" == "${running[0]}" ]] ||
    fail "EXPECTED_ONE_RUNNING_${service^^}"
  [[ "$(docker inspect -f '{{.State.Status}}' "${running[0]}")" == running ]] ||
    fail "NOT_RUNNING_${service^^}"
  if [[ "$service" == db || "$service" == backend ]]; then
    [[ "$(docker inspect -f '{{.State.Health.Status}}' "${running[0]}")" == healthy ]] ||
      fail "NOT_HEALTHY_${service^^}"
  fi
  case "$service" in
    db) db_cid="${running[0]}" ;;
    backend) backend_cid="${running[0]}" ;;
    frontend) frontend_cid="${running[0]}" ;;
  esac
done
[[ -n "$db_cid" && -n "$backend_cid" && -n "$frontend_cid" ]] ||
  fail MISSING_SERVICE

# Select-only query; never print owner credentials, sessions or portfolio rows.
state="$(docker exec -i "$db_cid" \
  psql -X -w -q -At -v ON_ERROR_STOP=1 -U folio -d folio <<'SQL'
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10s';
SELECT CASE
 WHEN (SELECT count(*) FROM public.alembic_version) = 1
 AND (SELECT max(version_num) FROM public.alembic_version) = '20261119_auth01'
 AND (SELECT count(*) FROM public.auth_owner) = 1
 AND to_regclass('public.instrument') IS NULL
 AND to_regclass('public.tracked_instrument') IS NULL
 THEN 'AUTH01_PENDING_PHASE1' ELSE 'REVIEW_DB_STATE' END;
ROLLBACK;
SQL
)" || fail DB_READONLY_QUERY_FAILED
[[ "$state" == AUTH01_PENDING_PHASE1 ]] || fail UNEXPECTED_DB_SCHEMA

# User explicitly disabled automatic backups: guard status without changing it.
timer_state="$(systemctl --user show foliosentry-backup.timer \
  -p ActiveState -p UnitFileState --no-pager 2>/dev/null)" ||
  fail BACKUP_TIMER_STATUS_UNAVAILABLE
grep -Fxq 'ActiveState=inactive' <<< "$timer_state" ||
  fail BACKUP_TIMER_UNEXPECTEDLY_ACTIVE
grep -Fxq 'UnitFileState=disabled' <<< "$timer_state" ||
  fail BACKUP_TIMER_UNEXPECTEDLY_ENABLED

echo "GIT_MAIN_SYNCED=PASS"
echo "COMPOSE_CONFIG=PASS"
echo "DB_HEALTH=HEALTHY"
echo "BACKEND_HEALTH=HEALTHY"
echo "FRONTEND_STATE=RUNNING"
echo "DB_SCHEMA=AUTH01_PENDING_PHASE1"
echo "BACKUP_TIMER=INACTIVE_DISABLED"
echo "BACKEND_PREVIOUS_IMAGE=$(docker inspect -f '{{.Image}}' "$backend_cid")"
echo "FRONTEND_PREVIOUS_IMAGE=$(docker inspect -f '{{.Image}}' "$frontend_cid")"
echo "DB_DATA_CHANGED=NO"
echo "CONTAINERS_MODIFIED=NO"
echo "FOLIOSENTRY_PHASE1_LIVE_READONLY_PREFLIGHT_PASS"
