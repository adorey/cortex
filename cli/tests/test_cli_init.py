"""``cortex init`` — ``setup.sh``, at parity (ADR-008 §3.7, phase 4).

The matrix (``init_matrix``) is what ``setup.sh`` writes, captured. ``cortex init`` must write the
same files, byte for byte, plus its own three. The script replays the matrix too, until phase 5
deletes it.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the harness, not a package named tests
import cli_harness as harness  # noqa: E402
import init_matrix as matrix  # noqa: E402

EXPECTED = json.loads(matrix.EXPECTED.read_text(encoding="utf-8"))
OWN = harness.EXPECTED_VERSION if harness.BINARY else "9.9.9"
HAS_GIT = shutil.which("git") is not None


class InitTestCase(unittest.TestCase):
    """A store holding the matrix's spec at this command's own version, and a project to init."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-init-")).resolve()
        self.addCleanup(self.cleanup)
        self.spec = matrix.build_spec(self.tmp)
        self.home = self.tmp / "cortex-home"
        shutil.copytree(self.spec, self.home / "versions" / OWN)
        self.env = harness.environment(CORTEX_HOME=str(self.home), CORTEX_SOURCE_VERSION=OWN)
        self.project = self.tmp / "init" / "project"

    def cleanup(self):
        for directory, subdirs, files in os.walk(self.tmp):
            for name in subdirs + files:
                path = os.path.join(directory, name)
                if not os.path.islink(path):
                    os.chmod(path, 0o700)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def init(self, *args, cwd=None, stdin=subprocess.DEVNULL):
        proc = harness.run("init", *args, cwd=cwd or self.project, env=self.env, stdin=stdin)
        proc.out, proc.err = proc.stdout.decode(), proc.stderr.decode()
        return proc

    def run_case(self, case):
        options, services, before = matrix.CASES[case]
        matrix.prepare(self.project, before)
        proc = self.init(*options, *[arg for name in services for arg in ("--service", name)])
        self.assertEqual(proc.returncode, 0, proc.err)
        return proc

    def read(self, name):
        return (self.project / name).read_text(encoding="utf-8")


class MatrixTests(InitTestCase):
    def test_cortex_init_writes_what_setup_sh_wrote(self):
        for case in matrix.CASES:
            if "git" in matrix.CASES[case][2].values() and not HAS_GIT:
                continue
            with self.subTest(case=case):
                if self.project.exists():
                    shutil.rmtree(self.project)
                self.run_case(case)
                self.assertEqual(matrix.snapshot(self.project, skip=("cortex", *matrix.OWN_FILES)),
                                 EXPECTED[case]["files"])
                # The one difference: the theme goes to cortex.toml, not to a marker in the spec.
                self.assertIn(f'theme = "{EXPECTED[case]["active_theme"]}"', self.read("cortex.toml"))
                self.assertIn(f'version = "{OWN}"', self.read("cortex.toml"))
                self.assertIn("cortex.local.toml", self.read(".gitignore").splitlines())
                self.assertIn("spec = ", self.read("cortex.local.toml"))

    def test_the_comparison_catches_one_byte(self):
        self.run_case("single-claude")
        altered = dict(EXPECTED["single-claude"]["files"])
        text = altered["CLAUDE.md"]
        altered["CLAUDE.md"] = text[:100] + chr(ord(text[100]) ^ 1) + text[101:]
        self.assertNotEqual(matrix.snapshot(self.project, skip=("cortex", *matrix.OWN_FILES)), altered)

    def test_the_matrix_was_captured_for_every_case(self):
        self.assertEqual(sorted(EXPECTED), sorted(matrix.CASES))


@unittest.skipIf(os.name == "nt" or shutil.which("bash") is None or not HAS_GIT, "setup.sh is a Bash script")
@unittest.skipUnless((matrix.REPO / "setup.sh").is_file(), "setup.sh is gone")
class SetupShTests(unittest.TestCase):
    def test_setup_sh_still_writes_the_matrix(self):
        for case in matrix.CASES:
            with self.subTest(case=case):
                tmp = Path(tempfile.mkdtemp(prefix="cortex-init-"))
                try:
                    self.assertEqual(matrix.run_setup(case, tmp, matrix.build_spec(tmp)), EXPECTED[case])
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)


