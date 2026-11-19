#!/usr/bin/env bash
# Read-only DuckDNS address comparison. No DNS IP address is printed.
# Never edits DuckDNS, Traefik, ipTIME or the host.
set -Eeuo pipefail

BASE="picknext.ramza.duckdns.org"
CANDIDATE="${1:-foliosentry.ramza.duckdns.org}"

if [[ "${1:-}" == "--help" || $# -gt 1 ]]; then
  echo "Usage: bash scripts/check-duckdns-route.sh [candidate.example.duckdns.org]"
  exit 0
fi

if [[ ! "$CANDIDATE" =~ ^[a-z0-9][a-z0-9.-]{1,240}\.duckdns\.org$ ||
      "$CANDIDATE" == *..* || "$CANDIDATE" == "$BASE" ]]; then
  echo "REVIEW_CANDIDATE_DOMAIN=INVALID_OR_EXISTING_SERVICE"
  exit 2
fi

command -v getent >/dev/null 2>&1 || { echo "REVIEW_DNS_TOOL=UNAVAILABLE"; exit 2; }
resolved() {
  getent ahostsv4 "$1" 2>/dev/null |
    awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+[[:space:]]/ {print $1}' | sort -u
}

echo "DNS_CHECK_MODE=READ_ONLY"
echo "EXISTING_SERVICE_DOMAIN=$BASE"
echo "CANDIDATE_DOMAIN=$CANDIDATE"
echo "IP_VALUES_PRINTED=NO"
echo "TLS_CERTIFICATE_VERIFIED=NO"
BASE_IPS="$(resolved "$BASE")"
CANDIDATE_IPS="$(resolved "$CANDIDATE")"
if [[ -z "$BASE_IPS" ]]; then
  echo "REVIEW_EXISTING_PICKNEXT_DNS=UNRESOLVED"
  exit 2
fi
if [[ -z "$CANDIDATE_IPS" ]]; then
  echo "REVIEW_CANDIDATE_DNS=UNRESOLVED"
  exit 2
fi
if [[ "$BASE_IPS" != "$CANDIDATE_IPS" ]]; then
  echo "REVIEW_DUCKDNS_IP_MAPPING=DIFFERS_FROM_EXISTING_PICKNEXT"
  exit 2
fi
echo "DUCKDNS_IPV4_MAPPING=PASS_SAME_AS_PICKNEXT"
echo "NEXT_STEP=VALIDATE_TLS_CERTIFICATE_SEPARATELY_BEFORE_PUBLICATION"
echo "FOLIOSENTRY_DUCKDNS_READONLY_CHECK_PASS"
