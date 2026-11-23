"""Pure stdlib unit tests for the read-only merge rehearsal.

No GitHub, Docker, network, KIS, user files, database, or git fetch.
"""
from pathlib import Path
import re
import unittest

import merge_rehearsal as m


class MergeRehearsalContract(unittest.TestCase):
    def test_private_origin_exact_allowlist(self):
        accepted = (
            "git@github.com:ramza2/folio-sentry.git",
            "git@github.com:ramza2/folio-sentry",
            "ssh://git@github.com/ramza2/folio-sentry.git",
            "https://github.com/ramza2/folio-sentry.git",
            "https://github.com/ramza2/folio-sentry",
        )
        for url in accepted:
            with self.subTest(url=url):
                self.assertTrue(m.safe_remote(url))
        for url in (
            "https://github.com/another/folio-sentry.git",
            "https://example.com/ramza2/folio-sentry.git",
            "https://token@github.com/ramza2/folio-sentry.git",
            "git@evil.example:ramza2/folio-sentry.git",
            "file:///home/ramza/folio-sentry",
            "https://github.com/ramza2/folio-sentry.git/extra",
        ):
            with self.subTest(url=url):
                self.assertFalse(m.safe_remote(url))

    def test_all_refs_have_pinned_full_sha(self):
        self.assertEqual(
            set(m.BRANCHES), {"main", "ci", "pr24", "pr25", "pr26", "combined"}
        )
        for branch, sha in m.BRANCHES.values():
            self.assertTrue(branch)
            self.assertTrue(re.fullmatch("[0-9a-f]{40}", sha))

    def test_conflict_and_clean_merge_output_parsing(self):
        sha = "a" * 40
        self.assertEqual(m.parse_merge_output(0, sha + "\n").conflicted_paths, ())
        result = m.parse_merge_output(
            1, sha + "\nAGENTS.md\ndocs/ROADMAP.md\n"
        )
        self.assertEqual(result.conflicted_paths,
                         ("AGENTS.md", "docs/ROADMAP.md"))

    def test_invalid_or_unexpected_merge_result_denied(self):
        sha = "b" * 40
        for code, output in (
            (2, sha + "\n"), (0, sha + "\nAGENTS.md\n"),
            (1, sha + "\n"), (0, "bogus\n"),
            (1, sha + "\n\tunsafe\n"),
        ):
            with self.subTest(code=code, output=output):
                with self.assertRaises(m.RehearsalError):
                    m.parse_merge_output(code, output)

    def test_pairwise_analysis_does_not_claim_sequential_resolution(self):
        self.assertEqual(len(m.PAIRS), 7)
        self.assertIn(("main", "ci"), m.PAIRS)
        self.assertIn(("ci", "pr26"), m.PAIRS)
        self.assertIn(("pr24", "pr25"), m.PAIRS)
        self.assertEqual(sum(map(len, m.CODE_PATHS.values())), 23)
        script = Path(m.__file__).read_text(encoding="utf-8")
        self.assertIn("PAIRWISE_ONLY_NOT_SEQUENTIAL=YES", script)
        self.assertIn("REVIEW_COMPLETE_NOT_MERGE_APPROVAL", script)

    def test_git_mutations_are_temp_only_and_no_push(self):
        script = Path(m.__file__).read_text(encoding="utf-8")
        self.assertIn('tempfile.TemporaryDirectory(prefix="foliosentry-merge-rehearsal-"', script)
        self.assertIn('"init", "--bare", "--quiet"', script)
        self.assertIn('"fetch", "--quiet", "--no-tags"', script)
        self.assertIn('"merge-tree", "--write-tree"', script)
        self.assertNotIn('"push"', script)
        self.assertNotIn('"merge", "--no-commit"', script)
        self.assertNotIn('"checkout"', script)
        self.assertNotIn('"reset", "--hard"', script)


if __name__ == "__main__":
    unittest.main()
