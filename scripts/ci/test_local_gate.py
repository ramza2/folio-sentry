"""Offline tests for SHA-pinned Linux/WSL2 Local CI; no network or package install."""
import io
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import local_gate as gate


class LocalGateTests(unittest.TestCase):
    def test_sha_and_linux_fcntl_guard_fail_before_git(self):
        with self.assertRaisesRegex(gate.GateError, "EXPECTED_SHA_REQUIRED"):
            gate.preflight(Path("/tmp/unknown"), "notsha", "offline", False)
        with patch.object(platform, "system", return_value="Windows"):
            with self.assertRaisesRegex(gate.GateError, "LINUX_WSL2"):
                gate.preflight(Path("/tmp/unknown"), "a" * 40, "offline", False)

    def test_full_install_must_be_explicit(self):
        with self.assertRaisesRegex(gate.GateError, "INSTALL_DEPS_FULL_ONLY"):
            gate.preflight(Path("/tmp/unknown"), "a" * 40, "offline", True)
        with self.assertRaisesRegex(gate.GateError, "FULL_REQUIRES_EXPLICIT_INSTALL_DEPS"):
            gate.preflight(Path("/tmp/unknown"), "a" * 40, "full", False)

    def test_pin_worktree_remote_and_cleanliness(self):
        root = Path("/tmp/folio-test-root")
        sha = "a" * 40

        def fake_git(_, *args):
            commands = {
                ("rev-parse", "--show-toplevel"): str(root),
                ("rev-parse", "HEAD"): sha,
                ("status", "--porcelain", "--untracked-files=no"): "",
                ("remote", "get-url", "origin"):
                    "git@github.com:ramza2/folio-sentry.git",
            }
            return commands[args]

        with patch.object(gate, "run_git", side_effect=fake_git), \
             patch.object(platform, "system", return_value="Linux"), \
             patch.object(sys, "version_info", (3, 12, 3)):
            gate.preflight(root, sha, "offline", False)

        def changed(_, *args):
            if args == ("status", "--porcelain", "--untracked-files=no"):
                return " M backend/app/main.py"
            return fake_git(_, *args)

        with patch.object(gate, "run_git", side_effect=changed), \
             patch.object(platform, "system", return_value="Linux"), \
             patch.object(sys, "version_info", (3, 12, 3)):
            with self.assertRaisesRegex(gate.GateError, "TRACKED_CHANGES"):
                gate.preflight(root, sha, "offline", False)

    def test_no_real_credentials_or_proxy_in_test_environment(self):
        with patch.dict(os.environ, {
            "KIS_APPKEY": "sensitive",
            "KIS_APPSECRET": "sensitive",
            "FOLIOSENTRY_DB_PASSWORD": "sensitive",
            "DATABASE_URL": "postgresql://secret",
            "GITHUB_TOKEN": "sensitive",
            "HTTP_PROXY": "https://some-proxy",
            "PATH": "/usr/bin",
        }):
            env = gate.isolated_env(Path("/tmp/synthetic"))
        for key in ("KIS_APPKEY", "KIS_APPSECRET", "GITHUB_TOKEN",
                    "DATABASE_URL", "HTTP_PROXY"):
            self.assertNotIn(key, env)
        self.assertEqual(env["FOLIOSENTRY_DB_HOST"], "127.0.0.1")
        self.assertEqual(env["FOLIOSENTRY_DB_PORT"], "1")
        self.assertEqual(env["PYTHONPATH"], "/tmp/synthetic/backend")
        self.assertNotEqual(env["FOLIOSENTRY_DB_PASSWORD"], "sensitive")

    def test_archive_rejects_path_traversal_and_links(self):
        def archive_members(members):
            with tempfile.TemporaryFile() as f:
                with tarfile.open(fileobj=f, mode="w") as t:
                    for member in members:
                        t.addfile(member, io.BytesIO(b"x" * member.size))
                f.seek(0)
                with tarfile.open(fileobj=f, mode="r") as t:
                    return gate.safe_members(t)
        safe = tarfile.TarInfo("backend/app/synthetic.py")
        safe.size = 1
        self.assertEqual(len(archive_members([safe])), 1)
        for name in ("../bad.py", "/absolute.txt", ".git/config"):
            dangerous = tarfile.TarInfo(name)
            dangerous.size = 1
            with self.assertRaises(gate.GateError):
                archive_members([dangerous])
        symlink = tarfile.TarInfo("backend/app/link")
        symlink.type = tarfile.SYMTYPE
        symlink.linkname = "../../secret"
        with self.assertRaises(gate.GateError):
            archive_members([symlink])

    def test_report_step_records_failure_without_echoing_output(self):
        with tempfile.TemporaryDirectory(prefix="folio-local-unit-") as tmp:
            root = Path(tmp)
            env = gate.isolated_env(root)
            ok = gate.run_step(
                "safe_synthetic", [sys.executable, "-c", "print('OK')"],
                root, env, root, 20,
            )
            self.assertEqual(ok["status"], "PASS")
            self.assertEqual(ok["exit_code"], 0)
            self.assertTrue((root / "safe_synthetic.log").is_file())
            bad = gate.run_step(
                "synthetic_fail", [sys.executable, "-c", "raise SystemExit(6)"],
                root, env, root, 20,
            )
            self.assertEqual(bad["status"], "FAIL")
            self.assertEqual(bad["exit_code"], 6)

    def test_no_implicit_package_install_or_prod_db(self):
        source = Path(gate.__file__).read_text(encoding="utf-8")
        self.assertIn('if not args.install_deps:', source)
        self.assertIn('"full"', source)
        self.assertIn('"postgresql_migration": "N/A_NOT_RUN"', source)
        self.assertIn('"github_hosted_actions": "N/A_NOT_RUN"', source)
        self.assertIn('"production_db": "NOT_TOUCHED"', source)
        self.assertNotIn('"docker",', source)
        self.assertNotIn('"compose",', source)
        self.assertNotIn('"workflow_dispatch"', source)
        self.assertNotIn('"push",', source)


if __name__ == "__main__":
    unittest.main()
