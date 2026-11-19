#!/usr/bin/env bash
# Explicit daily FolioSentry database backup; trims ONLY verified old daily
# archive/checksum pairs. Never deletes prepublish, manual or unknown files.
set -Eeuo pipefail
umask 077

[[ "$#" -eq 1 && "$1" == "--confirm-daily-backup" ]] || {
  echo "USAGE=bash scripts/run-daily-backup.sh --confirm-daily-backup" >&2
  exit 2
}
command -v flock >/dev/null || { echo "ERROR=FLOCK_MISSING" >&2; exit 2; }
root="$(cd "$(dirname "$0")/.." && pwd)"
dir="$HOME/.local/share/folio-sentry/backups"
[[ ! -L "$dir" ]] || { echo "ERROR=BACKUP_DIRECTORY_IS_SYMLINK" >&2; exit 2; }
mkdir -p -m 700 -- "$dir"
[[ -d "$dir" && ! -L "$dir" &&
   "$(stat -c '%a' "$dir")" == 700 &&
   "$(stat -c '%u' "$dir")" == "$(id -u)" ]] || {
  echo "ERROR=BACKUP_DIRECTORY_NOT_PRIVATE" >&2; exit 2;
}
exec 9>"$dir/.daily-backup.lock"
chmod 600 "$dir/.daily-backup.lock"
flock -n 9 || {
  echo "ERROR=DAILY_BACKUP_ALREADY_RUNNING" >&2; exit 1;
}

# Retention is attempted ONLY after a new, validated archive is written.
bash "$root/scripts/backup-db.sh" --confirm-daily-backup
echo "FOLIOSENTRY_DAILY_BACKUP_NEW_ARCHIVE=VERIFIED"

removed=0
skipped=0
# Retain 14 days (files older than >=14*24 hours); never remove the
# original prepublish or user-created backups.
while IFS= read -r -d '' archive; do
  name="$(basename -- "$archive")"
  [[ "$name" =~ ^daily-[0-9]{8}T[0-9]{6}Z\.[A-Za-z0-9]{8}\.pgdump$ ]] || {
    skipped=$((skipped + 1)); continue;
  }
  checksum="$archive.sha256"
  [[ -f "$checksum" && ! -L "$checksum" &&
     -f "$archive" && ! -L "$archive" ]] || {
    skipped=$((skipped + 1)); continue;
  }
  safe=1
  for item in "$archive" "$checksum"; do
    if [[ "$(stat -c '%a' "$item")" != 600 ||
          "$(stat -c '%u' "$item")" != "$(id -u)" ||
          "$(stat -c '%h' "$item")" != 1 ]]; then
      safe=0
    fi
  done
  if (( safe == 0 )); then
    skipped=$((skipped + 1)); continue;
  fi
  actual="$(sha256sum -- "$archive" | awk '{print $1}')"
  saved="$(cat -- "$checksum")"
  [[ "$saved" == "$actual  $name" ]] || {
    skipped=$((skipped + 1)); continue;
  }
  rm -- "$archive" "$checksum"
  removed=$((removed + 1))
done < <(find "$dir" -maxdepth 1 -type f -name 'daily-*.pgdump' -mtime +13 -print0)

echo "FOLIOSENTRY_DAILY_RETENTION_DAYS=14"
echo "FOLIOSENTRY_DAILY_RETENTION_PAIRS_REMOVED=$removed"
echo "FOLIOSENTRY_DAILY_RETENTION_PAIRS_SKIPPED=$skipped"
echo "PREPUBLISH_BACKUPS_PRESERVED=YES"
echo "DATABASE_MUTATIONS=NO"
echo "FOLIOSENTRY_DAILY_BACKUP_AND_RETENTION_PASS"
