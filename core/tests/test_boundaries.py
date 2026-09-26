"""The two directions ADR-007 §3.3 forbids, enforced mechanically.

1. The core never imports the runtime — the runtime depends on the core, not the reverse.
2. The spec never references the core — the ADR-002 firewall, extended to the new package.
   (The runtime's own firewall test, ``runtime/tests/test_firewall.py``, keeps guarding its
   tokens; this one adds the core's without touching it.)
"""

import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CORE_PKG = Path(__file__).resolve().parents[1] / "cortex_core"
SPEC_DIR = Path(__file__).resolve().parents[2] / "agents"

FORBIDDEN_IN_SPEC = ["cortex_core", "from cortex_core", "import cortex_core"]


def runtime_imports(source: str):
    """Top-level module names imported by ``source`` that belong to the runtime."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        else:
            continue
        found += [n for n in names if n.split(".")[0] == "cortex_runtime"]
    return found


class DependencyDirectionTests(unittest.TestCase):
    def test_core_never_imports_the_runtime(self):
        offenders = [
            f"{py.relative_to(CORE_PKG.parent)} imports {name}"
            for py in sorted(CORE_PKG.rglob("*.py"))
            for name in runtime_imports(py.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [], "cortex-core must not depend on the runtime (ADR-007 §3.3):\n" + "\n".join(offenders))

    def test_the_guard_can_fail(self):
        # Proves the detector is not vacuous: both import forms are caught.
        self.assertEqual(runtime_imports("import cortex_runtime"), ["cortex_runtime"])
        self.assertEqual(runtime_imports("from cortex_runtime.resolver import x"), ["cortex_runtime.resolver"])
        self.assertEqual(runtime_imports("import cortex_core"), [])


class SpecFirewallTests(unittest.TestCase):
    def test_spec_does_not_reference_the_core(self):
        self.assertTrue(SPEC_DIR.is_dir(), f"spec dir not found: {SPEC_DIR}")
        offenders = [
            f"{md.relative_to(SPEC_DIR.parent)} :: '{token}'"
            for md in sorted(SPEC_DIR.rglob("*.md"))
            for token in FORBIDDEN_IN_SPEC
            if token in md.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [], "Spec Markdown must not depend on cortex-core (ADR-002 firewall):\n" + "\n".join(offenders))



class TestLayoutTests(unittest.TestCase):
    """The two suites share a repository, and IDE test explorers run them in one pytest session."""

    REPO = Path(__file__).resolve().parents[2]

    def test_core_and_runtime_test_modules_have_distinct_names(self):
        # Two packages named ``tests``: a module name found in both is collected once, the other
        # file silently never runs.
        core = {p.name for p in (self.REPO / "core" / "tests").glob("test_*.py")}
        runtime = {p.name for p in (self.REPO / "runtime" / "tests").glob("test_*.py")}
        self.assertEqual(core & runtime, set())

    def test_no_core_test_imports_the_tests_package_by_name(self):
        # ``tests`` is the runtime's package name too: in one pytest session, ``from tests import
        # validator_harness`` finds whichever was imported first.
        offenders = [
            f"{py.name}:{node.lineno}"
            for py in sorted((self.REPO / "core" / "tests").glob("*.py"))
            for node in ast.walk(ast.parse(py.read_text(encoding="utf-8")))
            if (isinstance(node, ast.ImportFrom) and node.level == 0 and (node.module or "").split(".")[0] == "tests")
            or (isinstance(node, ast.Import) and any(a.name.split(".")[0] == "tests" for a in node.names))
        ]
        self.assertEqual(offenders, [])

    def test_the_macos_job_runs_every_order_free_module(self):
        # The macOS job lists its modules by name: a new one must be listed there, or be named
        # here as depending on the order of an ext4 directory listing.
        order_dependent = {"test_validate", "test_validator_golden", "test_shim"}
        workflow = (self.REPO / ".github" / "workflows" / "core-tests.yml").read_text(encoding="utf-8")
        listed = set(re.findall(r"\btests\.(test_\w+)", workflow))
        present = {p.stem for p in (self.REPO / "core" / "tests").glob("test_*.py")}
        self.assertEqual(present - order_dependent, listed)


if __name__ == "__main__":
    unittest.main()
