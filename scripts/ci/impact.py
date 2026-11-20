"""FolioSentry GitHub Actions changed-area selector (stdlib only).

Fail closed: unknown changes, invalid refs, diff failures => run ALL checks.
No external actions/service APIs, no secret access, no user data logging.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
from typing import Iterable

JOBS = (
    "backend",
    "frontend",
    "compose-config",
    "auth-db-migration",
    "deploy01-production-config",
    "deploy02-backup-e2e",
)
ALL = frozenset(JOBS)
SHA = re.compile(r"^[0-9a-f]{40}$")


def classify(paths: Iterable[str]) -> frozenset[str]:
    chosen: set[str] = set()
    for path in paths:
        if not isinstance(path, str) or not path or path.startswith("/") \
                or ".." in Path(path).parts or "\n" in path:
            return ALL
        # Deployment CI/workflow / routing changes require ALL checks.
        if path.startswith(".github/workflows/") or path.startswith("scripts/ci/"):
            return ALL
        if path in ("README.md", "AGENTS.md") or path.startswith("docs/") \
                or path.endswith(".md"):
            continue
        if path.startswith("backend/"):
            chosen.add("backend")
            if path.startswith("backend/migrations/") \
                    or path.startswith("backend/scripts/") \
                    or path in ("backend/pyproject.toml", "backend/alembic.ini") \
                    or path.startswith("backend/app/auth") \
                    or path.startswith("backend/app/portfolio") \
                    or path.startswith("backend/app/price") \
                    or path in ("backend/app/database.py", "backend/app/config.py") \
                    or path.startswith("backend/tests/test_auth") \
                    or path.startswith("backend/tests/test_portfolio") \
                    or path.startswith("backend/tests/test_price") \
                    or path == "backend/tests/conftest.py":
                chosen.add("auth-db-migration")
            continue
        if path.startswith("frontend/"):
            chosen.add("frontend")
            if path in ("frontend/Dockerfile.prod", "frontend/nginx.prod.conf",
                        "frontend/package.json", "frontend/package-lock.json"):
                chosen.add("deploy01-production-config")
            continue
        if path == "compose.yaml":
            chosen.add("compose-config")
            continue
        if path in ("compose.production.yml", "compose.traefik.yml"):
            chosen.update(("compose-config", "deploy01-production-config",
                           "deploy02-backup-e2e"))
            continue
        if path == ".env.example":
            chosen.update(("compose-config", "deploy01-production-config"))
            continue
        if path.startswith("ops/systemd/"):
            chosen.add("deploy02-backup-e2e")
            continue
        if path == "scripts/minipc-auth-preflight.sh":
            chosen.add("compose-config")
            continue
        if path in (
            "scripts/backup-db.sh", "scripts/run-daily-backup.sh",
            "scripts/test-backup-ci.sh", "scripts/verify-backup-restore.sh",
        ):
            chosen.add("deploy02-backup-e2e")
            if path == "scripts/backup-db.sh":
                chosen.add("deploy01-production-config")
            continue
        if path in (
            "scripts/deploy.sh", "scripts/phase1-live-preflight.sh",
            "scripts/phase1-app-deploy.sh", "scripts/inspect-traefik.sh",
            "scripts/check-duckdns-route.sh", "scripts/verify-public-https.py",
            "scripts/check-existing-tls.py", "scripts/inspect-traefik-acme.py",
        ):
            chosen.add("deploy01-production-config")
            continue
        if path == "scripts/kis-secret-setup.py":
            chosen.add("backend")
            continue
        # Unknown shell/code/config must never be silently skipped.
        return ALL
    return frozenset(chosen)


def _files_for_commit_range(base: str, head: str) -> tuple[str, ...]:
    if SHA.fullmatch(base) is None or SHA.fullmatch(head) is None \
            or base == "0" * 40:
        raise ValueError("INVALID_CI_COMMIT_RANGE")
    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", "--no-renames", base, head],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=30,
    )
    return tuple(
        value.decode("utf-8", errors="strict")
        for value in result.stdout.split(b"\0") if value
    )


def selected_jobs(event: str, base: str, head: str) -> tuple[frozenset[str], str]:
    if event == "workflow_dispatch":
        return ALL, "MANUAL_FULL"
    if event not in ("pull_request", "push"):
        return ALL, "UNKNOWN_EVENT_FULL"
    try:
        paths = _files_for_commit_range(base, head)
        selected = classify(paths)
    except (ValueError, UnicodeError, OSError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired):
        return ALL, "UNDETERMINED_FULL"
    if selected == ALL:
        return ALL, "ALL_CHANGED_OR_UNKNOWN"
    return selected, "CHANGED_AREAS"


def main():
    selected, reason = selected_jobs(
        os.environ.get("GITHUB_EVENT_NAME", ""),
        os.environ.get("FOLIOSENTRY_CI_BASE", ""),
        os.environ.get("FOLIOSENTRY_CI_HEAD", ""),
    )
    outpath = os.environ.get("GITHUB_OUTPUT")
    if not outpath:
        raise SystemExit("CI_OUTPUT_REQUIRED")
    with open(outpath, "a", encoding="utf-8") as stream:
        for job in JOBS:
            stream.write(f"{job}={'true' if job in selected else 'false'}\n")
    # Do not print commit diffs, source file contents or credentials.
    print("FOLIOSENTRY_CI_ROUTE=" + reason)
    print("FOLIOSENTRY_CI_SELECTED_JOB_COUNT=" + str(len(selected)))


if __name__ == "__main__":
    main()
