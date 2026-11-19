#!/usr/bin/env bash
# Restore ONE verified FolioSentry archive into an isolated, ephemeral PostgreSQL.
# No Docker network, host ports, persistent volumes, or source DB mutations.
set -Eeuo pipefail
umask 077

[[ "$#" -eq 2 && "${1:-}" == "--confirm-isolated-restore" ]] || {
  echo "USAGE=bash scripts/verify-backup-restore.sh --confirm-isolated-restore ARCHIVE_PATH" >&2
  exit 2
}
[[ "$(id -u)" != 0 ]] || { echo "ERROR=RUN_AS_NORMAL_USER" >&2; exit 2; }
command -v docker >/dev/null || { echo "ERROR=DOCKER_MISSING" >&2; exit 2; }
command -v sha256sum >/dev/null || { echo "ERROR=SHA256SUM_MISSING" >&2; exit 2; }

dir="$HOME/.local/share/folio-sentry/backups"
archive="$2"
[[ -d "$dir" && ! -L "$dir" &&
   "$(stat -c '%a' "$dir")" == 700 &&
   "$(stat -c '%u' "$dir")" == "$(id -u)" ]] || {
  echo "ERROR=BACKUP_DIRECTORY_NOT_PRIVATE" >&2; exit 2;
}
[[ "$archive" == "$dir/"* ]] || {
  echo "ERROR=ARCHIVE_OUTSIDE_FOLIOSENTRY_DIRECTORY" >&2; exit 2;
}
name="${archive##*/}"
[[ "$name" =~ ^(daily|prepublish)-[0-9]{8}T[0-9]{6}Z\.[A-Za-z0-9]{8}\.pgdump$ ]] || {
  echo "ERROR=UNEXPECTED_ARCHIVE_NAME" >&2; exit 2;
}
[[ -f "$archive" && -s "$archive" && ! -L "$archive" &&
   -f "$archive.sha256" && ! -L "$archive.sha256" ]] || {
  echo "ERROR=ARCHIVE_OR_CHECKSUM_MISSING" >&2; exit 2;
}
for item in "$archive" "$archive.sha256"; do
  [[ "$(stat -c '%a' "$item")" == 600 &&
     "$(stat -c '%u' "$item")" == "$(id -u)" &&
     "$(stat -c '%h' "$item")" == 1 ]] || {
    echo "ERROR=ARCHIVE_PERMISSIONS_UNEXPECTED" >&2; exit 2;
  }
done
# Accept only an exact single checksum line for the nominated archive.
line="$(cat -- "$archive.sha256")"
actual="$(sha256sum -- "$archive" | awk '{print $1}')"
[[ "$line" == "$actual  $name" ]] || {
  echo "ERROR=ARCHIVE_SHA256_MISMATCH" >&2; exit 2;
}
docker image inspect postgres:17-alpine >/dev/null 2>&1 || {
  echo "ERROR=LOCAL_POSTGRES17_IMAGE_NOT_FOUND" >&2; exit 2;
}

