"""The overlay validator's behaviour, frozen — ADR-007 phase 2.

``fixtures/validator/expected.json`` holds what the Bash implementation of
``bin/validate-overlays.sh`` printed for every run of every case (see ``validator_harness.py``).
These tests replay it through the script — now a shim over the core — and through the core
directly, and check that it covers every verdict the validator can emit.
"""

import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests import validator_harness as harness  # noqa: E402

EXPECTED = json.loads(harness.EXPECTED.read_text(encoding="utf-8"))
ERRORS = {"MISSING_FIELD", "BASE_NOT_FOUND", "INVALID_SEMANTIC", "REPLACEMENT_OUTSIDE_WORKFLOWS",
          "PATH_MIRROR", "NON_OVERRIDABLE"}
WARNINGS = {"UNKNOWN_LAYER", "SCOPE_MISMATCH", "SECTIONS_UNTAGGED"}


def all_stdout_lines():
    return [line for runs in EXPECTED.values() for run in runs.values() for line in run["stdout"]]


class CaptureTests(unittest.TestCase):
    def test_every_case_was_captured(self):
        self.assertEqual(sorted(EXPECTED), harness.cases())
        for case in harness.cases():
            with self.subTest(case=case):
                self.assertEqual(sorted(EXPECTED[case]), sorted(harness.run_key(a) for a in harness.runs(case)))

    def test_every_verdict_is_covered(self):
        lines = all_stdout_lines()
        codes = {m.group(1) for line in lines for m in [re.match(r"^  ([A-Z_]+) — ", line)] if m}
        self.assertEqual(codes, ERRORS | WARNINGS)
        for mark in ("✓ ", "ℹ ", "✗ ", "⚠ "):
            with self.subTest(mark=mark):
                self.assertTrue(any(line.startswith(mark) for line in lines))


@unittest.skipIf(shutil.which("bash") is None, "bash not available")
class ScriptTests(unittest.TestCase):
    def test_the_script_reproduces_the_captured_outputs(self):
        for case in harness.cases():
            for args in harness.runs(case):
                with self.subTest(case=case, run=harness.run_key(args)):
                    self.assertEqual(harness.execute(case, args, harness.run_script), EXPECTED[case][harness.run_key(args)])


    def test_the_core_matches_the_script_on_a_large_project(self):
        # Many files, directories mixing files and subdirectories, nesting: the case where the
        # order files are listed in matters. The script and the core run on the same file
        # system, so their outputs must be identical even though that order is not predictable.
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = tmp / "host"
        (project / "cortex").mkdir(parents=True)
        for i in range(60):
            base = project / "cortex" / "agents" / "roles" / f"team{i}"
            base.mkdir(parents=True)
            (base / "lead.md").write_text("# base\n", encoding="utf-8")
            overlay = project / "agents" / "roles" / f"team{i}"
            overlay.mkdir(parents=True)
            (overlay / "lead.md").write_text(
                "<!-- OVERLAY\n     Base: cortex/agents/roles/team%d/lead.md\n     Scope: workspace\n"
                "     Semantic: additive\n-->\n\n## Rules%s\n" % (i, " (additive)" if i % 4 else ""), encoding="utf-8")
            if i % 3 == 0:
                (overlay / "notes.md").write_text("no header\n", encoding="utf-8")
        (project / "agents" / "roles" / "team7" / "deep").mkdir()
        (project / "agents" / "roles" / "team7" / "deep" / "z.md").write_text("x\n", encoding="utf-8")
        # Services, and more than one layer: the order of the roots and of the layers matters too.
        (project / "cortex" / "agents" / "workflows" / "eng").mkdir(parents=True)
        (project / "cortex" / "agents" / "workflows" / "eng" / "review.md").write_text("# base\n", encoding="utf-8")
        for service in ("svc-z", "svc-a", "apps/svc-m"):
            (project / service).mkdir(parents=True)
            (project / service / "project-overview.md").write_text("# s\n", encoding="utf-8")
            for layer, rel, base in (("workflows", "eng/review.md", "workflows/eng/review.md"),
                                     ("roles", "team3/lead.md", "roles/team3/lead.md")):
                path = project / service / "agents" / layer / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("<!-- OVERLAY\n     Base: cortex/agents/%s\n     Scope: service @%s\n"
                                "     Semantic: %s\n-->\n\n## Rules (additive)\n"
                                % (base, service, "replacement" if layer == "workflows" else "additive"), encoding="utf-8")
        for args in ([], ["--strict"]):
            with self.subTest(run=harness.run_key(args)):
                self.assertEqual(harness.run_core(project, args), harness.run_script(project, args))


class CoreTests(unittest.TestCase):
    """ADR-007 phase 2 — the port reproduces every captured output byte for byte."""

    def test_the_core_reproduces_the_captured_outputs(self):
        for case in harness.cases():
            for args in harness.runs(case):
                with self.subTest(case=case, run=harness.run_key(args)):
                    self.assertEqual(harness.execute(case, args, harness.run_core), EXPECTED[case][harness.run_key(args)])


if __name__ == "__main__":
    unittest.main()
