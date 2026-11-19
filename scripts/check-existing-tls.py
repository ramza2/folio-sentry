#!/usr/bin/env python3
"""Read-only TLS readiness check against EXISTING PickNext host.

Only opens a TLS handshake to the existing working domain. Does not request a
certificate, touch Docker or DuckDNS, or connect to the proposed new router.
Never prints IPs, certificate serials, DNS/provider credentials, or full SANs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import socket
import ssl
import sys

EXISTING = "picknext.ramza.duckdns.org"
CANDIDATE = "foliosentry.ramza.duckdns.org"


def covers_host(pattern: str, host: str) -> bool:
    """Check simple RFC6125 single-level wildcard SAN matching, fail-closed."""
    pattern, host = pattern.casefold().rstrip("."), host.casefold().rstrip(".")
    if "*" not in pattern:
        return pattern == host
    if not pattern.startswith("*.") or pattern.count("*") != 1:
        return False
    suffix = pattern[2:]
    head, sep, tail = host.partition(".")
    return bool(head) and bool(sep) and tail == suffix


def self_test() -> None:
    cases = (
        ("picknext.ramza.duckdns.org", EXISTING, True),
        ("*.ramza.duckdns.org", CANDIDATE, True),
        ("*.ramza.duckdns.org", "nested.foliosentry.ramza.duckdns.org", False),
        ("*.duckdns.org", CANDIDATE, False),
        ("*.example.duckdns.org", CANDIDATE, False),
        ("*.*.duckdns.org", CANDIDATE, False),
        (EXISTING, CANDIDATE, False),
    )
    for pattern, host, expected in cases:
        assert covers_host(pattern, host) is expected, (pattern, host)
    print("FOLIOSENTRY_TLS_SAN_MATCHER_TEST_PASS")


def check_existing() -> int:
    print("TLS_CHECK_MODE=READ_ONLY_EXISTING_DOMAIN_ONLY")
    print(f"EXISTING_SERVICE_DOMAIN={EXISTING}")
    print(f"NEW_CANDIDATE_DOMAIN={CANDIDATE}")
    print("DNS_IP_VALUES_PRINTED=NO")
    print("NEW_CANDIDATE_TLS_CERT_ISSUANCE_VERIFIED=NO")
    context = ssl.create_default_context()
    try:
        with socket.create_connection((EXISTING, 443), timeout=9) as raw:
            with context.wrap_socket(raw, server_hostname=EXISTING) as connection:
                certificate = connection.getpeercert()
    except (OSError, ssl.SSLError, TimeoutError):
        print("REVIEW_PICKNEXT_TLS=CONNECTIVITY_OR_TRUST_ERROR")
        print("NOTE=LOCAL_ROUTER_HAIRPIN_NAT_MAY_BLOCK_PUBLIC_ADDRESS_FROM_LAN")
        return 2

    print("PICKNEXT_TLS_TRUST_AND_HOSTNAME=PASS")
    if not isinstance(certificate, dict) or "notAfter" not in certificate:
        print("REVIEW_PICKNEXT_TLS=CERT_METADATA_UNAVAILABLE")
        return 2

    try:
        expires = datetime.fromtimestamp(
            ssl.cert_time_to_seconds(certificate["notAfter"]), tz=timezone.utc
        )
    except (TypeError, ValueError):
        print("REVIEW_PICKNEXT_TLS=EXPIRY_UNREADABLE")
        return 2
    days_left = (expires - datetime.now(timezone.utc)).days
    print(f"PICKNEXT_TLS_DAYS_REMAINING={days_left}")

    sans = certificate.get("subjectAltName", ())
    names = tuple(name for kind, name in sans if kind == "DNS" and isinstance(name, str))
    if not names:
        print("CANDIDATE_COVERED_BY_EXISTING_CERT=UNKNOWN_NO_DNS_SAN")
    else:
        print(
            "CANDIDATE_COVERED_BY_EXISTING_CERT=" +
            ("YES" if any(covers_host(name, CANDIDATE) for name in names) else "NO")
        )
    if days_left < 14:
        print("REVIEW_PICKNEXT_CERTIFICATE=EXPIRES_WITHIN_14_DAYS")
        return 2

    print("TRAEFIK_NEW_ROUTER_OR_CERTIFICATE_REQUESTED=NO")
    print("NEXT_STEP=VERIFY_CERTRESOLVER_CHALLENGE_AND_NEW_HOST_TLS_AFTER_APPROVED_ROUTER")
    print("FOLIOSENTRY_EXISTING_TLS_READONLY_CHECK_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Offline SAN-matching regression tests")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    return check_existing()


if __name__ == "__main__":
    sys.exit(main())
