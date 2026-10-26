"""The pre-commit hook skips flagged files that a merge brings in unchanged, not the branch's own."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HOOK = Path(__file__).resolve().parents[1] / ".githooks/pre-commit"
FLAGGED = "docs/x_docs/some_plan.md"


def git(cwd, *args, check=True):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=check, capture_output=True, text=True)


def hook(cwd):
    return subprocess.run(["sh", str(HOOK)], cwd=cwd, capture_output=True, text=True).returncode


def write(cwd, rel, text):
    path = Path(cwd, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(cwd, "add", rel)


class PreCommitHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = self.tmp.name
        git(self.repo, "init", "-q", "-b", "dev")
        write(self.repo, "a.txt", "a")
        git(self.repo, "commit", "-qm", "base")
        git(self.repo, "checkout", "-qb", "feature")
        write(self.repo, "b.txt", "b")
        git(self.repo, "commit", "-qm", "feature")
        git(self.repo, "checkout", "-q", "dev")
        write(self.repo, FLAGGED, "from dev")
        git(self.repo, "commit", "-qm", "dev adds a plan")
        git(self.repo, "checkout", "-q", "feature")

    def merge(self):
        git(self.repo, "merge", "--no-commit", "--no-ff", "dev")

    def test_plain_commit_of_flagged_file_is_refused(self):
        write(self.repo, FLAGGED, "mine")
        self.assertEqual(hook(self.repo), 1)

    def test_merge_bringing_in_existing_flagged_file_passes(self):
        self.merge()
        self.assertEqual(hook(self.repo), 0)

    def test_merge_with_branch_added_flagged_file_is_refused(self):
        self.merge()
        write(self.repo, "docs/x_docs/other_plan.md", "mine")
        self.assertEqual(hook(self.repo), 1)

    def test_merge_with_branch_edit_of_merged_in_file_is_refused(self):
        self.merge()
        write(self.repo, FLAGGED, "edited by me")
        self.assertEqual(hook(self.repo), 1)


if __name__ == "__main__":
    unittest.main()
