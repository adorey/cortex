"""Cortex resolves itself — ADR-007 §3.1.

In the Cortex repository the base *is* the project root: ``agents/`` is both the shipped base
and the workspace tier. With ``base_root = project_root`` the two candidates are the same file,
which must be read once — never stacked onto itself.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_core.prompt import build_system_prompt  # noqa: E402
from cortex_core.resolver import find_role_relpath, read_resolved, resolve_layer  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
ROLE = REPO / "agents" / "roles" / "engineering" / "lead-backend.md"


class SelfHostingTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ROLE.is_file(), f"the self-hosting test needs {ROLE}")

    def test_the_file_is_resolved_once(self):
        self.assertEqual(
            resolve_layer("roles", "engineering/lead-backend.md", None, REPO, base_root=REPO),
            [ROLE],
        )

    def test_resolved_content_equals_the_file(self):
        self.assertEqual(
            read_resolved("roles", "engineering/lead-backend.md", None, REPO, base_root=REPO),
            ROLE.read_text(encoding="utf-8"),
        )

    def test_the_role_is_found_in_the_repository(self):
        self.assertEqual(find_role_relpath("lead-backend", REPO, base_root=REPO), "engineering/lead-backend.md")

    def test_the_assembled_prompt_carries_the_role_once(self):
        first_line = ROLE.read_text(encoding="utf-8").splitlines()[0]
        prompt = build_system_prompt("lead-backend", None, None, REPO, base_root=REPO)
        self.assertEqual(prompt.count(first_line), 1)


if __name__ == "__main__":
    unittest.main()
