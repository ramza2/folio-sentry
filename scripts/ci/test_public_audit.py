"""Pre-public scanner tests use synthetic bytes only, no Git/network."""
from pathlib import Path
import importlib.util
import unittest

p = Path(__file__).parents[1] / "public-visibility-preflight.py"
spec = importlib.util.spec_from_file_location("prepublic", p)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


class PublicVisibilityAuditUnit(unittest.TestCase):
    def test_secret_tokens_detected_without_echo(self):
        flags = subject.scan_blob(b"-----BEGIN " + b"PRIVATE KEY-----\n")
        self.assertEqual(flags["private_key_header"], 1)
        flags = subject.scan_blob(b"ghp_" + b"x" * 35)
        self.assertEqual(flags["github_token"], 1)
        flags = subject.scan_blob(b"KIS_APPSECRET=" + b"aVeryRealLongSecret123")
        self.assertEqual(flags["credential_assignment"], 1)

    def test_placeholder_and_blank_are_not_real_secrets(self):
        for value in (b"KIS_APPSECRET=", b"KIS_APPSECRET=dummy-not-a-real-secret",
                      b"POSTGRES_PASSWORD=synthetic-password"):
            self.assertEqual(subject.scan_blob(value)["credential_assignment"], 0)

    def test_home_network_metadata_flagged(self):
        self.assertEqual(
            subject.scan_blob(b"the host ramza" + b"miniserver is in README")[
                "operational_endpoint_exposure"], 1,
        )


    def test_location_mode_uses_safe_path_allowlist_and_no_values(self):
        import inspect
        implementation = inspect.getsource(subject.locate_private_key_headers)
        self.assertIn("KEY_HEADER_VALUES_PRINTED=NO", implementation)
        self.assertIn("KEY_HEADER_BLOB_SHA=", implementation)
        self.assertNotIn("print(data)", implementation)
        self.assertNotIn("print(match.group", implementation)

    def test_operational_path_report_masks_matched_values(self):
        import contextlib
        from io import StringIO
        from unittest.mock import patch
        sha = "a" * 40
        content = b"example: ramzaminiserver / 192.168.10.104"
        def fake_git(*args, input_data=None):
            if args[:2] == ("rev-parse", "--is-shallow-repository"):
                return b"false\n"
            if args[:3] == ("rev-list", "--objects", "--all"):
                return (sha + " docs/ARCHITECTURE.md\n").encode()
            if args[:2] == ("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"):
                return (sha + f" blob {len(content)}\n").encode()
            if args[:2] == ("cat-file", "blob"):
                return content
            raise AssertionError("Unexpected Git request")
        out = StringIO()
        with patch.object(subject, "_git", side_effect=fake):
            with contextlib.redirect_stdout(out):
                subject.locate_operational_paths()
        report = out.getvalue()
        self.assertIn("FOLIOSENTRY_OPERATIONAL_PATH=docs/ARCHITECTURE.md VERSIONS=1", report)
        self.assertIn("FOLIOSENTRY_OPERATIONAL_VALUES_PRINTED=NO", report)
        self.assertNotIn("ramzaminiserver", report)
        self.assertNotIn("192.168.", report)

    def test_hidden_secret_paths_flagged(self):
        self.assertTrue(subject.SENSITIVE_PATH.search(".env.production"))
        self.assertTrue(subject.SENSITIVE_PATH.search("keys/id_rsa"))
        self.assertFalse(subject.SENSITIVE_PATH.search(".env.example"))


if __name__ == "__main__":
    unittest.main()
