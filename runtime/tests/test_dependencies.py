"""The runtime never imports the ``cortex`` command — ADR-008 §3.6.

The runtime reads a project's ``cortex.toml`` with the core's grammar (``cortex_core.project``),
the one the command reads it with. It does not import the command's package: ADR-016 will have the
command drive the runtime over HTTP, and the two ship apart. The core's own direction tests, in
``core/tests/test_boundaries.py``, keep the core free of both.
"""

import ast
import unittest
from pathlib import Path

RUNTIME_PKG = Path(__file__).resolve().parents[1] / "cortex_runtime"


def imports_of(source: str, package: str):
    """The modules of ``package`` that ``source`` imports, in either form."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        else:
            continue
        found += [name for name in names if name.split(".")[0] == package]
    return found


class DependencyTests(unittest.TestCase):
    def test_the_runtime_never_imports_the_command(self):
        offenders = [
            f"{py.relative_to(RUNTIME_PKG.parent)} imports {name}"
            for py in sorted(RUNTIME_PKG.rglob("*.py"))
            for name in imports_of(py.read_text(encoding="utf-8"), "cortex_cli")
        ]
        self.assertEqual(offenders, [], "the runtime must not depend on the cortex command (ADR-008 §3.6):\n"
                         + "\n".join(offenders))

    def test_the_guard_can_fail(self):
        self.assertEqual(imports_of("import cortex_cli.sync\nfrom cortex_cli import store", "cortex_cli"),
                         ["cortex_cli.sync", "cortex_cli"])
        self.assertEqual(imports_of("from cortex_core import project\nfrom . import base", "cortex_cli"), [])


if __name__ == "__main__":
    unittest.main()