class OptionTests(InitTestCase):
    def setUp(self):
        super().setUp()
        self.project.mkdir(parents=True)

    def test_a_workspace_with_services_runs_unattended_with_stdin_closed(self):
        read_end, write_end = os.pipe()
        os.close(write_end)
        try:
            proc = self.init("--workspace", "--service", "api", "--service", "core/web", stdin=read_end)
        finally:
            os.close(read_end)
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn("<!-- @alias: web -->", self.read("core/web/project-overview.md"))

    def test_an_existing_instructions_file_is_kept_without_force(self):
        (self.project / "CLAUDE.md").write_text("# ours\n", encoding="utf-8")
        proc = self.init("--tool", "claude")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertEqual(self.read("CLAUDE.md"), "# ours\n")
        self.assertIn("kept — --force replaces it", proc.out)

    def test_and_replaced_with_it(self):
        (self.project / "CLAUDE.md").write_text("# ours\n", encoding="utf-8")
        self.assertEqual(self.init("--tool", "claude", "--force").returncode, 0)
        self.assertEqual(self.read("CLAUDE.md"), EXPECTED["single-claude"]["files"]["CLAUDE.md"])

    def test_link_and_copy_go_to_cortex_toml_and_gitignore(self):
        for flag in ("--link", "--copy"):
            with self.subTest(flag=flag):
                project = self.tmp / flag.strip("-")
                project.mkdir()
                proc = self.init(flag, cwd=project)
                self.assertEqual(proc.returncode, 0, proc.err)
                self.assertIn(f'sync = "{flag[2:]}"', (project / "cortex.toml").read_text(encoding="utf-8"))
                self.assertIn("/cortex/", (project / ".gitignore").read_text(encoding="utf-8").splitlines())
                self.assertTrue(os.path.lexists(project / "cortex"))
                self.assertNotIn("note:", proc.err)

    def test_an_existing_gitignore_keeps_its_lines(self):
        (self.project / ".gitignore").write_text("node_modules/", encoding="utf-8")
        self.init()
        self.assertEqual(self.read(".gitignore"), "node_modules/\ncortex.local.toml\n")
        self.init()
        self.assertEqual(self.read(".gitignore"), "node_modules/\ncortex.local.toml\n")

    def test_a_second_init_keeps_cortex_toml(self):
        self.init("--theme", "acme")
        proc = self.init("--theme", "h2g2")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn('theme = "acme"', self.read("cortex.toml"))
        self.assertIn("kept", proc.out)

    def test_a_theme_the_spec_does_not_have(self):
        proc = self.init("--theme", "no-such-theme")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("theme 'no-such-theme' is not in", proc.err)
        self.assertIn("acme, h2g2", proc.err)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_a_directory_given(self):
        proc = self.init("sub/app", cwd=self.project)
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertTrue((self.project / "sub" / "app" / "cortex.toml").is_file())
        self.assertTrue((self.project / "sub" / "app" / ".github" / "copilot-instructions.md").is_file())

    def test_bad_arguments(self):
        for args in (["--service", "api"], ["--tool", "vim"], ["--link", "--copy"]):
            with self.subTest(args=args):
                self.assertEqual(self.init(*args).returncode, 2)
        for args, message in ((["--tool", "custom"], "needs --instructions-file"),
                              (["--instructions-file", "x.md"], "goes with --tool custom"),
                              (["--workspace", "--service", "../out"], "a folder inside the workspace")):
            with self.subTest(args=args):
                proc = self.init(*args)
                self.assertEqual(proc.returncode, 1)
                self.assertIn(message, proc.err)
        self.assertFalse((self.tmp / "init" / "out").exists())

    def test_the_team_tier_is_its_own_repository_not_the_projects(self):
        # setup.sh asked git whether agents/ was in a working tree — true inside the project's own
        # repository too. The team tier is for an agents/ that is a repository of its own.
        if not HAS_GIT:
            self.skipTest("needs git")
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        (self.project / "agents").mkdir()
        self.init("--workspace", "--service", "api")
        self.assertFalse((self.project / "agents" / "project-overview.md").exists())


if __name__ == "__main__":
    unittest.main()
