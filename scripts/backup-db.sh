#!/usr/bin/env bash
# Approved, limited mutation: write ONE private PostgreSQL backup archive.
# Never restarts Docker, changes Postgres data, reads login passwords, or writes
# inside the repository. A complete archive is required before HTTPS publication.
set -Eeuo pipefail
umask 077

[[ "$#" -eq 1 ]] || {
  echo "Usage: bash scripts/backup-db.sh --confirm-prepublish-backup|--confirm-daily-backup" >&2
  exit 2
}
case "$1" in
  --confirm-prepublish-backup) kind=prepublish ;;
  --confirm-daily-backup) kind=daily ;;
  *) echo "ERROR=EXPLICIT_BACKUP_CONFIRMATION_REQUIRED" >&2; exit 2 ;;
esac

command -v docker >/dev/null || { echo "ERROR=DOCKER_MISSING" >&2; exit 1; }
command -v sha256sum >/dev/null || { echo "ERROR=SHA256SUM_MISSING" >&2; exit 1; }

mapfile -t db_ids < <(docker ps -q \
  --filter 'label=com.docker.compose.project=foliosentry-prod' \
  --filter 'label=com.docker.compose.service=db')

[[ "${#db_ids[@]}" -eq 1 ]] || {
  echo "ERROR=EXPECTED_ONE_RUNNING_FOLIOSENTRY_DB" >&2; exit 1;
}
cid="${db_ids[0]}"
[[ "$(docker inspect -f '{{.State.Health.Status}}' "$cid")" == "healthy" ]] || {
  echo "ERROR=DB_NOT_HEALTHY" >&2; exit 1;
}

state="$(docker exec -i "$cid" \
  psql -X -w -q -At -v ON_ERROR_STOP=1 -U folio -d folio <<'SQL'
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
SELECT CASE WHEN
  (SELECT COUNT(*) FROM public.auth_owner) = 1
  AND (SELECT COUNT(*) FROM public.auth_session) >= 0
  AND (SELECT COUNT(*) FROM public.alembic_version) = 1
  AND EXISTS (
    SELECT 1 FROM public.alembic_version v
    WHERE v.version_num IN (
      '20261119_auth01', '20261119_portfolio01',
      '20261120_pricebar01', '20261123_quality01', '20261123_quality02'
    )
    AND (v.version_num = '20261119_auth01' OR (
      to_regclass('public.instrument') IS NOT NULL
      AND to_regclass('public.tracked_instrument') IS NOT NULL
    ))
    AND (v.version_num NOT IN ('20261120_pricebar01', '20261123_quality01', '20261123_quality02')
      OR to_regclass('public.price_bar') IS NOT NULL)
    AND (v.version_num NOT IN ('20261123_quality01', '20261123_quality02')
      OR to_regclass('public.price_quality_evidence') IS NOT NULL)
    AND (v.version_num <> '20261123_quality02'
      OR to_regclass('public.evidence_reference_revision') IS NOT NULL)
  )
  THEN 'OWNER_SCHEMA_READY'
  ELSE 'BLOCKED'
END;
ROLLBACK;
SQL
)" || { echo "ERROR=SCHEMA_CHECK_FAILED" >&2; exit 1; }
[[ "$state" == "OWNER_SCHEMA_READY" ]] || {
  echo "ERROR=OWNER_SCHEMA_NOT_READY" >&2; exit 1;
}

backup_dir="$HOME/.local/share/folio-sentry/backups"
[[ ! -L "$backup_dir" ]] || { echo "ERROR=BACKUP_DIR_SYMLINK" >&2; exit 1; }
mkdir -p -m 700 -- "$backup_dir"
[[ -d "$backup_dir" && ! -L "$backup_dir" &&
   "$(stat -c '%u' "$backup_dir")" == "$(id -u)" &&
   "$(stat -c '%a' "$backup_dir")" == "700" ]] || {
  echo "ERROR=BACKUP_DIR_NOT_PRIVATE" >&2; exit 1;
}
free_mib="$(df -Pm "$backup_dir" | awk 'NR==2 {print $4}')"
[[ "$free_mib" =~ ^[0-9]+$ && "$free_mib" -ge 256 ]] || {
  echo "ERROR=BACKUP_DISK_FREE_LT_256_MIB" >&2; exit 1;
}

tmp="$(mktemp "$backup_dir/${kind}-$(date -u +%Y%m%dT%H%M%SZ).XXXXXXXX")"
cleanup() { [[ ! -f "$tmp" ]] || rm -f -- "$tmp"; }
trap cleanup EXIT

echo "FOLIOSENTRY_${kind^^}_BACKUP_STARTED"
# pg_dump is read-only on the isolated FolioSentry DB; the archive may contain
# authentication hashes, so the local private file must NEVER be shared.
docker exec -i "$cid" pg_dump \
  --username=folio --dbname=folio --format=custom --no-owner --no-acl > "$tmp"

[[ -s "$tmp" ]] || { echo "ERROR=EMPTY_BACKUP" >&2; exit 1; }
toc="$(docker exec -i "$cid" pg_restore --list < "$tmp")" || {
  echo "ERROR=ARCHIVE_TOC_INVALID" >&2; exit 1;
}
grep -Eq 'TABLE DATA[[:space:]]+public[[:space:]]+auth_owner[[:space:]]' <<< "$toc" || {
  echo "ERROR=OWNER_TABLE_NOT_IN_ARCHIVE" >&2; exit 1;
}
grep -Eq 'TABLE DATA[[:space:]]+public[[:space:]]+auth_session[[:space:]]' <<< "$toc" || {
  echo "ERROR=SESSION_TABLE_NOT_IN_ARCHIVE" >&2; exit 1;
}
# Read every archive section without connecting to a destination database.
docker exec -i "$cid" pg_restore --file=/dev/null < "$tmp" || {
  echo "ERROR=BACKUP_ARCHIVE_STREAM_INVALID" >&2; exit 1;
}

backup="${tmp}.pgdump"
[[ ! -e "$backup" && ! -L "$backup" ]] || {
  echo "ERROR=BACKUP_NAME_COLLISION" >&2; exit 1;
}
mv -- "$tmp" "$backup"
chmod 600 "$backup"
name="$(basename "$backup")"
checksum="$(sha256sum "$backup" | awk '{print $1}')"
printf '%s  %s\n' "$checksum" "$name" > "$backup.sha256"
chmod 600 "$backup.sha256"
( cd "$backup_dir" && sha256sum -c -- "$name.sha256" >/dev/null ) || {
  echo "ERROR=BACKUP_CHECKSUM_INVALID" >&2; exit 1;
}

echo "FOLIOSENTRY_${kind^^}_BACKUP_VERIFY_PASS"
echo "BACKUP_PRIVATE_DIRECTORY=$backup_dir"
echo "BACKUP_FILE_NAME=$name"
echo "BACKUP_SHA256_CHECK=PASS"
echo "ARCHIVE_READABILITY=PASS_NOT_RESTORE_TRIAL"
echo "DB_DATA_CHANGED=NO"
echo "PUBLICATION=NOT_PERFORMED_BY_BACKUP"
