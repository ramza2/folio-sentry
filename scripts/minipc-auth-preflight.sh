#!/usr/bin/env bash
# FolioSentry MiniPC AUTH preflight (READ ONLY). No installs, container changes,
# database access, secrets, network configuration, or writes.
# Usage: bash scripts/minipc-auth-preflight.sh [repo_dir]
set -uo pipefail

ROOT="${1:-$PWD}"
FLAGS=0
say()  { printf '%s=%s\n' "$1" "$2"; }
flag() { say "REVIEW_$1" "$2"; FLAGS=$((FLAGS + 1)); }
has()  { command -v "$1" >/dev/null 2>&1; }
section() { printf '\n===== %s =====\n' "$1"; }

if [[ $# -gt 1 || ${1:-} == "--help" ]]; then
  echo 'Usage: bash scripts/minipc-auth-preflight.sh [repo_dir]'
  exit 0
fi

section "FOLIOSENTRY_MINIPC_AUTH_PREFLIGHT_V1"
say "MODE" "READ_ONLY"
say "UTC" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
say "OS_KERNEL" "$(uname -sr)"
say "ARCH" "$(uname -m)"
if [[ -r /etc/os-release ]]; then
  say "OS" "$(sed -n 's/^PRETTY_NAME=//p' /etc/os-release | head -n1 | tr -d '"')"
fi

section "REPOSITORY"
if ! has git; then
  flag "GIT" "NOT_INSTALLED"
elif ! REPO=$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null); then
  flag "REPO" "NOT_FOUND"
else
  say "REPO_DIR" "$REPO"
  say "BRANCH" "$(git -C "$REPO" branch --show-current 2>/dev/null || echo UNKNOWN)"
  say "HEAD" "$(git -C "$REPO" rev-parse --short=12 HEAD 2>/dev/null || echo UNKNOWN)"
  if git -C "$REPO" diff --quiet --no-ext-diff && git -C "$REPO" diff --cached --quiet --no-ext-diff; then
    say "TRACKED_CHANGES" "NONE"
  else
    flag "WORKTREE" "TRACKED_CHANGES"
  fi
  # Print only expected remote classification, never unknown URL/credentials.
  REMOTE=$(git -C "$REPO" remote get-url origin 2>/dev/null || :)
  case "$REMOTE" in
    git@github.com:ramza2/folio-sentry.git) say "GIT_ORIGIN" "EXPECTED_SSH" ;;
    https://github.com/ramza2/folio-sentry.git) say "GIT_ORIGIN" "EXPECTED_HTTPS" ;;
    *) flag "GIT_ORIGIN" "UNEXPECTED" ;;
  esac
fi

section "RESOURCES"
if has nproc; then say "LOGICAL_CPUS" "$(nproc)"; else flag "CPU" "UNKNOWN"; fi
if has free; then
  free -h | awk '/^Mem:/ {print "RAM_TOTAL=" $2 "\nRAM_AVAILABLE=" $7} /^Swap:/ {print "SWAP_TOTAL=" $2}'
else flag "MEMORY" "UNKNOWN"; fi
if has df; then
  df -hP "$ROOT" 2>/dev/null | awk 'NR==2 {print "REPO_DISK_SIZE=" $2 "\nREPO_DISK_FREE=" $4 "\nREPO_DISK_USE=" $5}' || :
else flag "DISK" "UNKNOWN"; fi

section "DOCKER_READONLY"
if ! has docker; then
  flag "DOCKER" "CLI_MISSING"
else
  say "DOCKER_CLI" "$(docker --version 2>/dev/null || echo UNKNOWN)"
  if docker compose version >/dev/null 2>&1; then
    say "COMPOSE_VERSION" "$(docker compose version --short 2>/dev/null || echo INSTALLED)"
  else
    flag "COMPOSE" "UNAVAILABLE"
  fi
  if docker info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
    say "DOCKER_DAEMON" "ACCESSIBLE"
    # Inspect project names only. Never print unrelated home-service names.
    PROJECTS=$(docker ps -a --format '{{.Label "com.docker.compose.project"}}' 2>/dev/null || :)
    if grep -Fxq "folio-sentry" <<< "$PROJECTS"; then
      flag "FOLIO_PROJECT" "EXISTING_CONTAINERS"
    else say "FOLIO_PROJECT" "NONE_SEEN"; fi
    if grep -Fxq "foliosentry-auth-preview" <<< "$PROJECTS"; then
      flag "PREVIEW_PROJECT" "EXISTING_CONTAINERS"
    else say "PREVIEW_PROJECT" "NONE_SEEN"; fi
    VOLUMES=$(docker volume ls --format '{{.Name}}' 2>/dev/null || :)
    if grep -Eq '(^|_)folio.?sentry([_-]|$)' <<< "$VOLUMES"; then
      flag "FOLIO_VOLUME" "EXISTING_VOLUME"
    else say "FOLIO_VOLUME" "NONE_SEEN"; fi
  else
    flag "DOCKER" "DAEMON_UNAVAILABLE_OR_PERMISSION_DENIED"
  fi
fi

section "LOOPBACK_PORT_CANDIDATES"
if ! has ss; then flag "SOCKET_SCAN" "SS_MISSING"
elif ! SOCKETS=$(ss -H -ltn 2>/dev/null); then flag "SOCKET_SCAN" "UNAVAILABLE"
else
  for PORT in 18901 18902; do
    if awk -v port="$PORT" '$4 ~ (":" port "$") {seen=1} END {exit seen ? 0 : 1}' <<< "$SOCKETS"; then
      flag "PORT_$PORT" "IN_USE"
    else
      say "PORT_$PORT" "NO_LISTENER_SEEN"
    fi
  done
fi

section "REVIEW_GATE"
say "REVIEW_FLAGS" "$FLAGS"
say "CONTAINERS_MODIFIED" "NO"
say "DATABASE_MODIFIED" "NO"
say "PORTS_CHANGED" "NO"
say "CREDENTIALS_REQUESTED" "NO"
say "NEXT_STEP" "REVIEW_OUTPUT_AND_CONFIRM_BEFORE_PREVIEW"
echo "FOLIOSENTRY_MINIPC_PREFLIGHT_READONLY_COMPLETE"
