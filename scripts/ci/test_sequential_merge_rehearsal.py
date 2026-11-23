"""Offline fail-closed tests for synthetic sequential Git merge (no network)."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import sequential_merge_rehearsal as seq
from merge_rehearsal import RehearsalError


class SequentialMergeContract(unittest.TestCase):
    def test_order_and_allowed_paths(self):
        self.assertEqual(seq.ORDER, ("ci", "pr24", "pr25", "pr26"))
        self.assertEqual(seq.ALLOWED["ci"], frozenset())
        self.assertEqual(seq.ALLOWED["pr24"], seq.DOCS)
        self.assertEqual(seq.ALLOWED["pr25"], seq.DOCS)
        self.assertEqual(seq.ALLOWED["pr26"],
                         seq.DOCS | frozenset((".github/workflows/ci.yml",)))
        self.assertEqual(len(seq.MANAGED), 3)

    def test_followup_tests_separated_from_independent_prs(self):
        self.assertIn("backend/tests/test_market_data_integration.py",
                      seq.INTEGRATION_FOLLOWUP)
        self.assertIn("scripts/ci/md02_md03_offline_acceptance.py",
                      seq.INTEGRATION_FOLLOWUP)
        self.assertIn("scripts/ci/test_ci_kis_combined_contract.py",
                      seq.INTEGRATION_FOLLOWUP)

    def test_script_only_uses_temporary_bare_repo_and_pinned_refs(self):
        body = Path(seq.__file__).read_text(encoding="utf-8")
        for required in (
            'tempfile.TemporaryDirectory(prefix="foliosentry-sequential-review-"',
            '"init", "--bare"',
            '"fetch", "--quiet", "--no-tags"',
            '"merge-tree", "--write-tree"',
            '"commit-tree", proposed',
            'validate_fetched_refs(repo)',
            'validate_code_blobs(repo)',
            "UNAPPROVED_SEQUENTIAL_CONFLICT",
            "NO_GITHUB_PUSH_OR_MERGE=YES",
            "NOT_PRODUCTION_APPROVAL",
        ):
            self.assertIn(required, body)
        for forbidden in ('"push"', '"checkout"', '"reset", "--hard"',
                          '"docker"', '"compose"', '"KIS_APPKEY"', '"alembic"'):
            self.assertNotIn(forbidden, body)

    def test_unexpected_conflict_fails_closed_before_any_resolution(self):
        from subprocess import CompletedProcess
        fake = CompletedProcess([], 1, "a" * 40 + "\nbackend/app/main.py\n", "")
        with patch.object(seq, "temp_git", return_value=fake):
            with self.assertRaisesRegex(RehearsalError,
                                        "UNAPPROVED_SEQUENTIAL_CONFLICT"):
                seq.combine_step(Path("/tmp/nonexistent"), Path("/tmp"),
                                 "fake", "pr26")

    def test_unknown_stage_rejected_without_commands(self):
        with self.assertRaisesRegex(RehearsalError, "INVALID_SEQUENTIAL_STAGE"):
            seq.combine_step(Path("/tmp/nonexistent"), Path("/tmp"),
                             "fake", "unapproved")

    def test_real_git_plumbing_only_in_disposable_synthetic_fixture(self):
        """A three-way textual conflict is resolved from pinned reviewed blobs."""
        def local(cwd, *args):
            r = subprocess.run(
                ["git", "-C", str(cwd), *args],
                capture_output=True, text=True, check=False, timeout=20,
            )
            self.assertEqual(r.returncode, 0, (args, r.stderr))
            return r.stdout.strip()

        with tempfile.TemporaryDirectory(prefix="folio-git-contract-") as tmp:
            root = Path(tmp)
            src = root / "source"
            src.mkdir()
            local(src, "init", "--quiet")
            local(src, "config", "user.name", "Synthetic")
            local(src, "config", "user.email", "synthetic@example.invalid")
            (src / "docs").mkdir()
            for name in ("AGENTS.md", "docs/ROADMAP.md"):
                (src / name).write_text("initial\n", encoding="utf-8")
            local(src, "add", ".")
            local(src, "commit", "-qm", "base")
            base = local(src, "rev-parse", "HEAD")
            for name, value in (("ci", "ci"), ("pr24", "pr24"),
                                ("combined", "reviewed")):
                local(src, "checkout", "-q", "-B", name, base)
                for path in ("AGENTS.md", "docs/ROADMAP.md"):
                    (src / path).write_text(value + "\n", encoding="utf-8")
                local(src, "commit", "-qam", name)
            bare = root / "bare.git"
            local(root, "clone", "--quiet", "--bare", str(src), str(bare))
            for name in ("ci", "pr24", "combined"):
                local(bare, "update-ref", "refs/heads/rehearsal/" + name,
                      local(bare, "rev-parse", "refs/heads/" + name))
            commit, tree, conflicts = seq.combine_step(
                bare, root, "refs/heads/rehearsal/ci", "pr24"
            )
            self.assertEqual(set(conflicts), seq.DOCS)
            for path in seq.DOCS:
                self.assertEqual(
                    local(bare, "rev-parse", tree + ":" + path),
                    local(bare, "rev-parse",
                          "refs/heads/rehearsal/combined:" + path),
                )
            self.assertEqual(len(local(bare, "rev-list", "--parents", "-n", "1",
                                       commit).split()), 3)


if __name__ == "__main__":
    unittest.main()
