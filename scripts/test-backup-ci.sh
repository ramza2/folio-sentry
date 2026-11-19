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

# Daily backup uses the same validated archive mechanism, without touching prepublish.
HOME="$scratch" bash scripts/run-daily-backup.sh --confirm-daily-backup
dailies=("$scratch"/.local/share/folio-sentry/backups/daily-*.pgdump)
[[ "${#dailies[@]}" -eq 1 ]] || { echo "ERROR=CI_DAILY_ARCHIVE_COUNT" >&2; exit 1; }
HOME="$scratch" bash scripts/verify-backup-restore.sh \
  --confirm-isolated-restore "${dailies[0]}"

# A verified synthetic daily copy over 14 days old must be pruned; the
# original immutable prepublish archive must remain untouched.
old="$scratch/.local/share/folio-sentry/backups/daily-20260101T000000Z.TESTOLD1.pgdump"
cp -- "${dailies[0]}" "$old"
old_hash="$(sha256sum "$old" | awk '{print $1}')"
printf '%s  %s\n' "$old_hash" "$(basename "$old")" > "$old.sha256"
chmod 600 "$old" "$old.sha256"
touch -d "20 days ago" "$old" "$old.sha256"
HOME="$scratch" bash scripts/run-daily-backup.sh --confirm-daily-backup
[[ ! -e "$old" && ! -e "$old.sha256" ]] || {
  echo "ERROR=CI_OLD_DAILY_BACKUP_NOT_PRUNED" >&2; exit 1;
}
[[ -s "${archives[0]}" && -f "${archives[0]}.sha256" ]] || {
  echo "ERROR=CI_PREPUBLISH_BACKUP_CHANGED" >&2; exit 1;
}
echo "FOLIOSENTRY_OPS01_DAILY_RETENTION_E2E_PASS"
