"""The ``cortex`` command itself — its version, its help, its package (ADR-008 §3.1, §3.9)."""

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the harness, not a package named tests
import cli_harness as harness  # noqa: E402

sys.path.insert(0, str(harness.CLI))
from cortex_cli.version import VERSION  # noqa: E402

PACKAGE = harness.CLI / "cortex_cli"
# A release, or a build of no release: X.Y.Z, then a pre-release after a dash.
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


class VersionTests(unittest.TestCase):
    def test_version_prints_the_version_of_the_build(self):
        proc = harness.run("--version")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        expected = harness.EXPECTED_VERSION or (None if harness.BINARY else VERSION)
        if expected is not None:
            self.assertEqual(proc.stdout, f"cortex {expected}\n".encode())
        self.assertRegex(proc.stdout.decode().removeprefix("cortex ").strip(), VERSION_PATTERN)

    def test_short_option(self):
        self.assertEqual(harness.run("-V").stdout, harness.run("--version").stdout)

    def test_an_unknown_option_of_version_is_named(self):
        proc = harness.run("--version", "--bogus")
        self.assertEqual(proc.returncode, 2)
        self.assertIn(b"unknown option '--bogus'", proc.stderr)
        self.assertEqual(proc.stdout, b"")
        self.assertEqual(harness.run("--version", "--verbose", "--bogus").returncode, 2)
        verbose = harness.run("--version", "--verbose")
        self.assertEqual(verbose.returncode, 0, verbose.stderr)
        self.assertIn(b"known spec archives: ", verbose.stdout)
        for twice in (("-v", "--verbose"), ("--verbose", "--verbose")):
            proc = harness.run("--version", *twice)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.count(b"known spec archives: "), 1)

    def test_a_source_checkout_is_no_release(self):
        self.assertTrue(VERSION_PATTERN.match(VERSION), VERSION)

    @unittest.skipIf(harness.BINARY, "runs the source")
    def test_python_m_runs_with_nothing_but_core_and_cli_on_sys_path(self):
        # -S: no site-packages. The working directory is an empty one.
        with tempfile.TemporaryDirectory() as cwd:
            env = harness.environment(PYTHONPATH=os.pathsep.join([str(harness.CORE), str(harness.CLI)]))
            proc = subprocess.run([sys.executable, "-S", "-m", "cortex_cli", "--version"],
                                  cwd=cwd, env=env, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.startswith(b"cortex "), proc.stdout)


class HelpTests(unittest.TestCase):
    def test_help(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                proc = harness.run(flag)
                self.assertEqual(proc.returncode, 0)
                self.assertTrue(proc.stdout.startswith(b"Usage: cortex <command>"), proc.stdout)
                self.assertEqual(proc.stderr, b"")

    def test_no_command_is_a_bad_argument(self):
        proc = harness.run()
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertTrue(proc.stderr.startswith(b"Usage: cortex <command>"), proc.stderr)

    def test_an_unknown_command_is_named(self):
        proc = harness.run("frobnicate")
        self.assertEqual(proc.returncode, 2)
        self.assertIn(b"unknown command 'frobnicate'", proc.stderr)

    def test_lines_end_with_lf_on_every_platform(self):
        self.assertNotIn(b"\r\n", harness.run("--help").stdout)


@unittest.skipIf(os.name == "nt", "a symbolic link needs a privilege on Windows")
class WorkingDirectoryTests(unittest.TestCase):
    """The project root is the directory as the user's shell names it (paths.working_directory)."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp(prefix="cortex-cwd-")).resolve()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "real" / "cortex").mkdir(parents=True)
        (tmp / "link").symlink_to(tmp / "real", target_is_directory=True)
        self.tmp = tmp

    def project_root(self, pwd):
        env = harness.environment()
        if pwd is not None:
            env["PWD"] = pwd
        out = harness.run("validate", cwd=self.tmp / "link", env=env).stdout.decode()
        return next(line.split(":", 1)[1].strip() for line in out.splitlines() if "Project root:" in line)

    def test_through_a_link_the_shells_name_is_kept(self):
        self.assertEqual(self.project_root(str(self.tmp / "link")), str(self.tmp / "link"))

    def test_a_pwd_naming_another_directory_is_ignored(self):
        self.assertEqual(self.project_root(str(self.tmp)), str(self.tmp / "real"))

    def test_without_pwd_the_directory_is_resolved(self):
        # subprocess passes no PWD of its own: harness.run sets one only from cwd, and here the
        # environment is given, without it.
        env = harness.environment()
        out = subprocess.run(harness.command("validate"), cwd=self.tmp / "link", env=env, capture_output=True).stdout
        self.assertIn(f"Project root:  {self.tmp / 'real'}".encode(), out)


def absolute_imports(source):
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append(node.module.split(".")[0])
    return found


class PackageTests(unittest.TestCase):
    def test_the_command_imports_the_standard_library_and_the_core_only(self):
        # The binary embeds the interpreter, the core and this package — nothing else (§3.1).
        allowed = set(sys.stdlib_module_names) | {"cortex_core", "cortex_cli"}
        offenders = [
            f"{py.relative_to(PACKAGE.parent)}: {name}"
            for py in sorted(PACKAGE.rglob("*.py"))
            for name in absolute_imports(py.read_text(encoding="utf-8"))
            if name not in allowed
        ]
        self.assertEqual(offenders, [])

    def test_the_command_never_imports_the_runtime(self):
        # Driving the runtime is ADR-016's, over HTTP: never by importing it.
        offenders = [py.name for py in sorted(PACKAGE.rglob("*.py"))
                     if "cortex_runtime" in absolute_imports(py.read_text(encoding="utf-8"))]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
