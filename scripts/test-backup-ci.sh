#!/usr/bin/env bash
# GitHub Actions only: synthetic disposable PostgreSQL for backup end-to-end.
# NEVER run this on a real MiniPC: it uses Docker project labels for isolation.
set -Eeuo pipefail
umask 077
[[ "${CI:-}" == "true" && "${GITHUB_ACTIONS:-}" == "true" ]] || {
  echo "ERROR=GITHUB_ACTIONS_ONLY" >&2; exit 2;
}

name="foliosentry-backup-ci-${GITHUB_RUN_ID:?}"
cid=""
cleanup() {
  if [[ -n "$cid" ]]; then docker rm -f "$cid" >/dev/null 2>&1 || :; fi
}
trap cleanup EXIT

cid="$(docker run -d --rm \
  --name "$name" \
  --label com.docker.compose.project=foliosentry-prod \
  --label com.docker.compose.service=db \
  -e POSTGRES_DB=folio -e POSTGRES_USER=folio \
  -e POSTGRES_PASSWORD=ci-synthetic-only-secret \
  --health-cmd 'pg_isready -U folio -d folio' \
  --health-interval=1s --health-timeout=2s --health-retries=30 \
  postgres:17-alpine)"
health=""
for _ in $(seq 1 40); do
  health="$(docker inspect -f '{{.State.Health.Status}}' "$cid")"
  [[ "$health" == "healthy" ]] && break
  sleep 1
done
[[ "$health" == "healthy" ]] || { echo "ERROR=CI_DB_NOT_HEALTHY" >&2; exit 1; }

docker exec -i "$cid" psql -X -w -q -v ON_ERROR_STOP=1 -U folio -d folio <<'SQL'
CREATE TABLE public.alembic_version (version_num varchar(32) NOT NULL);
INSERT INTO public.alembic_version VALUES ('20261119_auth01');
CREATE TABLE public.auth_owner (
  id integer PRIMARY KEY,
  username varchar(64) NOT NULL,
  password_hash text NOT NULL,
  failed_attempts integer NOT NULL DEFAULT 0
);
INSERT INTO public.auth_owner (id, username, password_hash)
  VALUES (1, 'ci-owner', 'synthetic-ci-only-not-a-real-hash');
CREATE TABLE public.auth_session (
  id_hash varchar(64) PRIMARY KEY,
  owner_id integer NOT NULL,
  csrf_token varchar(64) NOT NULL
);
SQL

scratch="$(mktemp -d)"
chmod 700 "$scratch"
HOME="$scratch" bash scripts/backup-db.sh --confirm-prepublish-backup

shopt -s nullglob
archives=("$scratch"/.local/share/folio-sentry/backups/*.pgdump)
[[ "${#archives[@]}" -eq 1 ]] || { echo "ERROR=CI_BACKUP_ARCHIVE_COUNT" >&2; exit 1; }
[[ -f "${archives[0]}.sha256" ]] || {
  echo "ERROR=CI_BACKUP_SHA256_MISSING" >&2; exit 1;
}
( cd "$(dirname "${archives[0]}")" &&
  sha256sum -c "$(basename "${archives[0]}").sha256" >/dev/null )

# Restore the exact synthetic archive into a no-network, tmpfs-only container.
HOME="$scratch" bash scripts/verify-backup-restore.sh \
  --confirm-isolated-restore "${archives[0]}"

echo "FOLIOSENTRY_DEPLOY02_SYNTHETIC_BACKUP_E2E_PASS"
echo "FOLIOSENTRY_OPS01_SYNTHETIC_ISOLATED_RESTORE_PASS"
