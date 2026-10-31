"""The pattern this repository's workflow passes takes the examples its CONTRIBUTING.md gives.

Skipped where the action runs without them — moved to a repository of its own (ADR-009 §7).
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import commit_messages as cm  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = ROOT / ".github" / "workflows" / "commit-messages.yml"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"


def workflow_pattern():
    match = re.search(r"^\s*pattern: '(.*)'\s*$", WORKFLOW.read_text(encoding="utf-8"), re.M)
    return re.compile(match.group(1).replace("''", "'"))


def contributing_examples():
    """The messages of CONTRIBUTING's *Examples* block, a BREAKING CHANGE footer kept with its commit."""
    text = CONTRIBUTING.read_text(encoding="utf-8")
    block = re.search(r"^### Examples\s*\n+```\n(.*?)\n```", text, re.M | re.S).group(1)
    messages = []
    for line in block.split("\n"):
        if not line.strip():
            continue
        if messages and (line.startswith("BREAKING CHANGE:") or "\n\nBREAKING CHANGE:" in messages[-1]):
            messages[-1] += ("\n\n" if line.startswith("BREAKING CHANGE:") else "\n") + line
        else:
            messages.append(line)
    return messages


@unittest.skipUnless(WORKFLOW.is_file() and CONTRIBUTING.is_file(), "not in the repository that calls the action")
class ThisRepositoryTests(unittest.TestCase):
    def test_contributing_examples_pass(self):
        examples = contributing_examples()
        self.assertGreaterEqual(len(examples), 8)
        pattern = workflow_pattern()
        for message in examples:
            with self.subTest(message=message.split("\n")[0]):
                self.assertEqual(cm.check_message(message, pattern, 72), [])

    def test_the_format_line_of_contributing_does_not(self):
        # `<gitmoji> <type>(<scope>): <imperative subject>` is a template, not a commit.
        self.assertNotEqual(cm.check_message("<gitmoji> <type>(<scope>): <subject>", workflow_pattern(), 72), [])

    def test_adr_work_names_its_issue(self):
        self.assertEqual(cm.check_message("✨ feat(core): #42 resolve the cascade from a configurable base root",
                                          workflow_pattern(), 72), [])


if __name__ == "__main__":
    unittest.main()
