#!/usr/bin/env python3
"""MiniPC-only KIS secret setup. No network, database, Docker or API calls.

Usage:
    python3 scripts/kis-secret-setup.py setup
    python3 scripts/kis-secret-setup.py check

Keys are entered using getpass (terminal echo disabled). Never supply a key via
a CLI argument, environment variable, clipboard logging or shell history.
Only owner-owned 0700 directory and 0600 regular files are accepted.
"""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import stat
import sys


class SetupError(Exception):
    """A static status only; never interpolate sensitive input."""


FILE_NAMES = ("kis_appkey", "kis_appsecret")
SUCCESS = "FOLIOSENTRY_KIS_SECRET_SETUP_LOCAL_PASS_NO_NETWORK"
CHECK_SUCCESS = "FOLIOSENTRY_KIS_SECRET_METADATA_PASS_NO_CONTENT_READ_NO_NETWORK"


def _validate_dir(path: Path, *, create: bool, private: bool) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        if not create:
            raise SetupError("SECRET_DIRECTORY_MISSING") from None
        try:
            path.mkdir(mode=0o700)
            info = path.lstat()
        except OSError:
            raise SetupError("SECRET_DIRECTORY_UNAVAILABLE") from None
    except OSError:
        raise SetupError("SECRET_DIRECTORY_UNAVAILABLE") from None
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise SetupError("SECRET_DIRECTORY_UNSAFE")
    if private and (stat.S_IMODE(info.st_mode) != 0o700):
        raise SetupError("SECRET_DIRECTORY_PERMISSIONS")


def _paths(*, create: bool = False) -> tuple[Path, Path]:
    if os.geteuid() == 0:
        raise SetupError("REFUSE_ROOT")
    root = Path.home() / ".config"
    _validate_dir(root, create=create, private=False)
    private = root / "folio-sentry"
    _validate_dir(private, create=create, private=True)
    return tuple(private / name for name in FILE_NAMES)


def _check_file(path: Path) -> None:
    try:
        info = path.lstat()  # metadata only; never open secret contents
    except FileNotFoundError:
        raise SetupError("SECRET_FILE_MISSING") from None
    except OSError:
        raise SetupError("SECRET_FILE_UNAVAILABLE") from None
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
        raise SetupError("SECRET_FILE_UNSAFE")
    if stat.S_IMODE(info.st_mode) != 0o600 or not 1 <= info.st_size <= 256:
        raise SetupError("SECRET_FILE_PERMISSIONS_OR_SIZE")


def check() -> None:
    for path in _paths():
        _check_file(path)


def _validate_value(value: str) -> None:
    # Match MD-02 KisCredentials invariants without printing the value.
    if not isinstance(value, str) or not 1 <= len(value) <= 256 \
            or value.strip() != value or any(ch.isspace() for ch in value):
        raise SetupError("SECRET_INPUT_INVALID")


def setup() -> None:
    paths = _paths(create=True)
    if any(path.is_symlink() or path.exists() for path in paths):
        raise SetupError("SECRET_FILES_ALREADY_EXIST_NO_OVERWRITE")
    if not sys.stdin.isatty():
        raise SetupError("INTERACTIVE_TTY_REQUIRED")

    # getpass prevents normal terminal echo; never print/repr contents.
    key = getpass.getpass("KIS production App Key (hidden input): ")
    secret = getpass.getpass("KIS production App Secret (hidden input): ")
    _validate_value(key)
    _validate_value(secret)

    created: list[Path] = []
    try:
        for path, content in zip(paths, (key, secret)):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            created.append(path)
            try:
                data = content.encode("utf-8")
                with os.fdopen(fd, "wb") as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
            except Exception:
                raise
        check()
    except Exception:
        # Clean up only paths created in this invocation; never touch existing.
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        raise SetupError("SECRET_WRITE_FAILED") from None


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KIS key setup (local hidden terminal input) or metadata check"
    )
    parser.add_argument("action", choices=("setup", "check"))
    args = parser.parse_args(argv)
    old_umask = os.umask(0o077)
    try:
        if args.action == "setup":
            setup()
            print(SUCCESS)
        else:
            check()
            print(CHECK_SUCCESS)
        return 0
    except SetupError as error:
        print(f"FOLIOSENTRY_KIS_SECRET_STATUS={error}", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("FOLIOSENTRY_KIS_SECRET_STATUS=INPUT_CANCELLED", file=sys.stderr)
        return 2
    except Exception:
        print("FOLIOSENTRY_KIS_SECRET_STATUS=UNEXPECTED_FAILURE", file=sys.stderr)
        return 2
    finally:
        os.umask(old_umask)


if __name__ == "__main__":
    raise SystemExit(run())
