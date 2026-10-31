"""This repository's release jobs (ADR-009 §3.3, §3.4): a merge into main or a line releases, with
no paths filter; a run started by hand cuts a pre-release; and no workflow starts on a tag, so a
version tag pushed by hand releases nothing. A push names its branches: one filtered on paths
alone, or not at all, runs on tags too.

Read as text: the runner's Python has no YAML parser. Skipped where the action runs elsewhere.
"""

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[4] / ".github" / "workflows"


def triggers(text):
    match = re.search(r"(?ms)^on:\s*\n(.*?)(?=^\S)", text)
    return match.group(1) if match else ""


def event_block(block, event):
    match = re.search(rf"(?m)^  {event}:[^\n]*\n((?:    [^\n]*\n|[ \t]*\n)*)", block)
    return match.group(1) if match else None


def push_without_branches(text):
    """True when ``text`` runs on a push that names no branches, which runs on tags too. The forms
    read are `on: push`, `on: [push, …]` and a `push:` block; the block list `on:` / `- push` is not,
    since no workflow here writes it."""
    if re.search(r"(?m)^on:[ \t]*(push[ \t]*$|\[[^\]]*\bpush\b)", text):
        return True
    push = event_block(triggers(text), "push")
    return push is not None and not re.search(r"(?m)^\s+branches(-ignore)?:", push)


class PushTests(unittest.TestCase):
    def test_a_push_with_no_branches_is_found(self):
        cases = [
            ("on:\n  push:\n    paths:\n      - \"cli/**\"\n  pull_request:\n\njobs:\n", True),
            ("on:\n  push:\n  pull_request:\n\njobs:\n", True),
            ("on: push\n\njobs:\n", True),
            ("on: [push, pull_request]\n\njobs:\n", True),
            ("on:\n  push:\n    branches: [main]\n    paths: [\"cli/**\"]\n\njobs:\n", False),
            ("on:\n  push:\n    branches-ignore: [\"wip/**\"]\n\njobs:\n", False),
            ("on:\n  pull_request:\n\njobs:\n", False),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertIs(push_without_branches(text), expected)


@unittest.skipUnless((WORKFLOWS / "release.yml").is_file(), "not in the repository that calls the actions")
class ThisRepositoryTests(unittest.TestCase):
    def test_no_workflow_starts_on_a_tag(self):
        # A tag pushed by hand is a push of a tag, or a `create`. A publication is not: the guard
        # starts on `release: published`, and only it.
        for path in sorted(WORKFLOWS.glob("*.yml")):
            block = triggers(path.read_text(encoding="utf-8"))
            with self.subTest(workflow=path.name):
                self.assertNotRegex(block, r"(?m)^\s+tags(-ignore)?:")
                self.assertNotRegex(block, r"(?m)^  create:")
                release = event_block(block, "release")
                if release is not None:
                    self.assertEqual(path.name, "release-guard.yml")
                    self.assertIn("types: [published]", release)
                self.assertFalse(push_without_branches(path.read_text(encoding="utf-8")))

    def test_a_merge_into_main_or_a_line_releases_whatever_it_changes(self):
        block = triggers((WORKFLOWS / "release.yml").read_text(encoding="utf-8"))
        push = event_block(block, "push")
        self.assertIn('branches: [main, "[0-9]+.x"]', push)
        self.assertNotRegex(push, r"(?m)^\s+paths(-ignore)?:")

    def test_a_pre_release_is_cut_by_hand_with_its_version(self):
        dispatch = event_block(triggers((WORKFLOWS / "release.yml").read_text(encoding="utf-8")), "workflow_dispatch")
        self.assertRegex(dispatch, r"(?m)^\s+version:")

    def test_the_build_releases_nothing_itself(self):
        text = (WORKFLOWS / "binary.yml").read_text(encoding="utf-8")
        self.assertNotIn("gh release", text)
        self.assertIsNotNone(event_block(triggers(text), "workflow_call"))


if __name__ == "__main__":
    unittest.main()
