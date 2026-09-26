"""``bin/validate-overlays.sh`` without a usable Python — ADR-007 §3.5.

The shim must stop before running anything and say what is missing, with exit code 2: never a
``command not found``, never a traceback from a Python too old for the core.
"""

import os
import shutil
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "bin" / "validate-overlays.sh"


@unittest.skipIf(shutil.which("bash") is None, "bash not available")
class ShimWithoutPythonTests(unittest.TestCase):
    def run_with_path(self, extra):
        """Run the shim with a PATH holding only bash, dirname and ``extra`` executables."""
        tmp = Path(tempfile.mkdtemp(prefix="cortex-shim-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for tool in ("bash", "dirname"):
            os.symlink(shutil.which(tool), bin_dir / tool)
        for name, body in extra.items():
            fake = bin_dir / name
            fake.write_text(body, encoding="utf-8")
            fake.chmod(0o755)
        return subprocess.run([str(bin_dir / "bash"), str(SCRIPT), "--strict"],
                              capture_output=True, text=True, env={"PATH": str(bin_dir)})

    def assert_names_the_requirement(self, proc):
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Python 3.9 or later", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_no_python_at_all(self):
        self.assert_names_the_requirement(self.run_with_path({}))

    def test_a_python_too_old(self):
        # Answers the version probe the way Python 3.8 would: it runs the -c code, which exits 1.
        old = "#!/bin/bash\nfor a; do [ \"$a\" = -c ] && exit 1; done\necho 'Python 3.8.18'\n"
        self.assert_names_the_requirement(self.run_with_path({"python3": old, "python": old}))

    def test_a_python_2(self):
        # Python 2 rejects -I (exit status 2), and without it runs the probe, which exits 1.
        py2 = ("#!/bin/bash\n[ \"$1\" = -I ] && { echo 'Unknown option: -I' >&2; exit 2; }\n"
               "[ \"$1\" = -c ] && exit 1\nexit 0\n")
        self.assert_names_the_requirement(self.run_with_path({"python3": py2, "python": py2}))


@unittest.skipIf(shutil.which("bash") is None, "bash not available")
class ShimIsolationTests(unittest.TestCase):
    """Code from the project under validation never runs — the validator is run from its root."""

    def test_modules_in_the_working_directory_are_not_imported(self):
        from tests import validator_harness as harness

        tmp = Path(tempfile.mkdtemp(prefix="cortex-shim-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = harness.layout("ok-additive", tmp)
        marker = tmp / "executed"
        payload = f"open({str(marker)!r}, 'w').close()\n"
        # Standard modules the core imports, the package name itself, and sitecustomize,
        # which any Python started without -I imports from sys.path — the version probe included.
        for name in ("fnmatch.py", "re.py", "typing.py", "enum.py", "pathlib.py", "sitecustomize.py"):
            (project / name).write_text(payload, encoding="utf-8")
        (project / "cortex_core").mkdir()
        (project / "cortex_core" / "__init__.py").write_text(payload, encoding="utf-8")
        (project / "cortex_core" / "validate.py").write_text(payload, encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=str(project), PYTHONSTARTUP=str(project / "re.py"))

        code, out, _ = harness.run_script(project, [])
        proc = subprocess.run(["bash", str(project / "cortex" / "bin" / "validate-overlays.sh")],
                              capture_output=True, text=True, cwd=project, env=env)

        self.assertFalse(marker.exists(), "a module from the project under validation was executed")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("✓ agents/roles/engineering/lead-backend.md", proc.stdout)


@unittest.skipIf(shutil.which("bash") is None, "bash not available")
class ShimOptionsTests(unittest.TestCase):
    def test_the_roots_are_not_options(self):
        # The script knew --service, --strict and --help. A root given on the command line would
        # validate somewhere else — /nonexistent, found empty: a green run that checked nothing.
        from tests import validator_harness as harness

        tmp = Path(tempfile.mkdtemp(prefix="cortex-shim-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = harness.layout("ok-additive", tmp)
        for option in ("--project-root", "--base-root"):
            with self.subTest(option=option):
                code, out, err = harness.run_script(project, [option, "/nonexistent"])
                self.assertEqual(code, 2)
                self.assertTrue(err.startswith(f"Unknown argument: {option}\n".encode()), err[:80])
                self.assertEqual(out, b"")


@unittest.skipIf(shutil.which("bash") is None, "bash not available")
class ShimLocationTests(unittest.TestCase):
    """The shim finds the core next to itself, however it is called."""

    def project(self):
        from tests import validator_harness as harness

        tmp = Path(tempfile.mkdtemp(prefix="cortex-shim-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = harness.layout("ok-additive", tmp)
        harness.run_script(project, [])       # puts the shim and the core in place
        return tmp, project

    def run_shim(self, path, cwd, env=None):
        return subprocess.run(["bash", str(path)], capture_output=True, text=True, cwd=cwd, env=env)

    def test_with_cdpath_exported(self):
        # With CDPATH exported, cd looks there first — here, into a decoy cortex/bin — and prints
        # what it found, which the shim would have captured into the path.
        tmp, project = self.project()
        (tmp / "elsewhere" / "cortex" / "bin").mkdir(parents=True)
        env = dict(os.environ, CDPATH=f"{tmp / 'elsewhere'}:.")
        proc = self.run_shim(Path("cortex/bin/validate-overlays.sh"), project, env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("✓ agents/roles/engineering/lead-backend.md", proc.stdout)

    def test_through_a_symbolic_link(self):
        tmp, project = self.project()
        (tmp / "bin").mkdir()
        (tmp / "bin" / "validate-overlays").symlink_to(project / "cortex" / "bin" / "validate-overlays.sh")
        proc = self.run_shim(tmp / "bin" / "validate-overlays", tmp)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("✓ agents/roles/engineering/lead-backend.md", proc.stdout)

    def test_a_copy_away_from_the_checkout_says_so(self):
        tmp, project = self.project()
        (tmp / "bin").mkdir()
        shutil.copy(project / "cortex" / "bin" / "validate-overlays.sh", tmp / "bin" / "validate-overlays.sh")
        proc = self.run_shim(tmp / "bin" / "validate-overlays.sh", tmp)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cannot find cortex-core", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


@unittest.skipIf(shutil.which("bash") is None or not hasattr(signal, "SIGPIPE"), "bash or SIGPIPE not available")
class ShimPipeTests(unittest.TestCase):
    def test_a_reader_that_goes_away_ends_the_run_quietly(self):
        # validate-overlays.sh | head -1: the script died of SIGPIPE, in silence — no traceback.
        from tests import validator_harness as harness

        tmp = Path(tempfile.mkdtemp(prefix="cortex-shim-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        project = harness.layout("ok-additive", tmp)
        harness.run_script(project, [])       # puts the shim and the core in place
        proc = subprocess.Popen(["bash", str(project / "cortex" / "bin" / "validate-overlays.sh")],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.stdout.close()                   # gone before the first line is written
        err = proc.stderr.read()
        proc.stderr.close()
        proc.wait()
        self.assertNotIn(b"Traceback", err)
        self.assertEqual(proc.returncode, -signal.SIGPIPE)


if __name__ == "__main__":
    unittest.main()
