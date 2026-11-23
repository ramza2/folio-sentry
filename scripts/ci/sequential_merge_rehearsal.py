#!/usr/bin/env python3
"""Rehearse CI -> PR #24 -> #25 -> #26 in a disposable bare Git repository.

This program never merges/checks out/resets the source worktree and never pushes.
Conflicts in the 3 known shared files are resolved using pinned, reviewed
blobs, solely in a temporary synthetic merge. No Docker, KIS or database.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from merge_rehearsal import (
    BRANCHES, CODE_PATHS, RehearsalError, git, preflight,
    require_ok, validate_fetched_refs, validate_code_blobs,
    parse_merge_output,
)

ORDER = ("ci", "pr24", "pr25", "pr26")
DOCS = frozenset(("AGENTS.md", "docs/ROADMAP.md"))
ALLOWED = {
    "ci": frozenset(),
    "pr24": DOCS,
    "pr25": DOCS,
    "pr26": DOCS | frozenset((".github/workflows/ci.yml",)),
}
MANAGED = ("AGENTS.md", "docs/ROADMAP.md", ".github/workflows/ci.yml")
INTEGRATION_FOLLOWUP = (
    "backend/tests/test_market_data_integration.py",
    "scripts/ci/md02_md03_offline_acceptance.py",
    "scripts/ci/test_ci_kis_combined_contract.py",
    "scripts/ci/run-md03-isolated-docker.sh",
    "scripts/ci/test_md03_isolated_docker_contract.py",
)


def temp_git(repo: Path, *args: str, index: Path | None = None):
    """Execute a Git plumbing command only against the disposable bare repo."""
    env = dict(os.environ)
    env.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "FolioSentry synthetic rehearsal",
        "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
        "GIT_COMMITTER_NAME": "FolioSentry synthetic rehearsal",
        "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
    })
    # Do not inherit a user's index override, even for bare read-tree.
    env.pop("GIT_INDEX_FILE", None)
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, encoding="utf-8",
            errors="replace", timeout=120, check=False, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RehearsalError("TEMP_GIT_PLUMBING_FAILED_OR_TIMEOUT") from None


def combine_step(repo: Path, scratch: Path, current: str, label: str):
    if label not in ALLOWED:
        raise RehearsalError("INVALID_SEQUENTIAL_STAGE")
    target = "refs/heads/rehearsal/" + label
    raw = temp_git(repo, "merge-tree", "--write-tree", "--name-only",
                   "--no-messages", current, target)
    parsed = parse_merge_output(raw.returncode, raw.stdout)
    conflicts = tuple(parsed.conflicted_paths)
    unknown = set(conflicts) - ALLOWED[label]
    if unknown:
        for path in sorted(unknown):
            print("SEQUENTIAL_UNEXPECTED_CONFLICT_PATH=" + path)
        raise RehearsalError("UNAPPROVED_SEQUENTIAL_CONFLICT")
    print("SEQUENTIAL_STAGE=" + label + " CONFLICT_COUNT=" + str(len(conflicts)))
    for path in conflicts:
        print("SEQUENTIAL_CONFLICT_RESOLVED_FROM_REVIEW=" + label + ":" + path)
    proposed = raw.stdout.splitlines()[0]
    if conflicts:
        index = scratch / ("index-" + label)
        require_ok(temp_git(repo, "read-tree", proposed, index=index),
                   "TEMP_READ_TREE_FAILED")
        for path in conflicts:
            reviewed = require_ok(
                temp_git(repo, "rev-parse", "--verify",
                         "refs/heads/rehearsal/combined:" + path),
                "PINNED_RESOLUTION_FILE_MISSING",
            )
            require_ok(
                temp_git(repo, "update-index", "--add", "--cacheinfo",
                         "100644," + reviewed + "," + path, index=index),
                "TEMP_RESOLUTION_INDEX_FAILED",
            )
        proposed = require_ok(
            temp_git(repo, "write-tree", index=index),
            "TEMP_RESOLVED_TREE_INVALID",
        )

    # A synthetic local commit is necessary for the next true sequential
    # 3-way merge to see BOTH parent histories. Never update GitHub refs.
    new_commit = require_ok(
        temp_git(repo, "commit-tree", proposed, "-p", current,
                 "-p", target, "-m", "Synthetic " + label + " merge (DO NOT PUSH)"),
        "TEMP_COMMIT_TREE_FAILED",
    )
    return new_commit, proposed, conflicts


def compare_final(repo: Path, tree: str):
    count = 0
    for _, paths in CODE_PATHS.items():
        for path in paths:
            merged = require_ok(
                temp_git(repo, "rev-parse", "--verify", tree + ":" + path),
                "SEQUENTIAL_CODE_BLOB_MISSING",
            )
            expected = require_ok(
                temp_git(repo, "rev-parse", "--verify",
                         "refs/heads/rehearsal/combined:" + path),
                "REVIEWED_CODE_BLOB_MISSING",
            )
            if merged != expected:
                print("SEQUENTIAL_BLOB_MISMATCH_PATH=" + path)
                raise RehearsalError("SEQUENTIAL_CODE_DIVERGED")
            count += 1

    for path in MANAGED:
        merged = require_ok(
            temp_git(repo, "rev-parse", "--verify", tree + ":" + path),
            "SEQUENTIAL_RESOLVED_FILE_MISSING",
        )
        expected = require_ok(
            temp_git(repo, "rev-parse", "--verify",
                     "refs/heads/rehearsal/combined:" + path),
            "SEQUENTIAL_REVIEW_RESOLUTION_MISSING",
        )
        if merged != expected:
            print("SEQUENTIAL_MANAGED_MISMATCH_PATH=" + path)
            raise RehearsalError("SEQUENTIAL_MANAGED_FILE_DIVERGED")

    print("FOLIOSENTRY_SEQUENTIAL_REHEARSAL_MATCHED_CODE_BLOBS=" + str(count))
    print("FOLIOSENTRY_SEQUENTIAL_REHEARSAL_REVIEWED_FILES_MATCH=3")
    for path in INTEGRATION_FOLLOWUP:
        exists = temp_git(repo, "cat-file", "-e", tree + ":" + path)
        if exists.returncode == 1:
            print("SEQUENTIAL_FOLLOWUP_NOT_INCLUDED=" + path)
        elif exists.returncode != 0:
            raise RehearsalError("SEQUENTIAL_FOLLOWUP_CHECK_FAILED")


def run(source: Path):
    remote = preflight(source)
    print("FOLIOSENTRY_SEQUENTIAL_PREFLIGHT_READONLY_PASS")
    with tempfile.TemporaryDirectory(prefix="foliosentry-sequential-review-") as folder:
        scratch = Path(folder)
        repo = scratch / "bare.git"
        require_ok(temp_git(scratch, "init", "--bare", "--quiet", str(repo)),
                   "TEMP_BARE_REPO_INIT_FAILED")
        require_ok(temp_git(repo, "remote", "add", "origin", remote),
                   "TEMP_GITHUB_REMOTE_ADD_FAILED")
        specs = [
            "refs/heads/" + name + ":refs/heads/rehearsal/" + label
            for label, (name, _) in BRANCHES.items()
        ]
        require_ok(
            temp_git(repo, "fetch", "--quiet", "--no-tags",
                     "--no-recurse-submodules", "origin", *specs),
            "TEMP_PRIVATE_FETCH_FAILED",
        )
        validate_fetched_refs(repo)
        print("FOLIOSENTRY_SEQUENTIAL_PINNED_REFS_PASS")
        preserved = validate_code_blobs(repo)
        print("FOLIOSENTRY_SEQUENTIAL_SOURCE_CODE_BLOBS=" + str(preserved))
        current = "refs/heads/rehearsal/main"
        final_tree = ""
        for label in ORDER:
            current, final_tree, _ = combine_step(repo, scratch, current, label)
        compare_final(repo, final_tree)
        print("FOLIOSENTRY_SEQUENTIAL_NO_SOURCE_WORKTREE_MUTATION=YES")
        print("FOLIOSENTRY_SEQUENTIAL_NO_GITHUB_PUSH_OR_MERGE=YES")
        print("FOLIOSENTRY_SEQUENTIAL_REVIEW_COMPLETE_NOT_PRODUCTION_APPROVAL")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.preflight:
            preflight(Path.cwd())
            print("FOLIOSENTRY_SEQUENTIAL_PREFLIGHT_PASS_NO_FETCH")
        else:
            run(Path.cwd())
        return 0
    except RehearsalError as exc:
        print("FOLIOSENTRY_SEQUENTIAL_REHEARSAL_FAIL=" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
