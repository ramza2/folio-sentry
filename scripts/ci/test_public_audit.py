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
        flags = subject.scan_blob(b"-----BEGIN PRIVATE KEY-----\n")
        self.assertEqual(flags["private_key_header"], 1)
        flags = subject.scan_blob(b"ghp_" + b"x" * 35)
        self.assertEqual(flags["github_token"], 1)
        flags = subject.scan_blob(b"KIS_APPSECRET=aVeryRealLongSecret123")
        self.assertEqual(flags["credential_assignment"], 1)

    def test_placeholder_and_blank_are_not_real_secrets(self):
        for value in (b"KIS_APPSECRET=", b"KIS_APPSECRET=dummy-not-a-real-secret",
                      b"POSTGRES_PASSWORD=synthetic-password"):
            self.assertEqual(subject.scan_blob(value)["credential_assignment"], 0)

    def test_home_network_metadata_flagged(self):
        self.assertEqual(
            subject.scan_blob(b"the host ramzaminiserver is in README")[
                "operational_endpoint_exposure"], 1,
        )

    def test_hidden_secret_paths_flagged(self):
        self.assertTrue(subject.SENSITIVE_PATH.search(".env.production"))
        self.assertTrue(subject.SENSITIVE_PATH.search("keys/id_rsa"))
        self.assertFalse(subject.SENSITIVE_PATH.search(".env.example"))


if __name__ == "__main__":
    unittest.main()
