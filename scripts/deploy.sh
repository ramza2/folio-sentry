#!/usr/bin/env bash
# FolioSentry deployment helper. No changes happen with inspect/check/status.
# Production deployment commands are separately gated; never run unapproved.
set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env.deploy"
PROJECT="foliosentry-prod"
BASE=(docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$ROOT/compose.production.yml")
EDGE=(docker compose --project-name "$PROJECT" --env-file "$ENV_FILE" -f "$ROOT/compose.production.yml" -f "$ROOT/compose.traefik.yml")

say() { printf '%s\n' "$*"; }
fatal() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
usage() {
  cat <<'EOF'
FolioSentry MiniPC deployment assistant (private single-owner service)

  bash scripts/deploy.sh inspect       # Show safe Traefik/PickNext routing hints
  bash scripts/deploy.sh inspect-acme  # Read-only ACME resolver/port mapping hints
  bash scripts/deploy.sh configure     # Interactive domain/network/certificate setup
  bash scripts/deploy.sh check         # Read-only DNS, Docker, and Compose preflight
  bash scripts/deploy.sh status        # Only inspect FolioSentry project's containers
  bash scripts/deploy.sh db-init --confirm-new-private-db
                                       # CREATE separate DB/migrate/interactive owner
  bash scripts/deploy.sh publish --confirm-public-https
                                       # Verified backup, backend, HTTPS frontend, automatic safe rollback
  bash scripts/deploy.sh unpublish --confirm-stop-frontend-only
                                       # Emergency stop of ONLY FolioSentry frontend
No down/prune or database deletion command is provided. Existing services are never targeted.
Deployment requires an explicit user approval and reviewed, synced main.
EOF
}
valid_domain() {
  [[ "$1" =~ ^[a-z0-9]([a-z0-9.-]{1,240}[a-z0-9])?\.duckdns\.org$ ]] &&
  [[ "$1" != *".."* ]]
}
valid_id() { [[ "$1" =~ ^[A-Za-z][A-Za-z0-9_-]{0,62}$ ]]; }
valid_network() { [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$ ]]; }
need_deps() {
  command -v docker >/dev/null || fatal "Docker CLI not installed"
  docker compose version >/dev/null 2>&1 || fatal "Docker Compose not available"
}
read_settings() {
  [[ -f "$ENV_FILE" && ! -L "$ENV_FILE" ]] || fatal "Run 'configure' first"
  local mode
  mode=$(stat -c %a "$ENV_FILE")
  [[ "$mode" == "600" ]] || fatal ".env.deploy must have mode 600"
  FOLIOSENTRY_DOMAIN=""
  FOLIOSENTRY_TRAEFIK_NETWORK=""
  FOLIOSENTRY_TRAEFIK_ENTRYPOINT=""
  FOLIOSENTRY_TRAEFIK_CERTRESOLVER=""
  FOLIOSENTRY_DB_SECRET_FILE=""
  local key value
  while IFS='=' read -r key value || [[ -n "$key" ]]; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    case "$key" in
      FOLIOSENTRY_DOMAIN|FOLIOSENTRY_TRAEFIK_NETWORK|FOLIOSENTRY_TRAEFIK_ENTRYPOINT|FOLIOSENTRY_TRAEFIK_CERTRESOLVER|FOLIOSENTRY_DB_SECRET_FILE)
        printf -v "$key" '%s' "$value" ;;
      *) fatal "Unexpected deployment config variable ($key)" ;;
    esac
  done < "$ENV_FILE"
  valid_domain "$FOLIOSENTRY_DOMAIN" || fatal "Invalid DuckDNS FQDN"
  valid_network "$FOLIOSENTRY_TRAEFIK_NETWORK" || fatal "Invalid Traefik network name"
  valid_id "$FOLIOSENTRY_TRAEFIK_ENTRYPOINT" || fatal "Invalid Traefik entrypoint"
  valid_id "$FOLIOSENTRY_TRAEFIK_CERTRESOLVER" || fatal "Invalid TLS certresolver"
  [[ "$FOLIOSENTRY_DB_SECRET_FILE" == /* && "$FOLIOSENTRY_DB_SECRET_FILE" != *$'\n'* ]] ||
    fatal "Invalid absolute DB secret path"
  [[ -f "$FOLIOSENTRY_DB_SECRET_FILE" && ! -L "$FOLIOSENTRY_DB_SECRET_FILE" ]] ||
    fatal "DB secret file missing or symbolic link"
  [[ "$(stat -c %a "$FOLIOSENTRY_DB_SECRET_FILE")" == "600" ]] ||
    fatal "DB secret permission must be 600"
  [[ -s "$FOLIOSENTRY_DB_SECRET_FILE" ]] || fatal "DB secret is empty"
  export FOLIOSENTRY_DOMAIN FOLIOSENTRY_TRAEFIK_NETWORK
  export FOLIOSENTRY_TRAEFIK_ENTRYPOINT FOLIOSENTRY_TRAEFIK_CERTRESOLVER FOLIOSENTRY_DB_SECRET_FILE
}

configure() {
  [[ -t 0 ]] || fatal "configure needs interactive terminal"
  [[ ! -e "$ENV_FILE" && ! -L "$ENV_FILE" ]] || fatal "Configuration already exists. Review/edit .env.deploy privately (mode 600)"
  command -v openssl >/dev/null || fatal "openssl is needed to create a random DB secret"
  local domain network entrypoint resolver secret_dir secret_file
  say "Existing PickNext Traefik configuration is NOT changed."
  say "Verified on MiniPC 2026-11-19: proxy / websecure / myresolver."
  say "Press Enter to accept each observed default, or enter a changed value."
  say "HTTPS hostname is still a candidate until DNS/TLS verification succeeds."
  read -r -p "FolioSentry DuckDNS FQDN (e.g. foliosentry.ramza.duckdns.org): " domain
  domain="${domain,,}"
  valid_domain "$domain" || fatal "Domain invalid: enter a DuckDNS hostname, not URL"
  read -r -p "Existing Traefik Docker network [proxy]: " network
  network="${network:-proxy}"
  valid_network "$network" || fatal "Network name invalid"
  read -r -p "Existing HTTPS entrypoint [websecure]: " entrypoint
  entrypoint="${entrypoint:-websecure}"
  valid_id "$entrypoint" || fatal "Entry point invalid"
  read -r -p "Existing TLS certificate resolver [myresolver]: " resolver
  resolver="${resolver:-myresolver}"
  valid_id "$resolver" || fatal "Certificate resolver invalid"
  secret_dir="$HOME/.config/folio-sentry"
  secret_file="$secret_dir/pg_password"
  mkdir -p -m 700 "$secret_dir"
  chmod 700 "$secret_dir"
  [[ ! -e "$secret_file" && ! -L "$secret_file" ]] || fatal "DB secret already exists: refuse to overwrite"
  ( umask 077; openssl rand -hex 32 > "$secret_file"; chmod 600 "$secret_file" )
  {
    printf 'FOLIOSENTRY_DOMAIN=%s\n' "$domain"
    printf 'FOLIOSENTRY_TRAEFIK_NETWORK=%s\n' "$network"
    printf 'FOLIOSENTRY_TRAEFIK_ENTRYPOINT=%s\n' "$entrypoint"
    printf 'FOLIOSENTRY_TRAEFIK_CERTRESOLVER=%s\n' "$resolver"
    printf 'FOLIOSENTRY_DB_SECRET_FILE=%s\n' "$secret_file"
  } > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  say "DEPLOY_CONFIG_CREATED_PRIVATE"
  say "Domain=$domain"
  say "Traefik network=$network"
  say "No DB secret or login password has been printed."
  say "Next: bash scripts/deploy.sh check"
}
check() {
  need_deps
  command -v python3 >/dev/null || fatal "Python3 is required for config safety checks"
  read_settings
  [[ -d "$ROOT/.git" ]] || fatal "Not a Git working tree"
  docker info >/dev/null 2>&1 || fatal "Docker daemon inaccessible"
  docker network inspect "$FOLIOSENTRY_TRAEFIK_NETWORK" >/dev/null 2>&1 ||
    fatal "Existing Traefik network not found (never create/rename it)"
  say "TRAEFIK_EXISTING_NETWORK=PASS"
  # Check existing Docker routing rules without printing other app labels.
  python3 - "$FOLIOSENTRY_DOMAIN" <<'PY'
import json, subprocess, sys
domain = sys.argv[1].lower()
ids = subprocess.run(
    ["docker", "ps", "--format", "{{.ID}}"],
    check=True, capture_output=True, text=True,
).stdout.splitlines()
for cid in ids:
    obj = json.loads(subprocess.run(
        ["docker", "inspect", cid], check=True, capture_output=True, text=True,
    ).stdout)[0]
    labels = obj.get("Config", {}).get("Labels") or {}
    for key, value in labels.items():
        if key.startswith("traefik.http.routers.") and key.endswith(".rule"):
            if isinstance(value, str) and "Host(" in value and domain in value.lower():
                raise SystemExit("ERROR: Traefik hostname is already used by a running router")
print("TRAEFIK_EXISTING_HOST_ROUTE=NO_COLLISION_SEEN")
PY
  # Observed MiniPC resolver: TLS-ALPN-01 with host 443 published.
  # This is preflight metadata only; external forwarding/certificate issuance
  # cannot be proven before the approved router is brought online.
  local acme_summary
  acme_summary=$(python3 "$ROOT/scripts/inspect-traefik-acme.py") ||
    fatal "Existing Traefik ACME metadata is unavailable"
  printf '%s\n' "$acme_summary"
  grep -Fqx "TRAEFIK_ACME_CHALLENGE=TLS_ALPN_01" <<< "$acme_summary" ||
    fatal "Expected myresolver TLS-ALPN-01 setting not confirmed"
  grep -Fqx "DOCKER_HOST_PORT_443=PUBLISHED_BY_DOCKER_NOT_EXTERNAL_VERIFIED" <<< "$acme_summary" ||
    fatal "Traefik Docker 443 binding not confirmed"
  grep -Fqx "ACME_STORAGE_MOUNT=MOUNT_PRESENT_NOT_BACKUP_VERIFIED" <<< "$acme_summary" ||
    fatal "Persistent ACME certificate storage mount not confirmed"
  say "TRAEFIK_ACME_PREFLIGHT=PASS_NOT_EXTERNAL_REACHABILITY"
  # A syntactically resolvable domain may still point to the wrong WAN IP.
  # Compare the candidate against the already-working PickNext DNS mapping.
  local dns_summary
  dns_summary=$(bash "$ROOT/scripts/check-duckdns-route.sh" "$FOLIOSENTRY_DOMAIN") ||
    fatal "DuckDNS candidate must match existing PickNext IPv4 mapping"
  printf '%s\n' "$dns_summary"
  grep -Fqx "FOLIOSENTRY_DUCKDNS_READONLY_CHECK_PASS" <<< "$dns_summary" ||
    fatal "DuckDNS comparison did not confirm the candidate mapping"
  say "DUCKDNS_DNS_MAPPING=PASS_NOT_CERTIFICATE_VALIDATION"

  "${EDGE[@]}" config -q || fatal "Production + Traefik Compose config invalid"
  # Verify that the API and DB have no host-exposed ports; only frontend
  # joins the pre-existing Traefik network. Never print the compose config.
  "${EDGE[@]}" config --format json | python3 -c '
import json, sys
o=json.load(sys.stdin)
sv=o["services"]
for name in ("db","backend","frontend"):
    if sv[name].get("ports"):
        raise SystemExit("Host-published port forbidden for " + name)
for name in ("db","backend"):
    if str(sv[name].get("labels",{}).get("traefik.enable","false")).lower() != "false":
        raise SystemExit("Private service accidentally exposed: " + name)
labels=sv["frontend"].get("labels",{})
if str(labels.get("traefik.enable")).lower() != "true":
    raise SystemExit("Frontend HTTPS routing is disabled unexpectedly")
if str(labels.get("traefik.http.routers.foliosentry-prod.tls")).lower() != "true":
    raise SystemExit("HTTPS must be enabled")
print("PRIVATE_API_DB_AND_HTTPS_ROUTER_CONTRACT_PASS")
'
  say "COMPOSE_CONFIG=PASS"
  say "AUTH_ORIGIN=https://$FOLIOSENTRY_DOMAIN"
  say "DB_PASSWORD_FILE=PRIVATE_REDACTED"
  say "PUBLICATION=NOT_PERFORMED"
}
require_release() {
  [[ "$(git -C "$ROOT" branch --show-current)" == "main" ]] ||
    fatal "Deployment only from reviewed main, not Draft feature branches"
  [[ -z "$(git -C "$ROOT" status --porcelain)" ]] ||
    fatal "Git working tree is not clean"
  local remote_head
  remote_head=$(git -C "$ROOT" ls-remote origin refs/heads/main | awk 'NR==1 {print $1}')
  [[ -n "$remote_head" && "$(git -C "$ROOT" rev-parse HEAD)" == "$remote_head" ]] ||
    fatal "main must exactly match the GitHub main ref"
}
db_init() {
  [[ "${1:-}" == "--confirm-new-private-db" ]] ||
    fatal "Explicit authorization required: db-init --confirm-new-private-db"
  require_release
  check
  local existing
  existing=$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT" -q)
  [[ -z "$existing" ]] || fatal "Project containers already exist; initial DB migration refused"
  docker volume inspect "${PROJECT}_pgdata" >/dev/null 2>&1 &&
    fatal "Project database volume already exists; refuse to overwrite"
  say "Starting only new, separate PostgreSQL for $PROJECT"
  "${BASE[@]}" up -d db
  "${BASE[@]}" build backend
  say "Applying AUTH schema ONLY to new private $PROJECT database"
  "${BASE[@]}" run --rm --no-deps backend alembic upgrade head
  say "Set owner credentials interactively. They are not accepted on the command line."
  "${BASE[@]}" run --rm --no-deps backend python -m app.auth_cli init-owner
  say "FOLIOSENTRY_NEW_PRIVATE_DB_AUTH_INITIALIZED"
  say "Public HTTPS routing has NOT been enabled."
}
publish() {
  [[ "${1:-}" == "--confirm-public-https" ]] ||
    fatal "Explicit authorization required: publish --confirm-public-https"
  require_release
  check

  # Restrict publishing to the already-approved, healthy FolioSentry DB.
  local db_ids
  mapfile -t db_ids < <(docker ps -q \
    --filter "label=com.docker.compose.project=$PROJECT" \
    --filter 'label=com.docker.compose.service=db')
  [[ "${#db_ids[@]}" -eq 1 ]] ||
    fatal "Expected exactly one running FolioSentry PostgreSQL container"
  [[ "$(docker inspect -f '{{.State.Health.Status}}' "${db_ids[0]}")" == "healthy" ]] ||
    fatal "FolioSentry PostgreSQL not healthy"

  # Existing owner and auth schema must be available. No migrations/bootstrap.
  "${BASE[@]}" run --rm --no-deps backend python -c \
    "import sys; from app.auth import auth_ready; sys.exit(0 if auth_ready() else 1)" ||
    fatal "Owner not initialized / AUTH tables unavailable"
  say "FOLIOSENTRY_OWNER_AUTH_READY=PASS"

  # Fail closed unless a new, locally-private, checksummed dump is readable.
  # Restoring this dump is not attempted here; only the archive is checked.
  bash "$ROOT/scripts/backup-db.sh" --confirm-prepublish-backup ||
    fatal "Pre-publication private DB backup failed; no public router created"

  "${BASE[@]}" up -d backend
  local backend_cid health
  backend_cid=$("${BASE[@]}" ps -q backend)
  [[ -n "$backend_cid" ]] || fatal "Backend container not found"
  health=""
  for _ in $(seq 1 30); do
    health=$(docker inspect -f '{{.State.Health.Status}}' "$backend_cid" 2>/dev/null || :)
    [[ "$health" == "healthy" ]] && break
    sleep 2
  done
  [[ "$health" == "healthy" ]] ||
    fatal "Backend did not become healthy; no public router created"
  say "BACKEND_HEALTH=HEALTHY"

  say "Starting ONLY FolioSentry HTTPS frontend on existing Traefik"
  if ! "${EDGE[@]}" up -d --build --no-deps frontend; then
    if ! "${EDGE[@]}" stop frontend; then
      fatal "FRONTEND_START_FAILED_AND_STOP_FAILED_MANUAL_ACTION_REQUIRED"
    fi
    fatal "Frontend failed to start; own frontend was stopped"
  fi
  if ! python3 "$ROOT/scripts/verify-public-https.py"; then
    say "FOLIOSENTRY_HTTPS_VERIFY=FAIL_STOPPING_OWN_FRONTEND"
    if ! "${EDGE[@]}" stop frontend; then
      fatal "FAILED_TO_STOP_FOLIOSENTRY_FRONTEND_MANUAL_ACTION_REQUIRED"
    fi
    fatal "HTTPS checks failed; own frontend stopped; DB and existing apps unchanged"
  fi

  say "FOLIOSENTRY_PUBLIC_HTTPS_ACCEPTANCE_PASS"
  say "FOLIOSENTRY_PUBLIC_ROUTE_APPLIED"
  say "NEXT=MANUAL_OWNER_LOGIN_AND_PICKNEXT_BROWSER_ACCEPTANCE"
}
unpublish() {
  [[ "${1:-}" == "--confirm-stop-frontend-only" ]] ||
    fatal "Explicit authorization required: unpublish --confirm-stop-frontend-only"
  require_release
  read_settings
  need_deps
  # Project and service are explicitly scoped; DB/backend and other stacks stay up.
  "${EDGE[@]}" stop frontend
  say "FOLIOSENTRY_FRONTEND_STOPPED"
  say "DATABASE_AND_BACKEND_PRESERVED=YES"
}

case "${1:-help}" in
  inspect) exec bash "$ROOT/scripts/inspect-traefik.sh" ;;
  inspect-acme) exec python3 "$ROOT/scripts/inspect-traefik-acme.py" ;;
  configure) configure ;;
  check) check ;;
  db-init) db_init "${2:-}" ;;
  publish) publish "${2:-}" ;;
  unpublish) unpublish "${2:-}" ;;
  status)
    need_deps
    read_settings
    "${BASE[@]}" ps
    ;;
  help|--help|-h) usage ;;
  *) usage; exit 2 ;;
esac
