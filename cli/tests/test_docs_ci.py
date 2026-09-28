"""The CI lines the docs give — the migration guide's and extending-layers' — run as written.

They read the version ``cortex.toml`` pins, to install that binary: read wrong, the version is
empty, and ``install.sh`` installs the latest release instead, in silence (ADR-008 §9).
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
GUIDES = (DOCS / "migrating-to-the-binary.md", DOCS / "extending-layers.md")
PINS = {'version = "1.2.3"\ntheme = "h2g2"\n': "1.2.3",
        "version = '1.2.3'\ntheme = 'h2g2'\n": "1.2.3",
        '# version = "0.1.0"\n  version="1.2.3"   # the team pins it\n': "1.2.3",
        '\ufeffversion = "1.2.3"\ntheme = "h2g2"\n': "1.2.3",          # a byte order mark, as Notepad writes one
        'theme = "h2g2"\n': None}


def block(path, language):
    """The first ``language`` code block of ``path``'s CI section."""
    text = path.read_text(encoding="utf-8")
    section = text[text.index("CI"):]
    return re.search(rf"```{language}\n(.*?)```", section, re.S).group(1).splitlines()


class CiLinesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-docs-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_both_guides_give_the_same_lines(self):
        self.assertEqual(block(GUIDES[0], "bash")[:2], block(GUIDES[1], "bash")[:2])
        self.assertEqual(block(GUIDES[0], "powershell")[:3], block(GUIDES[1], "powershell")[:3])

    @unittest.skipIf(os.name == "nt" or not shutil.which("sh"), "a POSIX shell's lines")
    def test_the_shell_lines_read_the_pinned_version_or_stop(self):
        lines = "\n".join(block(GUIDES[0], "bash")[:2]) + '\necho "$version"\n'
        for toml, expected in PINS.items():
            with self.subTest(toml=toml):
                (self.tmp / "cortex.toml").write_text(toml, encoding="utf-8")
                proc = subprocess.run(["sh", "-c", lines], cwd=self.tmp, capture_output=True, text=True)
                if expected is None:
                    self.assertEqual(proc.returncode, 1)
                    self.assertIn("cortex.toml pins no version", proc.stderr)
                else:
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout.strip(), expected)

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "Windows PowerShell's lines")
    def test_the_powershell_lines_read_the_pinned_version_or_stop(self):
        lines = "\n".join(block(GUIDES[0], "powershell")[:3]) + "\nWrite-Output $version\n"
        for toml, expected in PINS.items():
            with self.subTest(toml=toml):
                (self.tmp / "cortex.toml").write_text(toml, encoding="utf-8")
                proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", lines],
                                      cwd=self.tmp, capture_output=True, text=True)
                if expected is None:
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn("cortex.toml pins no version", proc.stderr)
                else:
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
