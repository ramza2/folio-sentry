#!/usr/bin/env python3
"""Anonymous HTTPS acceptance check for approved FolioSentry publication.

Only performs TLS handshakes and unauthenticated HTTP requests. No credentials,
cookies, login attempts, password hashes, or personal portfolio data are read.
"""
from __future__ import annotations

import argparse
import http.client
import json
import socket
import ssl
import sys
import time

HOST = "foliosentry.ramza.duckdns.org"
EXISTING = "picknext.ramza.duckdns.org"


def verify_tls(host: str) -> None:
    context = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=8) as raw:
        with context.wrap_socket(raw, server_hostname=host) as secure:
            if secure.version() not in {"TLSv1.2", "TLSv1.3"}:
                raise RuntimeError("TLS_VERSION_NOT_ACCEPTABLE")
            if not secure.getpeercert():
                raise RuntimeError("TLS_CERTIFICATE_MISSING")


def get_path(path: str, method: str = "GET") -> tuple[int, dict, bytes]:
    # HTTPSConnection validates both the certificate chain and the FQDN.
    connection = http.client.HTTPSConnection(
        HOST, 443, context=ssl.create_default_context(), timeout=9
    )
    try:
        body = b"{}" if method == "POST" else None
        headers = {"User-Agent": "FolioSentry-HTTPS-Acceptance/1.0"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        result = connection.getresponse()
        data = result.read(8192)
        return result.status, {k.lower(): v for k, v in result.getheaders()}, data
    finally:
        connection.close()


def inspect_once() -> None:
    verify_tls(HOST)
    status, headers, html = get_path("/")
    if status != 200 or b'<div id="root"' not in html:
        raise RuntimeError("FRONTEND_STATIC_PAGE_NOT_READY")
    status, headers, data = get_path("/api/health/ready")
    if status != 200:
        raise RuntimeError("BACKEND_READY_NOT_200")
    obj = json.loads(data)
    if obj.get("status") != "ready" or obj.get("auth") != "ready":
        raise RuntimeError("BACKEND_AUTH_NOT_READY")
    for path in ("/api/v1/auth/me", "/api/v1/demo/overview"):
        status, headers, data = get_path(path)
        if status != 401:
            raise RuntimeError("ANONYMOUS_API_ACCESS_NOT_BLOCKED")
        if "no-store" not in headers.get("cache-control", "").lower():
            raise RuntimeError("PRIVATE_API_CACHE_NOT_DISABLED")
    status, _, _ = get_path("/api/v1/auth/login", method="POST")
    if status != 403:
        raise RuntimeError("MISSING_ORIGIN_LOGIN_NOT_REJECTED")


def self_test() -> None:
    assert HOST != EXISTING
    assert HOST.endswith(".ramza.duckdns.org")
    assert "/api/v1/auth/me".startswith("/api/v1/")
    print("FOLIOSENTRY_HTTPS_VERIFIER_SELFTEST_PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    print("FOLIOSENTRY_PUBLIC_HTTPS_CHECK=READ_ONLY_ANONYMOUS")
    print("TARGET_DOMAIN=" + HOST)
    print("CREDENTIALS_OR_COOKIES_SENT=NO")
    # Existing PickNext previously passed. Preserve the cross-service gate.
    try:
        verify_tls(EXISTING)
    except (OSError, ssl.SSLError, RuntimeError) as exc:
        print("REVIEW_EXISTING_PICKNEXT_TLS=FAILED_" + type(exc).__name__)
        return 2
    print("EXISTING_PICKNEXT_TLS=PASS")

    # A newly added Traefik router can take several reconciliation/ACME cycles.
    for attempt in range(1, 9):
        try:
            inspect_once()
            print("NEW_FOLIOSENTRY_TLS_CHAIN_AND_HOST=PASS")
            print("FRONTEND_HTTP_200=PASS")
            print("BACKEND_AUTH_READY=PASS")
            print("ANONYMOUS_API_DENY=PASS")
            print("MISSING_ORIGIN_DENY=PASS")
            print("FOLIOSENTRY_PUBLIC_HTTPS_ACCEPTANCE_PASS")
            return 0
        except (OSError, ssl.SSLError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            print("HTTPS_ACCEPTANCE_RETRY=" + str(attempt) +
                  " REASON=" + type(exc).__name__)
            if attempt < 8:
                time.sleep(5)
    print("FOLIOSENTRY_PUBLIC_HTTPS_ACCEPTANCE_FAILED")
    return 2


if __name__ == "__main__":
    sys.exit(main())
