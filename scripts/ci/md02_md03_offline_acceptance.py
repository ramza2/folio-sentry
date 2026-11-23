#!/usr/bin/env python3
"""MD-02/MD-03 hermetic integration acceptance; Python stdlib only.

Synthetic credentials, in-memory fake transport, temporary state directory.
No pytest, Docker, DB, network, account access, installed backend or KIS calls.
This validates selected contracts, NOT actual PostgreSQL migration or live API.
"""
from __future__ import annotations

import ast
from datetime import date, datetime, timezone
import json
from pathlib import Path
import socket
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if not (BACKEND / "app" / "kis_shared_state.py").is_file():
    raise SystemExit("MD02_MD03_OFFLINE_SOURCE_NOT_FOUND")
sys.path.insert(0, str(BACKEND))

from app import exchange_calendar, price_quality
from app.kis_readonly import (
    KR_DAILY_PATH, TOKEN_PATH, US_DAILY_PATH,
    KisCredentials, KisReadOnlyDailyProvider, KisReadOnlyError,
)
from app.kis_shared_state import (
    KisSharedState, KisSharedStateError, ISSUE_MARKER, STATE_FILE,
)
from app.market_data import InstrumentIdentity

NOW = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)
DAY = date(2026, 11, 19)
KR = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
US = InstrumentIdentity("US", "XNAS", "AAPL", "USD")
CREDS = KisCredentials("synthetic-only-not-real-key", "synthetic-only-not-real-secret")

KR_ROW = {
    "stck_bsop_date": "20261119", "stck_oprc": "70000",
    "stck_hgpr": "72000", "stck_lwpr": "69000",
    "stck_clpr": "71000", "acml_vol": "123456",
}
US_ROW = {
    "xymd": "20261119", "open": "250.12", "high": "254.34",
    "low": "249.90", "clos": "252.44", "tvol": "234567",
}


class Clock:
    def __init__(self):
        self.seconds = NOW.timestamp()

    def __call__(self):
        return self.seconds

    def move(self, seconds):
        self.seconds += seconds


class NoNetworkFakeKis:
    """Only 1 synthetic OAuth path, 2 synthetic quote paths; never external I/O."""
    def __init__(self, fail_quote=False):
        self.calls = []
        self.fail_quote = fail_quote

    def __call__(self, method, path, headers, params=None, body=None):
        self.calls.append((method, path))
        if method == "POST" and path == TOKEN_PATH:
            if not isinstance(body, dict) or body.get("appkey") != CREDS.appkey:
                raise AssertionError("SYNTHETIC_CREDENTIAL_MISMATCH")
            return {"access_token": "synthetic-opaque-token-12345", "expires_in": 86400}
        if method == "GET" and path in (KR_DAILY_PATH, US_DAILY_PATH):
            if headers.get("authorization") != "Bearer synthetic-opaque-token-12345":
                raise AssertionError("SYNTHETIC_AUTH_HEADER_MISSING")
            if self.fail_quote:
                raise RuntimeError("offline-fake-quote-failure")
            return {"rt_cd": "0", "output2": [KR_ROW if path == KR_DAILY_PATH else US_ROW]}
        raise AssertionError("UNEXPECTED_KIS_ENDPOINT_REQUEST")


class OfflineIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="folio-offline-md02-md03-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "state"
        self.directory.mkdir(mode=0o700)
        self.clock = Clock()
        self.fake = NoNetworkFakeKis()
        # Reject any accidental socket connection even if a default transport
        # is added to this test suite in the future.
        deny = patch.object(socket.socket, "connect",
                            side_effect=AssertionError("REAL_NETWORK_FORBIDDEN"))
        deny.start()
        self.addCleanup(deny.stop)

    def provider(self, *, enabled, issue, fake=None, restart=False):
        gate = KisSharedState(self.directory, clock=self.clock)
        return KisReadOnlyDailyProvider(
            CREDS, shared_state=gate, transport=fake or self.fake,
            live_enabled=enabled, allow_shared_token_issue=issue,
            utcnow=lambda: NOW,
        )

    def fetch(self, cli, instrument=KR):
        return cli.fetch_daily(instrument, DAY, DAY, "RAW")

    def test_default_offline_blocks_all_api_calls_and_token_state(self):
        with self.assertRaisesRegex(KisReadOnlyError, "KIS_LIVE_READ_DISABLED"):
            self.fetch(self.provider(enabled=False, issue=True))
        self.assertEqual(self.fake.calls, [])
        self.assertFalse((self.directory / STATE_FILE).exists())
        self.assertFalse((self.directory / ISSUE_MARKER).exists())

    def test_shared_state_token_issuance_default_denied(self):
        with self.assertRaisesRegex(
            KisSharedStateError, "KIS_SHARED_TOKEN_MISSING_ISSUE_DENIED"
        ):
            self.fetch(self.provider(enabled=True, issue=False))
        self.assertEqual(self.fake.calls, [])
        self.assertFalse((self.directory / ISSUE_MARKER).exists())

    def test_synthetic_token_reuse_kr_us_bars_stay_partial(self):
        kr_batch = self.fetch(self.provider(enabled=True, issue=True))
        self.assertEqual(kr_batch.availability, "UNFINALIZED")
        self.clock.move(1.3)
        us_batch = self.fetch(self.provider(enabled=True, issue=False), US)
        self.assertEqual(
            self.fake.calls,
            [("POST", TOKEN_PATH), ("GET", KR_DAILY_PATH), ("GET", US_DAILY_PATH)]
        )
        self.assertEqual(len(kr_batch.bars), 1)
        self.assertEqual(len(us_batch.bars), 1)
        for batch in (kr_batch, us_batch):
            self.assertFalse(batch.bars[0].is_final)
            self.assertIsNone(batch.bars[0].source_observed_at)
            accepted = price_quality.validate_batch(batch, now=NOW)
            self.assertEqual(len(accepted), 1)
            self.assertEqual(accepted[0].quality_status, "PARTIAL")
            self.assertFalse(accepted[0].is_final)
            self.assertIsNone(accepted[0].source_observed_at)
        self.assertFalse(price_quality.analysis_eligible(
            quality_status="VALID", is_final=True, source_observed_at=NOW
        ))
        self.assertEqual(
            stat.S_IMODE((self.directory / STATE_FILE).stat().st_mode), 0o600
        )
        self.assertEqual(
            stat.S_IMODE((self.directory / ISSUE_MARKER).stat().st_mode), 0o600
        )
        state = json.loads((self.directory / STATE_FILE).read_text())
        self.assertEqual(len(state["requests"]), 3)

    def test_cross_instance_rate_limit_prevents_immediate_get(self):
        self.fetch(self.provider(enabled=True, issue=True))
        with self.assertRaisesRegex(KisSharedStateError, "KIS_SHARED_QUOTE_RATE_LIMIT"):
            self.fetch(self.provider(enabled=True, issue=False))
        self.assertEqual(len(self.fake.calls), 2)
        self.clock.move(1.25)
        self.fetch(self.provider(enabled=True, issue=False))
        self.assertEqual(len(self.fake.calls), 3)

    def test_token_marker_protects_missing_json_against_new_issue(self):
        self.fetch(self.provider(enabled=True, issue=True))
        (self.directory / STATE_FILE).unlink()
        self.clock.move(2)
        with self.assertRaisesRegex(
            KisSharedStateError, "KIS_SHARED_STATE_LOST_AFTER_ISSUE"
        ):
            self.fetch(self.provider(enabled=True, issue=True))
        self.assertEqual(len(self.fake.calls), 2)

    def test_failed_synthetic_quote_is_charged_before_transport(self):
        bad = NoNetworkFakeKis(fail_quote=True)
        with self.assertRaisesRegex(KisSharedStateError, "KIS_SHARED_QUOTE_REQUEST_FAILED"):
            self.fetch(self.provider(enabled=True, issue=True, fake=bad))
        state = json.loads((self.directory / STATE_FILE).read_text())
        self.assertEqual(len(state["requests"]), 2)
        with self.assertRaisesRegex(KisSharedStateError, "KIS_SHARED_QUOTE_RATE_LIMIT"):
            self.fetch(self.provider(enabled=True, issue=False, fake=bad))
        self.assertEqual(len(bad.calls), 2)

    def test_unknown_calendar_day_and_holiday_not_inferred(self):
        with self.assertRaisesRegex(
            exchange_calendar.ExchangeCalendarError, "PRICE_SESSION_CALENDAR_UNVERIFIED"
        ):
            exchange_calendar.attested_session(KR, date(2026, 11, 20))
        with self.assertRaisesRegex(
            exchange_calendar.ExchangeCalendarError, "PRICE_EXCHANGE_CLOSED"
        ):
            exchange_calendar.attested_session(US, date(2026, 11, 26))
        kr_session = exchange_calendar.attested_session(KR, DAY)
        self.assertEqual((kr_session.opens_at.hour,
                          kr_session.closes_at.hour,
                          kr_session.closes_at.minute), (10, 16, 30))

    def test_price_storage_opt_in_and_atomic_savepoint_statically_protected(self):
        file = BACKEND / "app/price_repository.py"
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        fn = next(x for x in tree.body
                  if isinstance(x, ast.FunctionDef)
                  and x.name == "insert_unverified_daily_batch")
        defaults = dict(zip(
            [a.arg for a in fn.args.kwonlyargs],
            fn.args.kw_defaults,
        ))
        self.assertIsInstance(defaults["allow_write"], ast.Constant)
        self.assertIs(defaults["allow_write"].value, False)
        source = ast.get_source_segment(file.read_text(encoding="utf-8"), fn) or ""
        for required in (
            "if not allow_write:",
            "PRICE_BAR_WRITE_DISABLED",
            "with session.begin_nested():",
            ".on_conflict_do_nothing(",
            "PRICE_BAR_CONFLICT_NEEDS_REVIEW",
        ):
            self.assertIn(required, source)
        self.assertNotIn("session.commit(", source)

    def test_sql_migration_remains_additive_and_prevents_finality(self):
        migration = (BACKEND / "migrations/versions/20261120_pricebar01.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('down_revision = "20261119_portfolio01"', migration)
        for condition in (
            "sa.CheckConstraint(\"is_final = false\"",
            "sa.CheckConstraint(\"quality_status = 'PARTIAL'\"",
            "sa.CheckConstraint(\"source_observed_at IS NULL\"",
            "sa.UniqueConstraint(",
            'op.create_table(\n        "price_bar"',
        ):
            self.assertIn(condition, migration)
        self.assertNotIn("op.drop_table(", migration)
        self.assertNotIn("op.execute(", migration)

    def test_production_api_has_no_kis_price_storage_wiring(self):
        path = BACKEND / "app/main.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        for module in ("kis_shared_state", "kis_first_probe", "kis_readonly",
                       "price_repository", "price_models", "price_quality"):
            self.assertNotIn(module, imported)
        self.assertEqual(self.fake.calls, [])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OfflineIntegration)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if result.wasSuccessful():
        print("FOLIOSENTRY_MD02_MD03_STDLIB_OFFLINE_GATE_PASS")
    else:
        print("FOLIOSENTRY_MD02_MD03_STDLIB_OFFLINE_GATE_FAIL")
        sys.exit(1)
