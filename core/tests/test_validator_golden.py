"""The overlay validator's behaviour, frozen — ADR-007 phase 2.

``fixtures/validator/expected.json`` holds what the validator prints for every run of every case —
captured from its Bash implementation, then re-captured for ADR-007 phase 4 and ADR-008 (see
``validator_harness.py``). These tests replay it through the core, and check that it covers every
verdict the validator can emit. The cortex command replays it too (``cli/tests``).
"""

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the harness, not a package named tests
import validator_harness as harness  # noqa: E402

EXPECTED = json.loads(harness.EXPECTED.read_text(encoding="utf-8"))
ERRORS = {"MISSING_FIELD", "BASE_NOT_FOUND", "INVALID_SEMANTIC", "REPLACEMENT_OUTSIDE_WORKFLOWS",
          "PATH_MIRROR", "NON_OVERRIDABLE"}
WARNINGS = {"SCOPE_MISMATCH", "SECTIONS_UNTAGGED", "MISSING_HEADER"}


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


class CoreTests(unittest.TestCase):
    """ADR-007 phase 2 — the port reproduces every captured output byte for byte."""

    def test_the_core_reproduces_the_captured_outputs(self):
        for case in harness.cases():
            for args in harness.runs(case):
                with self.subTest(case=case, run=harness.run_key(args)):
                    self.assertEqual(harness.execute(case, args, harness.run_core), EXPECTED[case][harness.run_key(args)])

    def test_a_crlf_checkout_gives_the_same_report(self):
        # What git checks out on Windows with core.autocrlf — the base's files and the project's
        # alike — reads as the LF files it was committed as (ADR-008 §3.1).
        for case in harness.cases():
            for args in harness.runs(case):
                with self.subTest(case=case, run=harness.run_key(args)):
                    self.assertEqual(harness.execute(case, args, harness.run_core, crlf=True),
                                     EXPECTED[case][harness.run_key(args)])


if __name__ == "__main__":
    unittest.main()
