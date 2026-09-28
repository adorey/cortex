"""``install.ps1`` — the one-line install on Windows (ADR-008 §3.2).

The script runs against a release served from this machine (``release_fixture``), under Windows
PowerShell 5.1 and PowerShell 7 when both are there. Its stand-in binary is a copy of
``doskey.exe``: a program Windows starts, and whose ``--version`` exits 0, which the script runs
once before installing it. What
is checked is what the script downloads, verifies, and installs under which name; the binary
workflow installs the real one.

The user's PATH is left alone (``CORTEX_NO_MODIFY_PATH``), but by the one test that checks it is
written, which runs in CI only and puts the value back.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the fixture, not a package named tests
from release_fixture import FakeRelease, failing_windows_program, stand_in  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[2] / "install.ps1"
SHELLS = [shell for shell in ("powershell", "pwsh") if os.name == "nt" and shutil.which(shell)]


@unittest.skipIf(not SHELLS, "Windows PowerShell's script")
class InstallPs1Tests(unittest.TestCase):
    def setUp(self):
        self.release = FakeRelease()
        self.addCleanup(self.release.close)
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-install-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.cortex_home = self.tmp / "home" / ".cortex"

    def powershell(self, command, shell="powershell", first_on_path=(), modify_path=False):
        env = dict(os.environ, CORTEX_HOME=str(self.cortex_home), CORTEX_RELEASES_URL=self.release.url)
        env.pop("CORTEX_NO_MODIFY_PATH", None)
        if not modify_path:
            env["CORTEX_NO_MODIFY_PATH"] = "1"
        env["PATH"] = os.pathsep.join([*map(str, first_on_path), env["PATH"]])
        return subprocess.run([shutil.which(shell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                               "-Command", command], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def install(self, *args, **kwargs):
        return self.powershell(f"& '{SCRIPT}' {' '.join(args)}; if (-not $?) {{ exit 1 }}", **kwargs)

    def installed(self, name="cortex"):
        return self.cortex_home / "bin" / f"{name}.exe"

    def fake_cortex(self):
        other = self.tmp / "other-tool"
        other.mkdir()
        (other / "cortex.cmd").write_text("@echo another cortex\r\n", encoding="ascii")
        return other

    def test_installs_the_latest_release_into_an_empty_cortex_home(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                shutil.rmtree(self.cortex_home, ignore_errors=True)
                proc = self.install(shell=shell)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(self.installed().read_bytes(), stand_in("9.9.9", windows=True))
                self.assertEqual(sorted(p.name for p in self.cortex_home.iterdir()), ["bin"])
                self.assertIn("is not on your PATH", proc.stdout)

    def test_piped_into_iex(self):
        proc = self.powershell(f"Get-Content -Raw '{SCRIPT}' | Invoke-Expression; if (-not $?) {{ exit 1 }}")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.installed().read_bytes(), stand_in("9.9.9", windows=True))

    def test_a_given_version_as_a_script_block(self):
        proc = self.powershell(f"& ([scriptblock]::Create((Get-Content -Raw '{SCRIPT}'))) -Version 9.9.8; if (-not $?) {{ exit 1 }}")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.installed().read_bytes(), stand_in("9.9.8", windows=True))

    def test_one_byte_altered_installs_nothing(self):
        self.release.alter_one_byte("windows-x86_64")
        for shell in SHELLS:
            with self.subTest(shell=shell):
                proc = self.install(shell=shell)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("checksum mismatch", proc.stderr)
                self.assertFalse(self.installed().exists())
                self.assertEqual(list(self.cortex_home.iterdir()), [])

    def test_another_cortex_first_on_path_installs_cortex_ai(self):
        proc = self.install(first_on_path=[self.fake_cortex()])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Another cortex command comes first on PATH", proc.stdout)
        self.assertTrue(self.installed("cortex-ai").exists())
        self.assertFalse(self.installed("cortex").exists())

    def test_name_cortex_installs_cortex_anyway(self):
        proc = self.install("-Name", "cortex", first_on_path=[self.fake_cortex()])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.installed("cortex").exists())
        self.assertFalse(self.installed("cortex-ai").exists())

    def test_running_it_again_is_the_upgrade(self):
        self.install("-Version", "9.9.8")
        proc = self.install()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.installed().read_bytes(), stand_in("9.9.9", windows=True))

    def test_a_file_windows_does_not_start_is_not_installed(self):
        from release_fixture import NOT_A_PROGRAM

        self.release.replace_windows_binary(NOT_A_PROGRAM)
        proc = self.install()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("does not run here", proc.stderr)
        self.assertFalse(self.installed().exists())

    def test_a_program_that_starts_and_fails_is_not_installed(self):
        # A DLL missing, the files of a onefile binary not unpacked: Windows starts it, it exits
        # with an error, and nothing may be installed.
        self.release.replace_windows_binary(failing_windows_program())
        proc = self.install()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("does not run here - it exited with code 1", " ".join(proc.stderr.split()))
        self.assertFalse(self.installed().exists())

    def test_a_redirect_off_https_is_refused(self):
        self.release.redirect("/latest/download/SHA256SUMS", f"{self.release.url}/download/9.9.9/SHA256SUMS")
        proc = self.install()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("which is not https", " ".join(proc.stderr.split()))     # PowerShell wraps its errors
        self.assertFalse(self.installed().exists())

    def test_a_user_part_or_a_port_that_is_no_number_is_refused(self):
        for url in ("http://127.0.0.1:1@example.invalid", "https://user@github.com/adorey/cortex/releases",
                    "http://localhost:x/releases", "http://127.0.0.1.example.com/releases"):
            with self.subTest(url=url):
                self.release.url, saved = url, self.release.url
                try:
                    proc = self.install()
                finally:
                    self.release.url = saved
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("CORTEX_RELEASES_URL must be https://", proc.stderr)
                self.assertFalse(self.cortex_home.exists())

    def test_a_junction_on_path_to_its_directory_is_no_other_cortex(self):
        self.install("-Version", "9.9.8")
        junction = self.tmp / "tools"
        made = self.powershell(f"New-Item -ItemType Junction -Path '{junction}' -Target '{self.cortex_home / 'bin'}'")
        self.assertEqual(made.returncode, 0, made.stderr)
        proc = self.install(first_on_path=[junction])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("another cortex", proc.stdout.lower())
        self.assertEqual(self.installed().read_bytes(), stand_in("9.9.9", windows=True))
        self.assertFalse(self.installed("cortex-ai").exists())

    def test_installed_as_cortex_it_keeps_its_name_under_another_cortex(self):
        other = self.fake_cortex()
        self.install("-Version", "9.9.8", "-Name", "cortex", first_on_path=[other])
        proc = self.install(first_on_path=[other])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.installed("cortex-ai").exists())
        self.assertEqual(self.installed().read_bytes(), stand_in("9.9.9", windows=True))
        self.assertIn("typing cortex runs it, not this one", proc.stdout)

    def test_plain_http_elsewhere_is_refused(self):
        for url in ("http://example.com/releases", "file:///C:/releases"):
            with self.subTest(url=url):
                self.release.url, saved = url, self.release.url
                try:
                    proc = self.install()
                finally:
                    self.release.url = saved
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("CORTEX_RELEASES_URL must be https://", proc.stderr)
                self.assertFalse(self.cortex_home.exists())

    def test_bad_arguments(self):
        for args, message in ((["-Version", "latest"], "not a version"), (["-Name", "cx"], "-Name is cortex or cortex-ai")):
            with self.subTest(args=args):
                proc = self.install(*args)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(message, proc.stderr)
                self.assertFalse(self.cortex_home.exists())

    @unittest.skipUnless(os.environ.get("CI") == "true", "writes the user's PATH: in CI only")
    def test_adds_the_directory_to_the_users_path_keeping_its_variables(self):
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS) as key:
            try:
                before = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                before = None
            # An entry that names a variable must come back as it was written, unexpanded.
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, r"%USERPROFILE%\cortex-test-tools")
            try:
                proc = self.install(modify_path=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                value, kind = winreg.QueryValueEx(key, "Path")
                self.assertEqual(kind, winreg.REG_EXPAND_SZ)
                self.assertEqual(value, rf"%USERPROFILE%\cortex-test-tools;{self.cortex_home / 'bin'}")
                again = self.install(modify_path=True)
                self.assertEqual(winreg.QueryValueEx(key, "Path")[0], value, again.stdout)
            finally:
                if before is None:
                    winreg.DeleteValue(key, "Path")
                else:
                    winreg.SetValueEx(key, "Path", 0, before[1], before[0])


if __name__ == "__main__":
    unittest.main()
