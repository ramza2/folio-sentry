#!/usr/bin/env python3
"""Read-only public-visibility preflight for local Git history.

No network, no writes, no printing any token/secret/plaintext. Checks reachable
Git objects in refs present in THIS clone. It cannot inspect GitHub Actions
logs, GitHub-only refs, LFS contents, or secrets disguised by encoding.
A green result is NOT sufficient authorization to change visibility.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import subprocess
import sys

MAX_BLOB = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_OBJECTS = 30000

PATTERNS = {
    "private_key_header": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "github_token": re.compile(
        rb"(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{40,})"
    ),
    "aws_access_key": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "http_bearer": re.compile(
        rb"(?i:\bBearer[ \t]+)(?:[A-Za-z0-9_\-.]{30,})"
    ),
    "credential_assignment": re.compile(
        rb"(?im)^[ \t]*(?:export[ \t]+)?"
        rb"(?:KIS_)?(?:APPKEY|APPSECRET|APP_KEY|APP_SECRET|"
        rb"GITHUB_TOKEN|GITHUB_PAT|DB_PASSWORD|POSTGRES_PASSWORD|"
        rb"API_KEY|ACCESS_TOKEN|CLIENT_SECRET|PRIVATE_KEY)"
        rb"[ \t]*=[ \t]*[\"']?([A-Za-z0-9_+./:=-]{12,})"
    ),
}
PLACEHOLDER = re.compile(
    rb"(?i:synthetic|dummy|example|placeholder|fake|ci.only|test.only|"
    rb"replace.me|not.a.real|change.me|os\.environ|environ|getenv)"
)
OPERATIONAL = re.compile(
    rb"(?i:ramza\.duckdns\.org|ramzaminiserver|192\.168\.[0-9]{1,3}\.[0-9]{1,3})"
)
SENSITIVE_PATH = re.compile(
    r"(?i)(?:^|/)(?:\.env(?!\.example$)(?:\.[^/]+)?|id_rsa|id_ed25519|"
    r"kis_appkey|kis_appsecret|pg_password|credentials(?:\.[^/]*)?|"
    r"secrets?(?:\.[^/]*)?)$|"
    r"\.(?:pem|p12|pfx|key|jks|keystore|sqlite3?|dump|bak)$"
)


class AuditError(Exception):
    pass


def _git(*args: str, input_data: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args], input=input_data,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=True, timeout=120,
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise AuditError("GIT_AUDIT_COMMAND_FAILED") from None


def scan_blob(content: bytes) -> Counter:
    flags: Counter = Counter()
    for name, pattern in PATTERNS.items():
        hits = pattern.findall(content)
        if name == "credential_assignment":
            hits = [h for h in hits if not PLACEHOLDER.search(h)]
        if hits:
            flags[name] += len(hits)
    if OPERATIONAL.search(content):
        flags["operational_endpoint_exposure"] += 1
    return flags


def self_test():
    assert scan_blob(b"-----BEGIN " + b"PRIVATE KEY-----")["private_key_header"] == 1
    assert scan_blob(b"ghp_" + b"x" * 35)["github_token"] == 1
    assert scan_blob(b"KIS_APPSECRET=verylongsyntheticsecretvalue123")["credential_assignment"] == 0
    assert scan_blob(b"KIS_APPSECRET=" + b"useConcreteSecureValue123")["credential_assignment"] == 1
    assert scan_blob(b"FOLIOSENTRY_DB_PASSWORD=")["credential_assignment"] == 0
    assert scan_blob(b"notes for " + b"ramza" + b"miniserver")["operational_endpoint_exposure"] == 1
    print("FOLIOSENTRY_PREPUBLIC_SCANNER_SYNTHETIC_SELFTEST_PASS")


def locate_private_key_headers():
    """Print only matching Git object IDs/path/line, never any blob content."""
    if _git("rev-parse", "--is-shallow-repository").strip() == b"true":
        raise AuditError("SHALLOW_HISTORY_INCOMPLETE")
    rows = _git("rev-list", "--objects", "--all").splitlines()
    if len(rows) > MAX_OBJECTS:
        raise AuditError("HISTORY_TOO_LARGE_FOR_SCANNER")
    objects = {}
    for row in rows:
        raw_sha, _, raw_path = row.partition(b" ")
        if not re.fullmatch(rb"[0-9a-f]{40,64}", raw_sha):
            raise AuditError("INVALID_GIT_OBJECT_LIST")
        objects.setdefault(raw_sha.decode("ascii"), raw_path.decode("utf-8", "replace"))
    info = _git(
        "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        input_data=("\n".join(objects) + "\n").encode("ascii"),
    ).splitlines()
    found = 0
    scanned_bytes = 0
    for record in info:
        parts = record.split()
        if len(parts) != 3:
            raise AuditError("INVALID_GIT_OBJECT_METADATA")
        sha_raw, kind, length = parts
        if kind != b"blob":
            continue
        size = int(length)
        if size > MAX_BLOB or scanned_bytes + size > MAX_TOTAL_BYTES:
            raise AuditError("KEY_HEADER_AUDIT_INCOMPLETE_LARGE_OBJECT")
        scanned_bytes += size
        sha = sha_raw.decode("ascii")
        data = _git("cat-file", "blob", sha)
        if len(data) != size:
            raise AuditError("GIT_BLOB_SIZE_MISMATCH")
        if b"\0" in data[:8192]:
            continue
        for match in PATTERNS["private_key_header"].finditer(data):
            found += 1
            path = objects.get(sha, "")
            # Strict ASCII path allowlist prevents log/control character injection.
            if not re.fullmatch(r"[A-Za-z0-9_./-]{1,300}", path):
                path = "PATH_REDACTED"
            footer = match.group(0).replace(b"BEGIN", b"END", 1)
            has_footer = footer in data[match.end():match.end() + 8192]
            print("FOLIOSENTRY_KEY_HEADER_BLOB_SHA=" + sha)
            print("FOLIOSENTRY_KEY_HEADER_PATH=" + path)
            print("FOLIOSENTRY_KEY_HEADER_LINE=" + str(data.count(b"\n", 0, match.start()) + 1))
            print("FOLIOSENTRY_KEY_HEADER_FOOTER_WITHIN_8K=" + ("YES" if has_footer else "NO"))
    print("FOLIOSENTRY_KEY_HEADER_MATCHES=" + str(found))
    print("FOLIOSENTRY_KEY_HEADER_VALUES_PRINTED=NO")
    print("FOLIOSENTRY_PREPUBLIC_VISIBILITY_APPROVAL=MANUAL_REVIEW_REQUIRED")


def locate_operational_paths():
    """Report file paths/counts only, without hostnames, IPs, or content."""
    if _git("rev-parse", "--is-shallow-repository").strip() == b"true":
        raise AuditError("SHALLOW_HISTORY_INCOMPLETE")
    rows = _git("rev-list", "--objects", "--all").splitlines()
    if len(rows) > MAX_OBJECTS:
        raise AuditError("HISTORY_TOO_LARGE_FOR_SCANNER")
    objects = {}
    for row in rows:
        raw_sha, _, raw_path = row.partition(b" ")
        if not re.fullmatch(rb"[0-9a-f]{40,64}", raw_sha):
            raise AuditError("INVALID_GIT_OBJECT_LIST")
        objects.setdefault(raw_sha.decode("ascii"), raw_path.decode("utf-8", "replace"))
    sizes = _git(
        "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        input_data=("\n".join(objects) + "\n").encode("ascii"),
    ).splitlines()
    counts: Counter = Counter()
    scanned_bytes = 0
    scanned = 0
    for item in sizes:
        parts = item.split()
        if len(parts) != 3:
            raise AuditError("INVALID_GIT_OBJECT_METADATA")
        sha_raw, kind, raw_size = parts
        if kind != b"blob":
            continue
        size = int(raw_size)
        if size > MAX_BLOB or scanned_bytes + size > MAX_TOTAL_BYTES:
            raise AuditError("OPERATIONAL_AUDIT_INCOMPLETE_LARGE_OBJECT")
        scanned_bytes += size
        data = _git("cat-file", "blob", sha_raw.decode("ascii"))
        if len(data) != size:
            raise AuditError("GIT_BLOB_SIZE_MISMATCH")
        scanned += 1
        if b"\0" in data[:8192] or not OPERATIONAL.search(data):
            continue
        path = objects[sha_raw.decode("ascii")]
        if not re.fullmatch(r"[A-Za-z0-9_./-]{1,300}", path):
            path = "PATH_REDACTED"
        counts[path] += 1
    print("FOLIOSENTRY_OPERATIONAL_SCANNED_BLOBS=" + str(scanned))
    print("FOLIOSENTRY_OPERATIONAL_AFFECTED_BLOB_VERSIONS=" + str(sum(counts.values())))
    print("FOLIOSENTRY_OPERATIONAL_UNIQUE_PATHS=" + str(len(counts)))
    # Show at most 50 paths. Names are sanitized and no matched values are shown.
    for path, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:50]:
        print("FOLIOSENTRY_OPERATIONAL_PATH=" + path + " VERSIONS=" + str(count))
    print("FOLIOSENTRY_OPERATIONAL_OMITTED_PATHS=" + str(max(0, len(counts)-50)))
    print("FOLIOSENTRY_OPERATIONAL_VALUES_PRINTED=NO")
    print("FOLIOSENTRY_PREPUBLIC_VISIBILITY_APPROVAL=MANUAL_REVIEW_REQUIRED")


def audit():
    if not Path(".git").exists():
        try:
            root = _git("rev-parse", "--show-toplevel").decode().strip()
        except AuditError:
            raise AuditError("REPOSITORY_NOT_FOUND") from None
        if not root:
            raise AuditError("REPOSITORY_NOT_FOUND")
    if _git("rev-parse", "--is-shallow-repository").strip() == b"true":
        raise AuditError("SHALLOW_HISTORY_INCOMPLETE")
    # rev-list includes all objects reachable from refs available locally.
    rows = _git("rev-list", "--objects", "--all").splitlines()
    objects = {}
    flags: Counter = Counter()
    if len(rows) > MAX_OBJECTS:
        raise AuditError("HISTORY_TOO_LARGE_FOR_SCANNER")
    for line in rows:
        sha, _, path = line.partition(b" ")
        if not re.fullmatch(rb"[a-f0-9]{40,64}", sha):
            raise AuditError("INVALID_GIT_OBJECT_LIST")
        objects.setdefault(sha.decode("ascii"), path.decode("utf-8", "replace"))
        if path and SENSITIVE_PATH.search(path.decode("utf-8", "replace")) \
                and ".env.example" not in path.decode("utf-8", "replace"):
            flags["sensitive_historical_path"] += 1
    check = _git(
        "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        input_data=("\n".join(objects) + "\n").encode("ascii"),
    ).splitlines()
    size_total = 0
    scanned = 0
    for record in check:
        items = record.split()
        if len(items) != 3:
            raise AuditError("INVALID_GIT_OBJECT_METADATA")
        sha, kind, rawsize = items
        if kind != b"blob":
            continue
        size = int(rawsize)
        if size > MAX_BLOB or size_total + size > MAX_TOTAL_BYTES:
            flags["unscanned_large_blob"] += 1
            continue
        size_total += size
        content = _git("cat-file", "blob", sha.decode("ascii"))
        if len(content) != size:
            raise AuditError("GIT_BLOB_SIZE_MISMATCH")
        scanned += 1
        if b"\0" in content[:8192]:
            flags["unscanned_binary_blob"] += 1
            continue
        flags.update(scan_blob(content))
    print("FOLIOSENTRY_PREPUBLIC_REACHABLE_OBJECTS=" + str(len(objects)))
    print("FOLIOSENTRY_PREPUBLIC_TEXT_BLOBS_SCANNED=" + str(scanned))
    # Only categories/counts. NEVER echo file content, match or credentials.
    for name in (*PATTERNS, "sensitive_historical_path",
                 "operational_endpoint_exposure", "unscanned_binary_blob",
                 "unscanned_large_blob"):
        print("FOLIOSENTRY_PREPUBLIC_" + name.upper() + "=" + str(flags[name]))
    print("FOLIOSENTRY_PREPUBLIC_GITHUB_ACTIONS_LOGS=NOT_SCANNED")
    print("FOLIOSENTRY_PREPUBLIC_REMOTE_ONLY_REFS=NOT_SCANNED")
    print("FOLIOSENTRY_PREPUBLIC_VISIBILITY_APPROVAL=MANUAL_REVIEW_REQUIRED")
    if any(flags.values()):
        print("FOLIOSENTRY_PREPUBLIC_RESULT=REVIEW_FLAGS_PRESENT")
    else:
        print("FOLIOSENTRY_PREPUBLIC_RESULT=NO_HEURISTIC_FLAGS_NOT_A_CLEARANCE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--locate-key-headers", action="store_true")
    parser.add_argument("--locate-operational-paths", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
        elif args.locate_key_headers:
            locate_private_key_headers()
        elif args.locate_operational_paths:
            locate_operational_paths()
        else:
            audit()
    except AuditError as exc:
        print("FOLIOSENTRY_PREPUBLIC_AUDIT_INCOMPLETE=" + str(exc))
        sys.exit(2)
