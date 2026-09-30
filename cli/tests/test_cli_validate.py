"""``cortex validate`` — ADR-007's frozen outputs, replayed through the command (ADR-008 §3.8).

The golden fixtures are the core's (``core/tests/fixtures/validator``), captured from the script.
The command must reproduce them byte for byte, exit codes included — on every platform, paths
printed with ``/`` (§3.1), and from a checkout with CRLF line endings too. One line differs, on
purpose: the help names the command it was asked of.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the harness, not a package named tests
import cli_harness as harness  # noqa: E402

sys.path.insert(0, str(harness.CORE / "tests"))
import validator_harness as golden  # noqa: E402

import json  # noqa: E402

EXPECTED = json.loads(golden.EXPECTED.read_text(encoding="utf-8"))


def run_command(project, args):
    """The validator as a project runs it now: ``cortex validate`` in the project's root, which
    ``cortex.toml`` marks and whose ``cortex.local.toml`` names the spec — here the base the
    fixture laid out at ``cortex/``, as ``cortex sync --copy`` would have."""
    (project / "cortex.toml").write_text('version = "1.0.0"\ntheme = "h2g2"\n', encoding="utf-8")
    (project / "cortex.local.toml").write_text('spec = "cortex"\n', encoding="utf-8")
    proc = harness.run("validate", *args, cwd=project, env=harness.environment(LC_ALL="C"))
    return proc.returncode, proc.stdout, proc.stderr


def expected(case, args):
    captured = EXPECTED[case][golden.run_key(args)]
    rename = lambda lines: [line.replace("Usage: validate-overlays.sh", "Usage: cortex validate") for line in lines]
    return dict(captured, stdout=rename(captured["stdout"]), stderr=rename(captured["stderr"]))


class GoldenTests(unittest.TestCase):
    def test_the_command_reproduces_the_captured_outputs(self):
        for case in golden.cases():
            for args in golden.runs(case):
                with self.subTest(case=case, run=golden.run_key(args)):
                    self.assertEqual(golden.execute(case, args, run_command), expected(case, args))

    def test_a_crlf_checkout_gives_the_same_report(self):
        # What git checks out on Windows with core.autocrlf, the base's files and the project's alike.
        for case in golden.cases():
            for args in golden.runs(case):
                with self.subTest(case=case, run=golden.run_key(args)):
                    self.assertEqual(golden.execute(case, args, run_command, crlf=True), expected(case, args))

    def test_the_help_names_the_command(self):
        proc = harness.run("validate", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(proc.stdout.startswith(b"Usage: cortex validate [OPTIONS]\n"), proc.stdout)

    def test_the_top_level_help_lists_it(self):
        self.assertIn(b"  validate ", harness.run("--help").stdout)


if __name__ == "__main__":
    unittest.main()
