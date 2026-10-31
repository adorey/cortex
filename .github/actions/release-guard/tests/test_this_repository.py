"""This repository's guard workflow: one run per release at a time (ADR-009 §3.5).

Read as text: the runner's Python has no YAML parser. Skipped where the action runs elsewhere.
"""

import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[3] / "workflows" / "release-guard.yml"


@unittest.skipUnless(WORKFLOW.is_file(), "not in the repository that calls the action")
class ThisRepositoryTests(unittest.TestCase):
    def test_two_runs_of_one_tag_never_run_together(self):
        # Two at once would each find no issue open yet, and open two.
        text = WORKFLOW.read_text(encoding="utf-8")
        block = re.search(r"(?m)^concurrency:\n((?:  .*\n)+)", text)
        self.assertIsNotNone(block, "no workflow-level concurrency")
        self.assertRegex(block.group(1), r"(?m)^  group: release guard \$\{\{ github\.event\.release\.tag_name \|\| inputs\.tag \}\}$")
        self.assertRegex(block.group(1), r"(?m)^  cancel-in-progress: false$")


if __name__ == "__main__":
    unittest.main()
