"""Stable final gate must reject failed required jobs and router failures."""
import contextlib
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

p = Path(__file__).with_name("final_gate.py")
spec = importlib.util.spec_from_file_location("folio_final_gate", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture(backend_enabled=False):
    return {
        "changes": {
            "result": "success",
            "outputs": {k: "true" if (k == "backend" and backend_enabled) else "false"
                        for k in mod.ROUTED},
        },
        **{k: {"result": "success" if (k == "backend" and backend_enabled)
                       else "skipped"} for k in mod.ROUTED},
    }


class GateTests(unittest.TestCase):
    def run_gate(self, data):
        output = StringIO()
        with patch.dict(os.environ, {"FOLIOSENTRY_CI_NEEDS": json.dumps(data)}):
            with contextlib.redirect_stdout(output):
                try:
                    mod.main()
                    return 0, output.getvalue()
                except SystemExit as err:
                    return err.code, output.getvalue()

    def test_docs_only_all_skipped_can_pass(self):
        self.assertEqual(self.run_gate(fixture())[0], 0)

    def test_backend_only_success_can_pass(self):
        self.assertEqual(self.run_gate(fixture(True))[0], 0)

    def test_failure_rejected(self):
        data = fixture(True)
        data["backend"]["result"] = "failure"
        self.assertNotEqual(self.run_gate(data)[0], 0)

    def test_unexpected_skips_rejected(self):
        data = fixture(True)
        data["backend"]["result"] = "skipped"
        self.assertNotEqual(self.run_gate(data)[0], 0)

    def test_router_failure_rejected(self):
        data = fixture()
        data["changes"]["result"] = "failure"
        self.assertNotEqual(self.run_gate(data)[0], 0)

    def test_corrupt_route_rejected(self):
        data = fixture()
        data["changes"]["outputs"]["backend"] = "maybe"
        self.assertNotEqual(self.run_gate(data)[0], 0)


if __name__ == "__main__":
    unittest.main()
