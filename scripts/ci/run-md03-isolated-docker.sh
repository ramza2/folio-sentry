#!/usr/bin/env bash
# MD-03 synthetic PostgreSQL validation. NEVER touch production DB or containers.
# --preflight is read-only. --run needs an explicit isolated-container approval.
set -Eeuo pipefail
umask 077

fail() { printf 'FOLIOSENTRY_MD03_DOCKER_GUARD_FAIL=%s\n' "$1" >&2; exit 2; }
usage() {
  echo 'Usage: bash scripts/ci/run-md03-isolated-docker.sh --preflight'
  echo '       bash scripts/ci/run-md03-isolated-docker.sh --run APPROVE_MD03_EPHEMERAL_DOCKER_ONLY'
}
MODE="$1"
case "$MODE" in
  --preflight) test "$#" -eq 1 || { usage; exit 2; } ;;
  --run)
    test "$#" -eq 2 || { usage; exit 2; }
    test "$2" = "APPROVE_MD03_EPHEMERAL_DOCKER_ONLY" || fail "CONFIRMATION_REQUIRED"
    ;;
  *) usage; exit 2 ;;
esac

# Caller must archive this review branch to /tmp or /var/tmp first.
ROOT="$(pwd -P)"
case "$ROOT" in /tmp/*|/var/tmp/*) ;; *) fail "TEMP_ARCHIVE_DIRECTORY_REQUIRED" ;; esac
test ! -e "$ROOT/.git" || fail "REPOSITORY_WORKTREE_NOT_ALLOWED"
for file in \
  backend/pyproject.toml \
  backend/alembic.ini \
  backend/app/database.py \
  backend/app/price_repository.py \
  backend/migrations/env.py \
  backend/migrations/versions/20261120_pricebar01.py \
  backend/scripts/test_price_bar_isolated_ci.py
do
  test -f "$ROOT/$file" || fail "INCOMPLETE_REVIEW_ARCHIVE"
done
if [[ -v FOLIOSENTRY_DB_PASSWORD_FILE || -v FOLIOSENTRY_DB_PASSWORD ]]; then
  fail "HOST_DB_SECRET_ENV_PRESENT"
fi
if [[ -v KIS_APPKEY || -v KIS_APPSECRET ]]; then
  fail "HOST_KIS_SECRET_ENV_PRESENT"
fi

command -v docker >/dev/null || fail "DOCKER_UNAVAILABLE"
docker info >/dev/null 2>&1 || fail "DOCKER_DAEMON_UNAVAILABLE"

# The production containers are only inspected for IMAGE IDs. Never docker
# exec into them, copy their configuration, access secrets or alter volumes.
BACKEND_LIST="$(docker ps -q \
  --filter label=com.docker.compose.project=foliosentry-prod \
  --filter label=com.docker.compose.service=backend)" || fail "BACKEND_DISCOVERY_FAILED"
DB_LIST="$(docker ps -q \
  --filter label=com.docker.compose.project=foliosentry-prod \
  --filter label=com.docker.compose.service=db)" || fail "POSTGRES_DISCOVERY_FAILED"
[[ "$BACKEND_LIST" =~ ^[0-9a-f]{12,64}$ ]] || fail "EXPECTED_ONE_OPERATING_BACKEND"
[[ "$DB_LIST" =~ ^[0-9a-f]{12,64}$ ]] || fail "EXPECTED_ONE_OPERATING_POSTGRES"

BACKEND_IMAGE="$(docker inspect --format '{{.Image}}' "$BACKEND_LIST")" \
  || fail "BACKEND_IMAGE_UNAVAILABLE"
PG_IMAGE="$(docker inspect --format '{{.Image}}' "$DB_LIST")" \
  || fail "POSTGRES_IMAGE_UNAVAILABLE"
PG_SOURCE="$(docker inspect --format '{{.Config.Image}}' "$DB_LIST")" \
  || fail "POSTGRES_SOURCE_UNAVAILABLE"
[[ "$BACKEND_IMAGE" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "BACKEND_IMAGE_INVALID"
[[ "$PG_IMAGE" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "POSTGRES_IMAGE_INVALID"
test "$PG_SOURCE" = "postgres:17-alpine" || fail "POSTGRES_IMAGE_NOT_APPROVED"
docker image inspect "$BACKEND_IMAGE" >/dev/null 2>&1 || fail "BACKEND_IMAGE_MISSING"
docker image inspect "$PG_IMAGE" >/dev/null 2>&1 || fail "POSTGRES_IMAGE_MISSING"

echo "FOLIOSENTRY_MD03_ISOLATED_IMAGES_LOCAL_ONLY=PASS"
echo "FOLIOSENTRY_MD03_PRODUCTION_CONTAINERS_INSPECT_ONLY=PASS"
echo "FOLIOSENTRY_MD03_PRODUCTION_DB_CONNECTIONS=0"
echo "FOLIOSENTRY_MD03_REAL_KIS_REQUESTS=0"
if test "$MODE" = "--preflight"; then
  echo "FOLIOSENTRY_MD03_ISOLATED_DOCKER_PREFLIGHT_PASS_NO_CONTAINERS_STARTED"
  exit 0
fi

# One short-lived synthetic DB, no network, no published ports or persistent
# volume. Never call compose, stop an operating service, or pull an image.
PG_CID=""
cleanup() {
  local rc=$?
  trap - EXIT
  if test -n "$PG_CID"; then
    docker rm -f -v "$PG_CID" >/dev/null 2>&1 || true
  fi
  if test "$rc" -ne 0; then
    echo "FOLIOSENTRY_MD03_ISOLATED_DOCKER_TEST_FAILED" >&2
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

PG_NAME="foliosentry-md03-synthetic-$$-$RANDOM"
PG_CID="$(docker run -d --pull never \
  --name "$PG_NAME" \
  --label foliosentry.synthetic.md03=yes \
  --network none \
  --memory 768m --pids-limit 128 \
  --tmpfs /var/lib/postgresql/data:rw,nosuid,nodev,size=512m \
  --tmpfs /run/postgresql:rw,nosuid,nodev,size=32m \
  --env POSTGRES_DB=folio_ci \
  --env POSTGRES_USER=folio_ci \
  --env POSTGRES_PASSWORD=ci-only-not-a-real-secret \
  "$PG_IMAGE")" || fail "EPHEMERAL_POSTGRES_START_FAILED"

test "$(docker inspect --format '{{.HostConfig.NetworkMode}}' "$PG_CID")" = none \
  || fail "POSTGRES_NETWORK_NOT_ISOLATED"
test -z "$(docker port "$PG_CID")" || fail "POSTGRES_HOST_PORT_EXPOSED"

ready=0
for i in $(seq 1 50); do
  if docker exec "$PG_CID" \
      pg_isready -h 127.0.0.1 -U folio_ci -d folio_ci >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
test "$ready" -eq 1 || fail "EPHEMERAL_POSTGRES_NOT_READY"
echo "FOLIOSENTRY_MD03_EPHEMERAL_POSTGRES_READY_NETWORK_NONE"

# A NEW Python process joins ONLY this disposable PostgreSQL network namespace.
# Use the already-local backend IMAGE for dependencies, mounting the archive
# as read-only source. No host/home/production secrets, keys or source volumes.
docker run --rm --pull never \
  --network "container:$PG_CID" \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m \
  --cap-drop ALL --security-opt no-new-privileges \
  --memory 768m --pids-limit 128 \
  --mount "type=bind,source=$ROOT/backend,target=/workspace/backend,readonly" \
  --workdir /workspace/backend \
  --env FOLIOSENTRY_DB_HOST=127.0.0.1 \
  --env FOLIOSENTRY_DB_PORT=5432 \
  --env FOLIOSENTRY_DB_USER=folio_ci \
  --env FOLIOSENTRY_DB_NAME=folio_ci \
  --env FOLIOSENTRY_DB_PASSWORD=ci-only-not-a-real-secret \
  --env FOLIOSENTRY_MD03_ISOLATED_DB_TEST=yes \
  --env PYTHONPATH=/workspace/backend \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env PYTHONUNBUFFERED=1 \
  "$BACKEND_IMAGE" sh -eu -c '
    # The reused operating image has an older installed app. Force and verify
    # all application imports from the read-only Git archive BEFORE migration.
    python -c "
from pathlib import Path
import app
from app import market_data, price_models, price_repository
root = Path(\"/workspace/backend/app\").resolve()
for module in (app, market_data, price_models, price_repository):
    location = Path(module.__file__).resolve()
    assert location.is_relative_to(root), \"MD03_WRONG_BACKEND_SOURCE_IMPORT\"
print(\"FOLIOSENTRY_MD03_ARCHIVED_SOURCE_IMPORT_PASS\")
"
    python -m alembic upgrade head
    python -m scripts.test_price_bar_isolated_ci
    python -c "
from sqlalchemy import text
from app.database import get_engine
with get_engine().connect() as conn:
    version = conn.execute(text(\"SELECT version_num FROM alembic_version\")).scalar_one()
    assert version == \"20261120_pricebar01\", \"ISOLATED_SCHEMA_VERSION_MISMATCH\"
    assert conn.execute(text(\"SELECT count(*) FROM price_bar\")).scalar_one() == 0
print(\"FOLIOSENTRY_MD03_ISOLATED_POSTGRES_REVISION_AND_EMPTY_PASS\")
"
  '
echo "FOLIOSENTRY_MD03_ISOLATED_POSTGRES_INTEGRATION_PASS"
echo "FOLIOSENTRY_MD03_PRODUCTION_CONTAINERS_CHANGED=NO"
echo "FOLIOSENTRY_MD03_PRODUCTION_DB_CHANGED=NO"
