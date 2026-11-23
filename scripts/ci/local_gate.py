#!/usr/bin/env python3
"""FolioSentry Local CI v1: SHA-pinned, disposable Linux/WSL2 test snapshot.

No GitHub Actions, production Docker/DB, live KIS API, account access, or
GitHub write. Only --mode full --install-deps permits pip/npm downloads.
Tests execute against git archive of HEAD, never against the source checkout.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

from merge_rehearsal import safe_remote

SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2]


class GateError(Exception):
    """Fixed error codes only: do not accidentally echo credentials."""


def run_git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, encoding="utf-8",
            timeout=35, check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired):
        raise GateError("GIT_UNAVAILABLE_OR_TIMEOUT") from None
    if result.returncode != 0:
        raise GateError("GIT_READ_FAILED")
    return result.stdout.strip()


def preflight(root: Path, expected_sha: str, mode: str, install_deps: bool) -> None:
    if not SHA.fullmatch(expected_sha):
        raise GateError("EXPECTED_SHA_REQUIRED_40_LOWERCASE_HEX")
    if platform.system() != "Linux" or sys.version_info < (3, 12):
        raise GateError("LINUX_WSL2_PYTHON312_REQUIRED")
    if install_deps and mode != "full":
        raise GateError("INSTALL_DEPS_FULL_ONLY")
    if mode == "full" and not install_deps:
        raise GateError("FULL_REQUIRES_EXPLICIT_INSTALL_DEPS")
    if Path(run_git(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise GateError("SCRIPT_MUST_RUN_FROM_REPOSITORY_ROOT")
    if run_git(root, "rev-parse", "HEAD") != expected_sha:
        raise GateError("SOURCE_SHA_MISMATCH")
    if run_git(root, "status", "--porcelain", "--untracked-files=no"):
        raise GateError("SOURCE_HAS_TRACKED_CHANGES")
    if not safe_remote(run_git(root, "remote", "get-url", "origin")):
        raise GateError("UNAPPROVED_GITHUB_ORIGIN")
    if not shutil.which("git"):
        raise GateError("GIT_MISSING")
    if mode == "full":
        if not shutil.which("node") or not shutil.which("npm"):
            raise GateError("NODE22_NPM_REQUIRED")
        try:
            node = subprocess.run(
                ["node", "--version"], capture_output=True, text=True,
                timeout=8, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise GateError("NODE_VERSION_UNAVAILABLE") from None
        match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", node.stdout.strip())
        if node.returncode != 0 or not match or (
            int(match.group(1)), int(match.group(2)), int(match.group(3))
        ) < (22, 17, 0):
            raise GateError("NODE_VERSION_MUST_BE_AT_LEAST_22_17")
    print("FOLIOSENTRY_LOCAL_CI_PREFLIGHT_PASS_SHA=" + expected_sha)


def safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    total = 0
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or not path.parts or any(
            part in ("..", ".git") for part in path.parts
        ) or not (member.isfile() or member.isdir()):
            raise GateError("ARCHIVE_UNSAFE_PATH_OR_TYPE")
        total += member.size
        if total > MAX_ARCHIVE_BYTES:
            raise GateError("ARCHIVE_TOO_LARGE")
    return members


def extract_pinned_tree(root: Path, sha: str, target: Path) -> None:
    archive_path = target.parent / "source.tar"
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar",
             "--output", str(archive_path), sha],
            capture_output=True, timeout=50, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise GateError("SOURCE_ARCHIVE_FAILED") from None
    if result.returncode != 0:
        raise GateError("SOURCE_ARCHIVE_FAILED")
    try:
        with tarfile.open(archive_path, "r") as archive:
            archive.extractall(target, members=safe_members(archive), filter="data")
    except (OSError, tarfile.TarError, ValueError):
        raise GateError("SOURCE_ARCHIVE_INVALID") from None
    archive_path.unlink(missing_ok=True)
    if not (target / "backend/app/kis_shared_state.py").is_file():
        raise GateError("PINNED_SOURCE_MISSING")
    if not (target / "frontend/package-lock.json").is_file():
        raise GateError("PINNED_FRONTEND_LOCK_MISSING")


def isolated_env(snapshot: Path) -> dict[str, str]:
    """No inherited provider credentials, database connection strings or proxies."""
    keep = {
        "PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
        "TMPDIR", "TERM", "SHELL", "USER", "LOGNAME",
        "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS",
    }
    env = {k: v for k, v in os.environ.items() if k in keep}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPATH"] = str(snapshot / "backend")
    # Any accidental DB connection uses an invalid local-only target.
    env["FOLIOSENTRY_DB_HOST"] = "127.0.0.1"
    env["FOLIOSENTRY_DB_PORT"] = "1"
    env["FOLIOSENTRY_DB_NAME"] = "folio_synthetic_ci"
    env["FOLIOSENTRY_DB_USER"] = "folio_synthetic_ci"
    env["FOLIOSENTRY_DB_PASSWORD"] = "synthetic-not-a-real-password"
    env["FOLIOSENTRY_ALLOW_HTTP_DEV"] = "true"
    return env


def run_step(name: str, argv: list[str], cwd: Path, env: dict[str, str],
             report_dir: Path, timeout: int) -> dict[str, object]:
    start = time.monotonic()
    try:
        result = subprocess.run(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            capture_output=True, timeout=timeout, check=False,
        )
        code = result.returncode
        stdout, stderr = result.stdout, result.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        code = 124
        stdout = getattr(exc, "stdout", b"") or b""
        stderr = getattr(exc, "stderr", b"") or b""
    if isinstance(stdout, str):
        stdout = stdout.encode("utf-8")
    if isinstance(stderr, str):
        stderr = stderr.encode("utf-8")
    # Local logs may contain test details; never upload or print them by default.
    log = report_dir / (name + ".log")
    log.write_bytes(stdout + b"\n--- stderr ---\n" + stderr)
    log.chmod(0o600)
    entry = {
        "name": name,
        "status": "PASS" if code == 0 else "FAIL",
        "exit_code": code,
        "seconds": round(time.monotonic() - start, 2),
    }
    print("FOLIOSENTRY_LOCAL_CI_STEP=" + name + " STATUS=" + entry["status"])
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--mode", choices=("offline", "full"), default="offline")
    parser.add_argument("--install-deps", action="store_true",
                        help="Explicitly permit pip/npm dependency downloads in temp snapshot")
    args = parser.parse_args(argv)
    try:
        preflight(ROOT, args.expected_sha, args.mode, args.install_deps)
        os.umask(0o077)
        output = Path.home() / "folio-sentry-local-ci-reports"
        output.mkdir(mode=0o700, parents=True, exist_ok=True)
        report_dir = output / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-" + args.expected_sha[:12]
        )
        report_dir.mkdir(mode=0o700, exist_ok=False)
        steps: list[dict[str, object]] = []
        try:
            with tempfile.TemporaryDirectory(prefix="foliosentry-local-ci-") as workspace:
                snapshot = Path(workspace) / "source"
                snapshot.mkdir()
                extract_pinned_tree(ROOT, args.expected_sha, snapshot)
                env = isolated_env(snapshot)
                python = sys.executable

                def step(name: str, command: list[str], cwd: Path,
                         timeout: int = 240) -> bool:
                    entry = run_step(name, command, cwd, env, report_dir, timeout)
                    steps.append(entry)
                    return entry["status"] == "PASS"

                if step("stdlib_contracts", [
                    python, "-B", "-m", "unittest", "discover",
                    "-s", "scripts/ci", "-p", "test_*.py",
                ], snapshot):
                    if step("kis_synthetic", [
                        python, "-I", "-B", "scripts/ci/md02_md03_offline_acceptance.py",
                    ], snapshot):
                        if args.mode == "full":
                            if not args.install_deps:
                                raise GateError("FULL_REQUIRES_EXPLICIT_INSTALL_DEPS")
                            venv = Path(workspace) / "venv"
                            if not step("create_temp_venv", [
                                python, "-m", "venv", str(venv),
                            ], snapshot):
                                raise GateError("BACKEND_VENV_SETUP_FAILED")
                            vpython = str(venv / "bin/python")
                            if not step("install_backend_dependencies", [
                                vpython, "-m", "pip", "install", "-e", ".[dev]",
                            ], snapshot / "backend", 600):
                                raise GateError("BACKEND_INSTALL_FAILED")
                            if not step("backend_pytest", [
                                vpython, "-B", "-m", "pytest", "-q",
                            ], snapshot / "backend", 400):
                                raise GateError("BACKEND_PYTEST_FAILED")
                            if not step("backend_compile", [
                                vpython, "-B", "-m", "compileall", "-q", "app",
                            ], snapshot / "backend"):
                                raise GateError("BACKEND_COMPILE_FAILED")
                            if not step("frontend_npm_ci", [
                                "npm", "ci", "--no-audit", "--no-fund",
                            ], snapshot / "frontend", 600):
                                raise GateError("FRONTEND_INSTALL_FAILED")
                            for label, command in (
                                ("frontend_test", ["npm", "test"]),
                                ("frontend_typecheck", ["npm", "run", "typecheck"]),
                                ("frontend_build", ["npm", "run", "build"]),
                            ):
                                if not step(label, command, snapshot / "frontend", 400):
                                    raise GateError("FRONTEND_CHECK_FAILED")
                    else:
                        raise GateError("KIS_SYNTHETIC_FAILED")
                else:
                    raise GateError("STDLIB_CONTRACTS_FAILED")
            fail_code = None
        except GateError as exc:
            fail_code = str(exc)
        except Exception:
            # Do not leak installed package logs/paths into the console.
            fail_code = "LOCAL_CI_UNEXPECTED_ERROR"
        report = {
            "commit_sha": args.expected_sha,
            "mode": args.mode,
            "result": "PASS" if fail_code is None else "FAIL",
            "error_code": fail_code,
            "steps": steps,
            "postgresql_migration": "N/A_NOT_RUN",
            "github_hosted_actions": "N/A_NOT_RUN",
            "kis_live": "NOT_CALLED",
            "production_db": "NOT_TOUCHED",
        }
        report_path = report_dir / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        report_path.chmod(0o600)
        print("FOLIOSENTRY_LOCAL_CI_REPORT=" + str(report_path))
        if fail_code is not None:
            print("FOLIOSENTRY_LOCAL_CI_FAIL=" + fail_code, file=sys.stderr)
            return 2
        print("FOLIOSENTRY_LOCAL_CI_" + args.mode.upper() + "_PASS")
        print("FOLIOSENTRY_LOCAL_CI_NO_PRODUCTION_MUTATION=YES")
        return 0
    except GateError as exc:
        print("FOLIOSENTRY_LOCAL_CI_PREFLIGHT_FAIL=" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
