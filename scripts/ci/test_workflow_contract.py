"""Offline GitHub Actions workflow invariants (stdlib only).

Not a complete YAML parser and not a hosted Actions-runner PASS substitute.
Protect important workflow contracts during the monthly budget block.
"""
from __future__ import annotations

import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github/workflows/ci.yml"
BROWSER = ROOT / ".github/workflows/auth-browser.yml"
MD03_MIGRATION = ROOT / "backend/migrations/versions/20261120_pricebar01.py"
MD03_SCRIPT = ROOT / "backend/scripts/test_price_bar_isolated_ci.py"

ROUTED = (
    "backend", "frontend", "compose-config", "auth-db-migration",
    "deploy01-production-config", "deploy02-backup-e2e",
)


def jobs_and_text(ci: str) -> dict[str, str]:
    """Extract job-level two-space blocks; narrower than a YAML parser."""
    found = list(re.finditer(r"(?m)^  ([a-z][a-z0-9-]*):\s*$", ci))
    anchor = ci.find("\njobs:\n")
    if anchor < 0:
        raise AssertionError("MISSING_JOBS_MAPPING")
    starts = [m for m in found if m.start() > anchor]
    return {
        m.group(1): ci[m.start():starts[i + 1].start() if i+1 < len(starts) else len(ci)]
        for i, m in enumerate(starts)
    }


class WorkflowCostAndSafetyContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = CI.read_text(encoding="utf-8")
        cls.browser = BROWSER.read_text(encoding="utf-8")
        cls.jobs = jobs_and_text(cls.ci)

    def test_trigger_no_duplicate_feature_push(self):
        header = self.ci.split("\njobs:\n", 1)[0]
        self.assertIn(
            "on:\n  pull_request:\n    branches: [main]\n"
            "  push:\n    branches: [main]\n  workflow_dispatch:", header,
        )
        self.assertNotIn("feat/**", header)
        self.assertNotIn("docs/**", header)
        self.assertIn("cancel-in-progress: true", header)
        self.assertIn("permissions:\n  contents: read", header)

    def test_exact_routed_jobs_and_fail_closed_routing(self):
        self.assertEqual(set(self.jobs), {"changes", "ci-gate", *ROUTED})
        changes = self.jobs["changes"]
        self.assertIn("fetch-depth: 0", changes)
        self.assertIn("python3 -m unittest discover -s scripts/ci", changes)
        self.assertIn("python3 scripts/ci/impact.py", changes)
        self.assertIn("FOLIOSENTRY_CI_BASE:", changes)
        self.assertIn("FOLIOSENTRY_CI_HEAD:", changes)
        for job in ROUTED:
            output = (job + ": " + chr(36) + "{{ steps.route.outputs['"
                      + job + "'] }}")
            condition = ("if: " + chr(36) + "{{ needs.changes.outputs['"
                         + job + "'] == 'true' }}")
            self.assertIn(output, changes)
            block = self.jobs[job]
            self.assertIn("needs: changes", block)
            self.assertIn(condition, block)
            self.assertIn("runs-on: ubuntu-latest", block)
            self.assertIn("timeout-minutes:", block)

    def test_stable_gate_does_not_mask_failures(self):
        block = self.jobs["ci-gate"]
        self.assertIn("if: " + chr(36) + "{{ always() }}", block)
        for job in ("changes", *ROUTED):
            self.assertIn(job, block)
        self.assertIn("FOLIOSENTRY_CI_NEEDS: " + chr(36) + "{{ toJSON(needs) }}", block)
        self.assertIn("python3 scripts/ci/final_gate.py", block)

    def test_md03_migration_and_synthetic_sql_checks_cannot_be_lost(self):
        block = self.jobs["auth-db-migration"]
        for value in (
            "FOLIOSENTRY_DB_HOST: 127.0.0.1",
            "FOLIOSENTRY_DB_NAME: folio_ci",
            "FOLIOSENTRY_DB_USER: folio_ci",
            "image: postgres:17-alpine",
            "alembic upgrade head",
            'required_tables.add("price_bar")',
            '"20261119_portfolio01"',
            '"20261120_pricebar01"',
            "assert md03_migration == md03_test",
            "SELECT count(*) FROM price_bar",
            "MD03_PARTIAL_INTEGRATION_BLOCKED",
            "FOLIOSENTRY_MD03_ISOLATED_DB_TEST:",
            "python scripts/test_price_bar_isolated_ci.py",
            "FOLIOSENTRY_MD03_ISOLATED_SCHEMA_CI_PASS",
        ):
            self.assertIn(value, block)
        # A partial PR #26 merge must not silently leave untested schema.
        self.assertEqual(MD03_MIGRATION.is_file(), MD03_SCRIPT.is_file())
        code = block.split("          python - <<'PY'\n", 1)[1].split(
            "\n          PY\n", 1
        )[0]
        source = "\n".join(
            row[10:] if row.startswith("          ") else row
            for row in code.splitlines()
        ) + "\n"
        compile(source, "<offline-ci-migration-heredoc>", "exec")

    def test_existing_tests_and_guards_still_present(self):
        for job, check in (
            ("backend", "python -m pytest -q"),
            ("backend", "python -m compileall -q app"),
            ("frontend", "npm test"),
            ("frontend", "npm run typecheck"),
            ("frontend", "npm run build"),
            ("compose-config", "docker compose -f compose.yaml config -q"),
            ("deploy01-production-config", "FOLIOSENTRY_DEPLOY01_MUTATION_GUARDS_PASS"),
            ("deploy01-production-config", "docker build --file frontend/Dockerfile.prod"),
            ("deploy02-backup-e2e", "bash scripts/test-backup-ci.sh"),
        ):
            self.assertIn(check, self.jobs[job])

    def test_backup_ci_waits_for_real_sql_readiness(self):
        """pg_isready may pass before POSTGRES_DB exists in entrypoint init."""
        backup_ci = (ROOT / "scripts/test-backup-ci.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("GITHUB_ACTIONS_ONLY", backup_ci)
        self.assertIn('[[ "$health" == "healthy" ]]', backup_ci)
        self.assertIn('sql_ready=0', backup_ci)
        self.assertIn("-c 'SELECT 1' >/dev/null 2>&1", backup_ci)
        self.assertIn('[[ "$sql_ready" == 1 ]]', backup_ci)
        self.assertIn("FOLIOSENTRY_CI_DB_SQL_READY_PASS", backup_ci)
        self.assertLess(
            backup_ci.index("FOLIOSENTRY_CI_DB_SQL_READY_PASS"),
            backup_ci.index("CREATE TABLE public.alembic_version"),
        )

    def test_chromium_browser_acceptance_manual_only(self):
        header = self.browser.split("\njobs:\n", 1)[0]
        self.assertIn("on:\n  workflow_dispatch:", header)
        self.assertNotIn("\n  push:", header)
        self.assertNotIn("\n  pull_request:", header)
        self.assertIn("cancel-in-progress: true", header)


if __name__ == "__main__":
    unittest.main()
