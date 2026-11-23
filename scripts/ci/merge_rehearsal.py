#!/usr/bin/env python3
"""Read-only rehearsal of CI / Draft PR merges in a disposable bare Git repo.

Never checks out, commits, merges, writes to, or pushes the user's worktree.
The only network request is an authenticated git fetch from the pinned private
GitHub repository into a TemporaryDirectory. No KIS, Docker, or database.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

REMOTE_RE = re.compile(
    r"(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
    r"ramza2/folio-sentry(?:\.git)?"
)
SHA_RE = re.compile(r"[0-9a-f]{40}")
BRANCHES = {
    "main": ("main", "c156cfd9e094c747caf3f9c48ecf73eee5759699"),
    "ci": ("ci/usage-control-20261120",
           "684309266ebbb495958352b3902acedce51f7d18"),
    "pr24": ("feat/md02b-kis-first-readonly-probe-20261120",
             "88a77b27990c7f23bc0a26917a0c99090fb2776d"),
    "pr25": ("feat/md02d-kis-shared-token-quota-20261120",
             "b8bcbc5bd23613fcecf1117df7e0443fa729d550"),
    "pr26": ("feat/md03-price-bar-additive-offline-20261120",
             "9947c90bc5801f42db2891961c95ffbd3e96398a"),
    "combined": ("review/ci-kis-offline-integration-20261123",
                 "0c1c22ada265a3607d0436f7b138b79356cf7f56"),
}

# Every pair is independently based on the SAME pinned main ancestry.
# Conflict counts here are not a complete sequential merge simulation.
PAIRS = (
    ("main", "ci"),
    ("ci", "pr24"),
    ("ci", "pr25"),
    ("ci", "pr26"),
    ("pr24", "pr25"),
    ("pr24", "pr26"),
    ("pr25", "pr26"),
)

# Verify that the pre-reviewed integrated tree really retains code from each
# input. Workflow and AGENTS/ROADMAP intentionally differ by safe resolution.
CODE_PATHS = {
    "ci": (
        ".github/workflows/auth-browser.yml",
        "scripts/ci/impact.py",
        "scripts/ci/final_gate.py",
        "scripts/ci/test_impact.py",
        "scripts/ci/test_final_gate.py",
        "scripts/ci/test_public_audit.py",
        "scripts/ci/test_workflow_contract.py",
        "scripts/public-visibility-preflight.py",
    ),
    "pr24": (
        "backend/app/kis_first_probe.py",
        "backend/tests/test_kis_first_probe.py",
        "backend/tests/test_kis_secret_setup.py",
        "scripts/kis-secret-setup.py",
    ),
    "pr25": (
        "backend/app/kis_readonly.py",
        "backend/app/kis_shared_state.py",
        "backend/tests/test_kis_shared_state.py",
    ),
    "pr26": (
        "backend/app/exchange_calendar.py",
        "backend/app/price_models.py",
        "backend/app/price_quality.py",
        "backend/app/price_repository.py",
        "backend/migrations/env.py",
        "backend/migrations/versions/20261120_pricebar01.py",
        "backend/scripts/test_price_bar_isolated_ci.py",
        "backend/tests/test_price_quality.py",
    ),
}


class RehearsalError(RuntimeError):
    """Only static status codes; never secret-bearing Git output."""


@dataclass(frozen=True)
class MergeResult:
    conflicted_paths: tuple[str, ...]


def git(cwd: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            ["git", "-C", str(cwd), *args],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, encoding="utf-8",
            errors="replace", timeout=timeout, check=False, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RehearsalError("GIT_COMMAND_UNAVAILABLE_OR_TIMEOUT") from None


def require_ok(result: subprocess.CompletedProcess[str], code: str) -> str:
    if result.returncode != 0:
        raise RehearsalError(code)
    return result.stdout.strip()


def safe_remote(url: str) -> bool:
    return bool(REMOTE_RE.fullmatch(url.strip()))


def parse_merge_output(returncode: int, stdout: str) -> MergeResult:
    if returncode not in (0, 1):
        raise RehearsalError("MERGE_TREE_COMMAND_FAILED")
    lines = stdout.splitlines()
    if not lines or SHA_RE.fullmatch(lines[0]) is None:
        raise RehearsalError("MERGE_TREE_OUTPUT_INVALID")
    paths = tuple(lines[1:])
    if returncode == 0 and paths:
        raise RehearsalError("MERGE_TREE_UNEXPECTED_CONFLICT_PATHS")
    if returncode == 1 and not paths:
        raise RehearsalError("MERGE_TREE_MISSING_CONFLICT_PATHS")
    if any(not path or "\t" in path or "\r" in path for path in paths):
        raise RehearsalError("MERGE_TREE_CONFLICT_PATH_INVALID")
    return MergeResult(conflicted_paths=paths)


def preflight(source: Path) -> str:
    root = require_ok(git(source, "rev-parse", "--show-toplevel"),
                      "SOURCE_NOT_GIT_REPOSITORY")
    if Path(root).resolve() != source.resolve():
        raise RehearsalError("SOURCE_MUST_BE_REPOSITORY_ROOT")
    remote = require_ok(git(source, "remote", "get-url", "origin"),
                        "ORIGIN_REMOTE_UNAVAILABLE")
    if not safe_remote(remote):
        raise RehearsalError("UNAPPROVED_ORIGIN_REMOTE")
    version = require_ok(git(source, "--version"), "GIT_VERSION_UNAVAILABLE")
    match = re.search(r"git version (\d+)\.(\d+)", version)
    if match is None or (int(match.group(1)), int(match.group(2))) < (2, 39):
        raise RehearsalError("GIT_MERGE_TREE_VERSION_TOO_OLD")
    return remote


def validate_fetched_refs(temp: Path) -> None:
    for label, (_, expected) in BRANCHES.items():
        result = require_ok(
            git(temp, "rev-parse", "--verify", "refs/heads/rehearsal/" + label),
            "FETCHED_REF_NOT_FOUND",
        )
        if result != expected:
            raise RehearsalError("REMOTE_BRANCH_MOVED_" + label.upper())


def validate_code_blobs(temp: Path) -> int:
    total = 0
    for label, paths in CODE_PATHS.items():
        for path in paths:
            left = require_ok(
                git(temp, "rev-parse", "--verify",
                    "refs/heads/rehearsal/" + label + ":" + path),
                "PR_CODE_BLOB_MISSING",
            )
            right = require_ok(
                git(temp, "rev-parse", "--verify",
                    "refs/heads/rehearsal/combined:" + path),
                "COMBINED_CODE_BLOB_MISSING",
            )
            if left != right:
                # Do not silently accept a changed security implementation.
                print("FOLIOSENTRY_MERGE_BLOB_MISMATCH_PATH=" + path)
                raise RehearsalError("COMBINED_CODE_DIFFERS_FROM_DRAFT")
            total += 1
    return total


def run(source: Path) -> None:
    remote = preflight(source)
    print("FOLIOSENTRY_MERGE_REHEARSAL_PREFLIGHT_PASS_NO_WORKTREE_CHANGE")
    with tempfile.TemporaryDirectory(prefix="foliosentry-merge-rehearsal-") as directory:
        temp = Path(directory) / "bare.git"
        require_ok(git(temp.parent, "init", "--bare", "--quiet", str(temp)),
                   "TEMP_BARE_GIT_INIT_FAILED")
        require_ok(git(temp, "remote", "add", "origin", remote),
                   "TEMP_REMOTE_ADD_FAILED")
        refspecs = [
            "refs/heads/" + branch + ":refs/heads/rehearsal/" + label
            for label, (branch, _) in BRANCHES.items()
        ]
        require_ok(
            git(temp, "fetch", "--quiet", "--no-tags", "--no-recurse-submodules",
                "origin", *refspecs, timeout=180),
            "READ_ONLY_PRIVATE_FETCH_FAILED",
        )
        validate_fetched_refs(temp)
        print("FOLIOSENTRY_MERGE_REHEARSAL_PINNED_REFS_PASS")
        count = validate_code_blobs(temp)
        print("FOLIOSENTRY_MERGE_REHEARSAL_MATCHED_CODE_BLOBS=" + str(count))

        conflicts = 0
        for left, right in PAIRS:
            result = git(temp, "merge-tree", "--write-tree", "--name-only",
                         "--no-messages", "refs/heads/rehearsal/" + left,
                         "refs/heads/rehearsal/" + right)
            paths = parse_merge_output(result.returncode, result.stdout).conflicted_paths
            conflicts += len(paths)
            print("MERGE_PAIR=" + left + "+" + right
                  + " CONFLICT_COUNT=" + str(len(paths)))
            for path in paths:
                print("MERGE_CONFLICT_FILE=" + left + "+" + right + ":" + path)
        print("FOLIOSENTRY_MERGE_REHEARSAL_TOTAL_PAIRWISE_CONFLICTS=" + str(conflicts))
        print("FOLIOSENTRY_MERGE_REHEARSAL_PAIRWISE_ONLY_NOT_SEQUENTIAL=YES")
        print("FOLIOSENTRY_MERGE_REHEARSAL_NO_MAIN_OR_PR_MUTATION=YES")
        print("FOLIOSENTRY_MERGE_REHEARSAL_REVIEW_COMPLETE_NOT_MERGE_APPROVAL")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.preflight:
            preflight(Path.cwd())
            print("FOLIOSENTRY_MERGE_REHEARSAL_PREFLIGHT_PASS_NO_FETCH")
        else:
            run(Path.cwd())
        return 0
    except RehearsalError as exc:
        print("FOLIOSENTRY_MERGE_REHEARSAL_FAIL=" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
