"""This repository's workflows report every check on every pull request (ADR-009 §3.10).

A workflow that runs on pull requests has no ``paths`` filter, since a check GitHub never starts
stays pending, and runs on the merge group too, since the queue waits for every required check.
Read as text: the runner's Python has no YAML parser. Skipped where the action runs elsewhere.
"""

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[3] / "workflows"


def triggers(text):
    """The `on:` block of a workflow, as text."""
    match = re.search(r"(?ms)^on:\s*\n(.*?)(?=^\S)", text)
    return match.group(1) if match else ""


def event_block(block, event):
    """The filters of one event in an `on:` block — a push may keep its own."""
    match = re.search(rf"(?m)^  {event}:[^\n]*\n((?:    [^\n]*\n|[ \t]*\n)*)", block)
    return match.group(1) if match else ""


@unittest.skipUnless(WORKFLOWS.is_dir(), "not in the repository that calls the action")
class ThisRepositoryTests(unittest.TestCase):
    def pull_request_workflows(self):
        found = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            block = triggers(path.read_text(encoding="utf-8"))
            if re.search(r"(?m)^  pull_request:", block):
                found.append((path.name, block))
        return found

    def test_there_are_such_workflows(self):
        self.assertGreaterEqual(len(self.pull_request_workflows()), 7)

    def test_no_pull_request_workflow_has_a_paths_filter(self):
        for name, block in self.pull_request_workflows():
            for event in ("pull_request", "merge_group"):
                with self.subTest(workflow=name, event=event):
                    self.assertNotRegex(event_block(block, event), r"(?m)^\s+paths(-ignore)?:")

    def test_every_pull_request_workflow_runs_on_the_merge_group(self):
        for name, block in self.pull_request_workflows():
            with self.subTest(workflow=name):
                self.assertRegex(block, r"(?m)^  merge_group:")


if __name__ == "__main__":
    unittest.main()
