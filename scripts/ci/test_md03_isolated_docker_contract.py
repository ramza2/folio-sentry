"""Offline contract only; does not start Docker or connect to any database."""
from pathlib import Path
import unittest

SCRIPT = Path(__file__).with_name("run-md03-isolated-docker.sh")


class Md03IsolatedDockerContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_explicit_preflight_and_run_confirmation(self):
        s = self.source
        self.assertIn('--preflight)', s)
        self.assertIn('--run)', s)
        self.assertIn("APPROVE_MD03_EPHEMERAL_DOCKER_ONLY", s)
        self.assertIn('test ! -e "$ROOT/.git"', s)
        self.assertIn("TEMP_ARCHIVE_DIRECTORY_REQUIRED", s)

    def test_no_prod_compose_or_db_exec(self):
        s = self.source
        self.assertNotIn("docker compose ", s)
        self.assertNotIn("docker stop ", s)
        self.assertNotIn("docker exec " + '"$DB_LIST"', s)
        self.assertNotIn("docker exec " + '"$BACKEND_LIST"', s)
        self.assertIn("PRODUCTION_CONTAINERS_INSPECT_ONLY", s)
        self.assertIn("FOLIOSENTRY_DB_NAME=folio_ci", s)
        self.assertIn("FOLIOSENTRY_DB_USER=folio_ci", s)

    def test_new_pg_network_none_tmpfs_no_ports_and_pull_disabled(self):
        s = self.source
        self.assertIn('--network none', s)
        self.assertIn('--pull never', s)
        self.assertIn('--tmpfs /var/lib/postgresql/data', s)
        self.assertIn('--tmpfs /run/postgresql', s)
        self.assertIn('docker port "$PG_CID"', s)
        self.assertNotIn("--publish", s)
        self.assertNotIn("-p 5432", s)
        self.assertIn('docker rm -f -v "$PG_CID"', s)

    def test_new_python_joins_disposable_pg_only(self):
        s = self.source
        self.assertIn('--network "container:$PG_CID"', s)
        self.assertIn('--read-only', s)
        self.assertIn('--cap-drop ALL', s)
        self.assertIn('target=/workspace/backend,readonly', s)
        self.assertIn("FOLIOSENTRY_MD03_ISOLATED_DB_TEST=yes", s)
        self.assertIn("python -m alembic upgrade head", s)
        self.assertIn("python scripts/test_price_bar_isolated_ci.py", s)
        self.assertIn("FOLIOSENTRY_MD03_ISOLATED_POSTGRES_INTEGRATION_PASS", s)

    def test_no_key_read_or_network_download(self):
        s = self.source
        for banned in (
            "curl ", "wget ", "pip install", "git clone",
            "docker pull", "KIS_APPKEY_FILE", "KIS_APPSECRET_FILE",
            "docker cp ", "docker volume rm ", "docker volume prune ",
        ):
            self.assertNotIn(banned, s)


if __name__ == "__main__":
    unittest.main()
