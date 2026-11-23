"""Combined CI + KIS draft review invariants; no network, Docker or DB.

These are narrow static checks to complement the existing offline behavior
and isolated PostgreSQL E2E. They are NOT hosted-GitHub CI verification.
"""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
BROWSER = ROOT / ".github/workflows/auth-browser.yml"
BACKEND = ROOT / "backend"


class CombinedCiKisContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_changes_job_runs_synthetic_transport_without_credential_file(self):
        self.assertIn(
            "PYTHONDONTWRITEBYTECODE=1 python3 -I -B "
            "scripts/ci/md02_md03_offline_acceptance.py",
            self.workflow,
        )
        self.assertIn("python3 -m unittest discover -s scripts/ci", self.workflow)
        probe = (ROOT / "scripts/ci/md02_md03_offline_acceptance.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('patch.object(socket.socket, "connect"', probe)
        self.assertIn("FOLIOSENTRY_MD02_MD03_STDLIB_OFFLINE_GATE_PASS", probe)
        self.assertNotIn("KisHttpsTransport()", probe)
        self.assertNotIn("KisCredentials.from_private_files(", probe)

    def test_md03_isolated_schema_ci_not_dropped(self):
        self.assertIn('md03_migration = Path("migrations/versions/20261120_pricebar01.py").is_file()', self.workflow)
        self.assertIn("assert md03_migration == md03_test", self.workflow)
        self.assertIn('required_tables.add("price_bar")', self.workflow)
        self.assertIn('"20261120_pricebar01"', self.workflow)
        self.assertIn("python scripts/test_price_bar_isolated_ci.py", self.workflow)
        self.assertIn("MD03_PARTIAL_INTEGRATION_BLOCKED", self.workflow)
        self.assertTrue((BACKEND / "migrations/versions/20261120_pricebar01.py").is_file())
        self.assertTrue((BACKEND / "scripts/test_price_bar_isolated_ci.py").is_file())

    def test_operating_api_stays_unconnected_to_live_kis_and_price_storage(self):
        api = BACKEND / "app/main.py"
        tree = ast.parse(api.read_text(encoding="utf-8"))
        names = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                names.update(part.name for part in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module)
                names.update(part.name for part in node.names)
        for denied in ("kis_first_probe", "kis_readonly", "kis_shared_state",
                       "price_repository", "price_quality", "price_models"):
            self.assertNotIn(denied, names)
        self.assertIn("app.include_router(portfolio_router)", api.read_text())

    def test_all_expensive_browser_checks_are_manual(self):
        browser = BROWSER.read_text(encoding="utf-8")
        header = browser.split("\njobs:\n", 1)[0]
        self.assertIn("on:\n  workflow_dispatch:", header)
        self.assertNotIn("\n  push:", header)
        self.assertNotIn("\n  pull_request:", header)
        self.assertIn("cancel-in-progress: true", header)


if __name__ == "__main__":
    unittest.main()
