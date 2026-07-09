"""Tests for project-context binding / capability derivation — ADR-002 §8.1 (Nuance A)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.context import (  # noqa: E402
    capability_catalog,
    derive_capabilities,
    read_project_context,
)

ROOT = Path(__file__).resolve().parent / "fixtures" / "host"


class CapabilityCatalogTests(unittest.TestCase):
    def test_lists_base_capabilities(self):
        catalog = capability_catalog(ROOT)
        self.assertIn("languages/php.md", catalog)
        self.assertIn("languages/typescript.md", catalog)

    def test_excludes_readme(self):
        self.assertFalse(any(c.lower().endswith("readme.md") for c in capability_catalog(ROOT)))


class ReadProjectContextTests(unittest.TestCase):
    def test_reads_root_context(self):
        self.assertIn("PHP", read_project_context(ROOT))

    def test_empty_when_absent(self):
        # svc-a has project-overview.md, not project-context.md
        self.assertEqual(read_project_context(ROOT / "svc-a"), "")


class DeriveCapabilitiesTests(unittest.TestCase):
    def test_selects_only_mentioned_technos(self):
        # context mentions PHP, not typescript → php selected, ts excluded
        self.assertEqual(derive_capabilities(ROOT), ["languages/php.md"])

    def test_service_does_not_break_selection(self):
        # svc-a adds a php overlay (same rel path) and has no project-context of its own
        self.assertEqual(derive_capabilities(ROOT, service="svc-a"), ["languages/php.md"])

    def test_no_context_yields_empty(self):
        # a root with capabilities but no project-context.md → nothing derived
        self.assertEqual(derive_capabilities(ROOT / "svc-a"), [])


if __name__ == "__main__":
    unittest.main()
