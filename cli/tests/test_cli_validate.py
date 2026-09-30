"""``cortex validate`` — ADR-007's frozen outputs, replayed through the command (ADR-008 §3.8).

The golden fixtures are the core's (``core/tests/fixtures/validator``), captured from the Bash
validator of Cortex 0.9.0. The command must reproduce them byte for byte, exit codes included —
on every platform, paths printed with ``/`` (§3.1), and from a checkout with CRLF line endings too.
"""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
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
    return EXPECTED[case][golden.run_key(args)]


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


class RootsTests(unittest.TestCase):
    def test_this_repository_validates_itself(self):
        # The base as its own project (ADR-007 §3.1): its agents/ is the base, never overlays of it.
        proc = harness.run("validate", "--strict", cwd=harness.REPO)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = proc.stdout.decode()
        repo = str(harness.REPO).replace(os.sep, "/")
        self.assertIn(f"Project root:  {repo}\n", out)
        self.assertIn(f"Cortex dir:    {repo}\n", out)
        self.assertNotIn("── Scope: . ──", out)
        self.assertNotIn("agents/roles/", out)

    def test_a_submodule_project_is_told_to_move(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validate-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "cortex" / "agents").mkdir(parents=True)
        proc = harness.run("validate", cwd=tmp)
        self.assertEqual(proc.returncode, 2)
        self.assertIn(b"no cortex.toml in", proc.stderr)
        self.assertIn(b"`cortex init` says how to leave it", proc.stderr)


class IsolationTests(unittest.TestCase):
    """Code from the project under validation never runs — the command runs in the project's root."""

    def test_modules_in_the_project_are_not_imported(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validate-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = golden.layout("ok-additive", tmp)
        marker = tmp / "executed"
        payload = f"open({str(marker)!r}, 'w').close()\n"
        # Standard modules the command imports, the packages' own names, and sitecustomize, which
        # a Python started without isolation imports from its path.
        for name in ("fnmatch.py", "re.py", "typing.py", "enum.py", "pathlib.py", "tomllib.py", "sitecustomize.py"):
            (project / name).write_text(payload, encoding="utf-8")
        for package in ("cortex_core", "cortex_cli"):
            (project / package).mkdir()
            (project / package / "__init__.py").write_text(payload, encoding="utf-8")
        env = harness.environment(PYTHONPATH=str(project), PYTHONSTARTUP=str(project / "re.py"))
        code, out, _ = run_command(project, [])
        proc = harness.run("validate", cwd=project, env=env)
        self.assertEqual((code, proc.returncode), (0, 0))
        self.assertIn(b"agents/roles/engineering/lead-backend.md", proc.stdout)
        self.assertFalse(marker.exists(), "a module of the project ran")


@unittest.skipIf(not hasattr(signal, "SIGPIPE"), "no SIGPIPE here")
class PipeTests(unittest.TestCase):
    def test_a_reader_that_goes_away_ends_the_run_quietly(self):
        # cortex validate | head -1: the run ends by SIGPIPE, in silence — no traceback.
        tmp = Path(tempfile.mkdtemp(prefix="cortex-validate-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = golden.layout("ok-additive", tmp)
        run_command(project, ["--help"])      # writes cortex.toml and cortex.local.toml
        proc = subprocess.Popen(harness.command("validate"), cwd=project, env=harness.environment(PWD=str(project)),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        proc.stdout.close()                   # gone before the first line is written
        err = proc.stderr.read()
        proc.stderr.close()
        proc.wait()
        self.assertNotIn(b"Traceback", err)
        self.assertEqual(proc.returncode, -signal.SIGPIPE)


if __name__ == "__main__":
    unittest.main()
