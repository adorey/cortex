"""``bin/validate-overlays.sh`` without a usable Python — ADR-007 §3.5.

The shim must stop before running anything and say what is missing, with exit code 2: never a
``command not found``, never a traceback from a Python too old for the core.
"""

import os
import shutil
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
        # Answers the version probe the way Python 3.8 would: exit status 1.
        old = "#!/bin/bash\n[ \"$1\" = -c ] && exit 1\necho 'Python 3.8.18'\n"
        self.assert_names_the_requirement(self.run_with_path({"python3": old, "python": old}))


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
        # Standard modules the validator imports, and the package name itself.
        for name in ("fnmatch.py", "re.py", "typing.py"):
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


if __name__ == "__main__":
    unittest.main()