cid=""
cleanup() {
  [[ -n "$cid" ]] || return 0
  if docker inspect "$cid" >/dev/null 2>&1; then
    label="$(docker inspect -f '{{index .Config.Labels "com.foliosentry.operation"}}' "$cid" 2>/dev/null || :)"
    if [[ "$label" == "isolated-restore-check" ]]; then
      docker stop -t 5 "$cid" >/dev/null 2>&1 ||
        echo "WARNING=ISOLATED_RESTORE_CONTAINER_CLEANUP_FAILED" >&2
    fi
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "FOLIOSENTRY_RESTORE_SOURCE=CHECKSUM_VERIFIED"
echo "FOLIOSENTRY_RESTORE_MODE=ISOLATED_EPHEMERAL_NO_NETWORK"
cid="$(docker run -d --rm --pull never \
  --network none \
  --label com.foliosentry.operation=isolated-restore-check \
  --memory 768m --pids-limit 160 \
  --tmpfs /var/lib/postgresql/data:rw,nosuid,nodev,size=536870912 \
  -e POSTGRES_USER=folio_restore_test \
  -e POSTGRES_DB=folio_restore_test \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  --health-cmd 'pg_isready -U folio_restore_test -d folio_restore_test' \
  --health-interval 2s --health-timeout 2s --health-retries 25 \
  postgres:17-alpine)" || {
    echo "ERROR=EPHEMERAL_POSTGRES_START_FAILED" >&2; exit 1;
  }
[[ "$(docker inspect -f '{{.HostConfig.NetworkMode}}' "$cid")" == none ]] || {
  echo "ERROR=RESTORE_CONTAINER_NOT_NETWORK_ISOLATED" >&2; exit 1;
}
[[ "$(docker inspect -f '{{index .Config.Labels "com.foliosentry.operation"}}' "$cid")" == "isolated-restore-check" ]] || {
  echo "ERROR=RESTORE_CONTAINER_LABEL_MISMATCH" >&2; exit 1;
}
[[ "$(docker inspect -f '{{len .HostConfig.PortBindings}}' "$cid")" == 0 ]] || {
  echo "ERROR=RESTORE_CONTAINER_HOST_PORT_PRESENT" >&2; exit 1;
}
[[ -n "$(docker inspect -f '{{index .HostConfig.Tmpfs "/var/lib/postgresql/data"}}' "$cid" 2>/dev/null)" ]] || {
  echo "ERROR=RESTORE_TMPFS_NOT_CONFIGURED" >&2; exit 1;
}
# Docker image VOLUME must not silently create a persistent DB volume.
mounts="$(docker inspect -f '{{range .Mounts}}{{if ne .Type "tmpfs"}}UNSAFE{{end}}{{end}}' "$cid")"
[[ -z "$mounts" ]] || {
  echo "ERROR=RESTORE_CONTAINER_HAS_PERSISTENT_MOUNTS" >&2; exit 1;
}
health=""
for _ in $(seq 1 35); do
  health="$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || :)"
  [[ "$health" == healthy ]] && break
  [[ "$health" == unhealthy ]] && break
  sleep 2
done
[[ "$health" == healthy ]] || {
  echo "ERROR=ISOLATED_RESTORE_DB_NOT_HEALTHY" >&2; exit 1;
}

# Archive bytes go directly to the transient container; never print table data.
docker exec -i "$cid" pg_restore \
  -U folio_restore_test -d folio_restore_test \
  --no-owner --no-acl --single-transaction --exit-on-error < "$archive" ||
  { echo "ERROR=PG_RESTORE_FAILED" >&2; exit 1; }
state="$(docker exec -i "$cid" psql -X -w -q -At -v ON_ERROR_STOP=1 \
  -U folio_restore_test -d folio_restore_test <<'SQL'
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10s';
SELECT CASE
 WHEN to_regclass('public.alembic_version') IS NOT NULL
  AND to_regclass('public.auth_owner') IS NOT NULL
  AND to_regclass('public.auth_session') IS NOT NULL
  AND (SELECT count(*) FROM public.alembic_version) = 1
  AND (SELECT max(version_num) FROM public.alembic_version) = '20261119_auth01'
  AND (SELECT count(*) FROM public.auth_owner) = 1
  AND (SELECT count(*) FROM public.auth_owner WHERE id = 1 AND length(password_hash) > 0) = 1
 THEN 'RESTORE_SCHEMA_AND_OWNER_PASS' ELSE 'RESTORE_CONTENT_INVALID' END;
ROLLBACK;
SQL
)" || { echo "ERROR=RESTORED_DATABASE_QUERY_FAILED" >&2; exit 1; }
[[ "$state" == "RESTORE_SCHEMA_AND_OWNER_PASS" ]] || {
  echo "ERROR=RESTORED_DATABASE_CONTENT_INVALID" >&2; exit 1;
}
echo "FOLIOSENTRY_RESTORE_SCHEMA_AND_OWNER_PASS"
echo "PRODUCTION_DB_READ_ONLY=YES"
echo "PRODUCTION_CONTAINERS_MODIFIED=NO"
echo "EPHEMERAL_POSTGRES_CLEANUP=ON_EXIT"
echo "FOLIOSENTRY_ISOLATED_RESTORE_TEST_PASS"
