"""The services of a workspace — found once, for the validator and for the prompt (#88)."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_core.workspace import service_index, services  # noqa: E402


class WorkspaceTests(unittest.TestCase):
    def workspace(self):
        root = Path(tempfile.mkdtemp(prefix="cortex-workspace-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        overviews = {
            "svc-b": "<!-- @alias: web -->\n\n# Web application\n",
            "svc-a": "<!-- @alias: api -->\n\n# Main API\n\nWhat it does.\n",
            "tools/batch": "# Nightly batch\n",                       # no alias: its folder names it
            "cortex/core/tests/fixtures/host": "# Cortex's own fixture\n",  # inside the base: not a service
            ".git/modules/old": "# a submodule's git dir\n",
        }
        for folder, text in overviews.items():
            (root / folder).mkdir(parents=True)
            (root / folder / "project-overview.md").write_text(text, encoding="utf-8")
        (root / "project-overview.md").write_text("# The workspace itself\n", encoding="utf-8")
        return root

    def test_services_are_the_folders_with_an_overview(self):
        root = self.workspace()
        self.assertEqual(sorted(Path(s).relative_to(root).as_posix() for s in services(str(root))),
                         ["svc-a", "svc-b", "tools/batch"])

    def test_the_index_names_each_service_and_marks_the_active_one(self):
        self.assertEqual(service_index(self.workspace(), active="svc-a"),
                         "- `@api` — `svc-a/` — Main API (active)\n"
                         "- `@web` — `svc-b/` — Web application\n"
                         "- `@batch` — `tools/batch/` — Nightly batch")

    def test_no_service_no_index(self):
        root = Path(tempfile.mkdtemp(prefix="cortex-workspace-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "project-overview.md").write_text("# Single project\n", encoding="utf-8")
        self.assertEqual(service_index(root), "")


if __name__ == "__main__":
    unittest.main()
