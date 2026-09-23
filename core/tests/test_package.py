"""The package imports from source, with nothing installed (ADR-007 §3.3)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class PackageTests(unittest.TestCase):
    def test_imports_from_source(self):
        import cortex_core

        self.assertTrue(cortex_core.__doc__)

    def test_declares_no_dependency(self):
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        self.assertIn("dependencies = []", pyproject.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
