"""What a change touches, and the globs that say whether it concerns a workflow's jobs."""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import changes  # noqa: E402


class GlobTests(unittest.TestCase):
    def test_globs(self):
        cases = [
            ("cli/**", "cli/cortex_cli/store.py", True),
            ("cli/**", "cli", False),
            ("cli/**", "clipboard/x", False),
            ("install.sh", "install.sh", True),
            ("install.sh", "docs/install.sh", False),
            ("docs/*.md", "docs/getting-started.md", True),
            ("docs/*.md", "docs/adr/ADR-001.md", False),
            ("**/*.md", "README.md", True),
            ("**/*.md", "docs/adr/ADR-001.md", True),
            (".github/workflows/cli-tests.yml", ".github/workflows/cli-tests.yml", True),
            ("cli/tests/**", "cli/tests/fixtures/a/b.json", True),
            ("v?.txt", "v1.txt", True),
            ("v?.txt", "v10.txt", False),
        ]
        for pattern, path, expected in cases:
            with self.subTest(pattern=pattern, path=path):
                self.assertIs(bool(changes.glob(pattern).fullmatch(path)), expected)

    def test_matching(self):
        files = ["README.md", "cli/cortex_cli/store.py", "docs/getting-started.md"]
        self.assertEqual(changes.matching(files, ["cli/**", "install.sh"]), ["cli/cortex_cli/store.py"])
        self.assertEqual(changes.matching(["README.md"], ["cli/**", "docs/**"]), [])


@unittest.skipUnless(shutil.which("git"), "git is needed")
class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="changes-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.commit({"README.md": "a", "cli/a.py": "a"})
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def commit(self, files):
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")

    def run_changes(self, base, paths="cli/**\ninstall.sh"):
        out = io.StringIO()
        output = Path(tempfile.mkstemp()[1])
        self.addCleanup(output.unlink)
        cwd, saved = os.getcwd(), os.environ.get("GITHUB_OUTPUT")
        os.chdir(self.repo)
        os.environ["GITHUB_OUTPUT"] = str(output)
        try:
            with redirect_stdout(out):
                changes.main(["--base", base, "--head", "HEAD", "--paths", paths])
        finally:
            os.chdir(cwd)
            if saved is None:
                os.environ.pop("GITHUB_OUTPUT")
            else:
                os.environ["GITHUB_OUTPUT"] = saved
        return output.read_text(encoding="utf-8").strip(), out.getvalue()

    def test_a_readme_only_change_skips_the_jobs(self):
        self.commit({"README.md": "b"})
        self.assertEqual(self.run_changes(self.base)[0], "run=false")

    def test_a_change_the_jobs_concern_runs_them(self):
        self.commit({"cli/a.py": "b"})
        run, out = self.run_changes(self.base)
        self.assertEqual(run, "run=true")
        self.assertIn("cli/a.py first", out)

    def test_the_change_is_read_against_the_merge_base(self):
        # The base moved on with a cli change of its own: the branch's README change still skips.
        self.git("checkout", "-q", "-b", "topic")
        self.commit({"README.md": "b"})
        self.git("checkout", "-q", "main")
        self.commit({"cli/a.py": "c"})
        main = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", "topic")
        self.assertEqual(self.run_changes(main)[0], "run=false")

    def test_no_base_runs_everything(self):
        for base in ("", "0" * 40, "f" * 40):
            with self.subTest(base=base):
                self.assertEqual(self.run_changes(base)[0], "run=true")

    def test_a_path_out_of_ascii_matches_as_it_is_named(self):
        self.git("config", "core.quotePath", "true")   # git's default, whatever this machine's
        self.commit({"cli/caf\u00e9.py": "x"})
        run, out = self.run_changes(self.base)
        self.assertEqual(run, "run=true")
        self.assertIn("cli/caf\u00e9.py first", out)

    def test_comments_and_blank_lines_in_paths(self):
        self.commit({"install.sh": "x"})
        self.assertEqual(self.run_changes(self.base, "# the scripts\n\ninstall.sh\n")[0], "run=true")


if __name__ == "__main__":
    unittest.main()
