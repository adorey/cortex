"""The capability catalog — ADR-007: moved from the runtime unchanged, then parameterised."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_core.catalog import capability_catalog, capability_dirs  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROOT = FIXTURES / "host"
# Captured from the runtime's context.capability_catalog before the move; svc-a then gained a
# capability of its own, languages/go.md, so that the service tier makes a difference.
GOLDEN = json.loads((FIXTURES / "golden" / "catalog.json").read_text(encoding="utf-8"))


class CatalogTests(unittest.TestCase):
    def test_workspace_catalog_is_unchanged(self):
        self.assertEqual(capability_catalog(ROOT), GOLDEN["workspace"])

    def test_service_catalog_is_unchanged(self):
        self.assertEqual(capability_catalog(ROOT, "svc-a"), GOLDEN["svc-a"])

    def test_readme_is_not_a_capability(self):
        self.assertFalse(any(c.lower().endswith("readme.md") for c in capability_catalog(ROOT)))

    def test_omitted_base_root_equals_explicit_default(self):
        self.assertEqual(capability_catalog(ROOT, "svc-a"), capability_catalog(ROOT, "svc-a", base_root=ROOT / "cortex"))

    def test_base_outside_the_project_tree(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-catalog-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copytree(ROOT / "cortex", tmp / "install")
        shutil.copytree(ROOT, tmp / "project", ignore=shutil.ignore_patterns("cortex"))
        self.assertEqual(capability_catalog(tmp / "project", "svc-a", base_root=tmp / "install"), GOLDEN["svc-a"])

    def test_a_base_that_is_the_project_root_is_listed_once(self):
        # ADR-007 §3.1: the base and the workspace tier coincide — one directory, not two.
        base = ROOT / "cortex"
        self.assertEqual(capability_dirs(base, "svc-a", base_root=base),
                         [base / "agents" / "capabilities", base / "svc-a" / "agents" / "capabilities"])


if __name__ == "__main__":
    unittest.main()
