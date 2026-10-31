"""The workflow this repository runs the gate from: on pull requests into main and its lines, and
on the merge group, where the queue checks the date at the moment of merging (ADR-009 §3.2).

Skipped where the action runs without it — moved to a repository of its own (ADR-009 §7).
"""

import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[4] / ".github" / "workflows" / "release-gate.yml"


@unittest.skipUnless(WORKFLOW.is_file(), "not in the repository that calls the action")
class ThisRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_it_runs_on_the_merge_group(self):
        self.assertRegex(self.text, r"(?m)^  merge_group:\s*$")

    def test_it_runs_on_pull_requests_into_main_and_its_lines(self):
        self.assertIn('branches: [main, "[0-9]+.x"]', self.text)

    def test_the_merge_group_gives_the_commits_and_the_branch(self):
        for name, field in (("base", "base_sha"), ("head", "head_sha"), ("base-ref", "base_ref")):
            with self.subTest(input=name):
                self.assertRegex(self.text, rf"(?m)^\s+{re.escape(name)}: .*github\.event\.merge_group\.{field}")


if __name__ == "__main__":
    unittest.main()
