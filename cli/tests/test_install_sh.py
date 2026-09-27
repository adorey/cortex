"""``install.sh`` — the one-line install on Linux and macOS (ADR-008 §3.2).

The script runs against a release served from this machine (``release_fixture``), with a ``PATH``
of the system's directories only: nothing of the user's ``~/.cortex`` or of another ``cortex``
reaches it unless a test puts it there.
"""

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the fixture, not a package named tests
from release_fixture import FakeRelease  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[2] / "install.sh"
SYSTEM_PATH = ["/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
SHELLS = [shell for shell in ("sh", "dash") if shutil.which(shell)]


def machine_target():
    machine = platform.machine().lower()
    if platform.system() == "Darwin":
        return "macos-arm64"
    return "linux-aarch64" if machine in ("aarch64", "arm64") else "linux-x86_64"


@unittest.skipIf(os.name == "nt" or not SHELLS, "a POSIX shell's script")
@unittest.skipIf(not (shutil.which("curl") or shutil.which("wget")), "needs curl or wget")
class InstallShTests(unittest.TestCase):
    def setUp(self):
        self.release = FakeRelease()
        self.addCleanup(self.release.close)
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-install-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.cortex_home = self.home / ".cortex"
        self.target = machine_target()

    def install(self, *args, shell="sh", first_on_path=(), stdin=False):
        env = {
            "HOME": str(self.home),
            "CORTEX_HOME": str(self.cortex_home),
            "CORTEX_RELEASES_URL": self.release.url,
            "PATH": os.pathsep.join([*map(str, first_on_path), *SYSTEM_PATH]),
        }
        if stdin:       # curl … | sh -s -- ARGS
            with open(SCRIPT, "rb") as script:
                return subprocess.run([shell, "-s", "--", *args], stdin=script, env=env, capture_output=True, text=True)
        return subprocess.run([shell, str(SCRIPT), *args], env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL)

    def installed(self, name="cortex"):
        return self.cortex_home / "bin" / name

    def fake_cortex(self):
        other = self.tmp / "other-tool"
        other.mkdir()
        fake = other / "cortex"
        fake.write_text("#!/bin/sh\necho 'another cortex'\n", encoding="utf-8")
        fake.chmod(0o755)
        return other

    def test_installs_the_latest_release_into_an_empty_cortex_home(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                shutil.rmtree(self.cortex_home, ignore_errors=True)
                proc = self.install(shell=shell)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertTrue(os.access(self.installed(), os.X_OK))
                self.assertEqual(subprocess.run([str(self.installed()), "--version"], capture_output=True,
                                                text=True).stdout, "cortex 9.9.9\n")
                self.assertIn("Installed cortex 9.9.9", proc.stdout)
                # Nothing left behind but the binary.
                self.assertEqual(sorted(p.name for p in self.cortex_home.iterdir()), ["bin"])

    def test_prints_the_path_line_and_edits_no_profile(self):
        proc = self.install()
        self.assertIn(f'export PATH="{self.cortex_home / "bin"}:$PATH"', proc.stdout)
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), [".cortex"])

    def test_says_nothing_about_path_when_the_directory_is_on_it(self):
        proc = self.install(first_on_path=[self.cortex_home / "bin"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("export PATH", proc.stdout)

    def test_installs_a_given_version(self):
        proc = self.install("9.9.8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("/download/9.9.8", proc.stdout)
        self.assertIn("Installed cortex 9.9.8", proc.stdout)

    def test_as_curl_pipes_it(self):
        proc = self.install("9.9.8", stdin=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Installed cortex 9.9.8", proc.stdout)

    def test_one_byte_altered_installs_nothing(self):
        self.release.alter_one_byte(self.target)
        proc = self.install()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("checksum mismatch", proc.stderr)
        self.assertFalse(self.installed().exists())
        self.assertFalse((self.cortex_home / "bin").exists())
        self.assertEqual(list(self.cortex_home.iterdir()), [])

    def test_an_asset_missing_from_sha256sums_installs_nothing(self):
        sums = self.release.root / "latest" / "download" / "SHA256SUMS"
        sums.write_text("".join(l for l in sums.read_text().splitlines(True) if self.target not in l))
        proc = self.install()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("lists no", proc.stderr)
        self.assertFalse(self.installed().exists())

    def test_another_cortex_first_on_path_installs_cortex_ai(self):
        other = self.fake_cortex()
        proc = self.install(first_on_path=[other])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"Another cortex command comes first on PATH: {other / 'cortex'}", proc.stdout)
        self.assertTrue(self.installed("cortex-ai").exists())
        self.assertFalse(self.installed("cortex").exists())

    def test_name_cortex_installs_cortex_anyway(self):
        proc = self.install("--name", "cortex", first_on_path=[self.fake_cortex()])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.installed("cortex").exists())
        self.assertFalse(self.installed("cortex-ai").exists())

    def test_its_own_cortex_first_on_path_is_no_other(self):
        self.install()
        proc = self.install(first_on_path=[self.cortex_home / "bin"])
        self.assertNotIn("Another cortex", proc.stdout)
        self.assertFalse(self.installed("cortex-ai").exists())

    def test_running_it_again_is_the_upgrade(self):
        self.install("9.9.8")
        proc = self.install()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(subprocess.run([str(self.installed()), "--version"], capture_output=True,
                                        text=True).stdout, "cortex 9.9.9\n")

    def test_a_download_cut_short_runs_nothing(self):
        # curl … | sh runs what arrived: a script cut anywhere before its last line must do nothing.
        script = SCRIPT.read_bytes()
        env = {"HOME": str(self.home), "CORTEX_HOME": str(self.cortex_home),
               "CORTEX_RELEASES_URL": self.release.url, "PATH": os.pathsep.join(SYSTEM_PATH)}
        for fraction in (0.3, 0.6, 0.9, 0.99):
            with self.subTest(fraction=fraction):
                cut = script[:int(len(script) * fraction)]
                subprocess.run(["sh", "-s"], input=cut, env=env, capture_output=True)
                self.assertFalse(self.cortex_home.exists())

    def test_bad_arguments(self):
        for args, message in ((["--frobnicate"], "unknown option"), (["latest"], "not a version"),
                              (["--name", "cx"], "--name is cortex or cortex-ai"), (["--name"], "needs a value")):
            with self.subTest(args=args):
                proc = self.install(*args)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(message, proc.stderr)
                self.assertFalse(self.cortex_home.exists())

    def test_a_release_that_does_not_exist(self):
        proc = self.install("1.2.3")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("could not download", proc.stderr)
        self.assertFalse(self.installed().exists())


if __name__ == "__main__":
    unittest.main()
