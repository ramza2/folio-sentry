"""Fail-closed router regression tests: no GitHub network calls."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("impact.py")
spec = importlib.util.spec_from_file_location("folio_impact", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ImpactTests(unittest.TestCase):
    def assert_only(self, paths, *expected):
        self.assertEqual(mod.classify(paths), frozenset(expected))

    def test_docs_only_never_runs_six_heavy_jobs(self):
        self.assert_only(["docs/ROADMAP.md", "AGENTS.md", "README.md"])
        self.assert_only(["backend/docs/policy.md"])

    def test_audit_utility_only_uses_lightweight_gate(self):
        self.assert_only(["scripts/public-visibility-preflight.py"])

    def test_backend_market_quote_only(self):
        self.assert_only(["backend/app/kis_shared_state.py"], "backend")
        self.assert_only(["backend/tests/test_kis_readonly.py"], "backend")

    def test_price_and_auth_require_db_checks(self):
        self.assert_only(
            ["backend/app/price_repository.py", "backend/tests/test_price_quality.py"],
            "backend", "auth-db-migration",
        )
        self.assert_only(
            ["backend/migrations/versions/20261120_pricebar01.py"],
            "backend", "auth-db-migration",
        )
        self.assert_only(["backend/app/auth.py"], "backend", "auth-db-migration")

    def test_frontend_without_production_docker(self):
        self.assert_only(["frontend/src/App.tsx"], "frontend")
        self.assert_only(
            ["frontend/package-lock.json"],
            "frontend", "deploy01-production-config",
        )

    def test_compose_and_backup_routes(self):
        self.assert_only(["compose.yaml"], "compose-config")
        self.assert_only(
            ["compose.production.yml"],
            "compose-config", "deploy01-production-config",
            "deploy02-backup-e2e",
        )
        self.assert_only(
            ["scripts/backup-db.sh"],
            "deploy01-production-config", "deploy02-backup-e2e",
        )

    def test_unknown_ci_or_config_fails_to_full(self):
        for name in (".github/workflows/ci.yml", "scripts/ci/impact.py",
                     ".gitignore", "unknown.cfg", "../secrets"):
            self.assertEqual(mod.classify([name]), mod.ALL)

    def test_multiple_changes_union(self):
        self.assert_only(
            ["docs/ROADMAP.md", "backend/app/kis_readonly.py", "frontend/src/style.css"],
            "backend", "frontend",
        )

    def test_invalid_git_range_full_not_false_pass(self):
        for event, base, head in [
            ("push", "0"*40, "1"*40),
            ("pull_request", "not-a-sha", "1"*40),
            ("repository_dispatch", "1"*40, "2"*40),
            ("workflow_dispatch", "", ""),
        ]:
            chosen, _ = mod.selected_jobs(event, base, head)
            self.assertEqual(chosen, mod.ALL)

    def test_diff_failure_is_full(self):
        with patch.object(mod, "_files_for_commit_range", side_effect=OSError):
            chosen, reason = mod.selected_jobs("pull_request", "a"*40, "b"*40)
        self.assertEqual(chosen, mod.ALL)
        self.assertEqual(reason, "UNDETERMINED_FULL")


if __name__ == "__main__":
    unittest.main()
