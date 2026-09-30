"""``cortex init`` — the setup script of Cortex 0.x, at parity (ADR-008 §3.7, phase 4).

The matrix (``init_matrix``) is what the script wrote, captured, and — since the script is gone —
what the command writes. ``cortex init`` must write the same files, byte for byte, plus its own
three.
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the harness, not a package named tests
import cli_harness as harness  # noqa: E402
import init_matrix as matrix  # noqa: E402


def display(path):
    return str(path).replace(os.sep, "/")


def quote(path):
    """A path as the commands are shown for the shell: PowerShell on Windows."""
    return "'" + path.replace("'", "''") + "'" if os.name == "nt" else shlex.quote(path)


def remove(path):
    return f"Remove-Item -Recurse -Force {quote(path)}" if os.name == "nt" else f"rm -rf {quote(path)}"

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
        if HAS_GIT:     # a repository to ignore files in: outside of one, init writes no .gitignore
            subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        proc = self.init(*options, *[arg for name in services for arg in ("--service", name)])
        self.assertEqual(proc.returncode, 0, proc.err)
        return proc

    def read(self, name):
        return (self.project / name).read_text(encoding="utf-8")


class MatrixTests(InitTestCase):
    def test_cortex_init_writes_the_matrix(self):
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
                if HAS_GIT:
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

    def test_and_replaced_with_it_the_old_one_kept_beside(self):
        (self.project / "CLAUDE.md").write_text("# ours\n", encoding="utf-8")
        proc = self.init("--tool", "claude", "--force")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertEqual(self.read("CLAUDE.md"), EXPECTED["single-claude"]["files"]["CLAUDE.md"])
        self.assertEqual(self.read("CLAUDE.md.bak"), "# ours\n")
        self.assertIn("CLAUDE.md.bak", proc.out)

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_git_ignores_cortex_in_link_and_copy_modes(self):
        # A link is a file to git: `/cortex/` would not match it, and the link — with the absolute
        # path of this machine's store — would go into the commit.
        for flag in ("--link", "--copy"):
            with self.subTest(flag=flag):
                project = self.tmp / flag.strip("-")
                subprocess.run(["git", "init", "-q", str(project)], check=True)
                proc = self.init(flag, cwd=project)
                self.assertEqual(proc.returncode, 0, proc.err)
                self.assertIn(f'sync = "{flag[2:]}"', (project / "cortex.toml").read_text(encoding="utf-8"))
                self.assertTrue(os.path.lexists(project / "cortex"))
                check = subprocess.run(["git", "-C", str(project), "check-ignore", "-q", "cortex"])
                self.assertEqual(check.returncode, 0, "git does not ignore cortex")
                status = subprocess.run(["git", "-C", str(project), "status", "--porcelain", "--untracked-files=all"],
                                        capture_output=True, text=True, check=True).stdout
                self.assertNotIn("cortex/", status)
                self.assertNotRegex(status, r"(?m) cortex$")
                self.assertNotIn("note:", proc.err)

    def test_an_existing_gitignore_keeps_its_bytes(self):
        (self.project / ".gitignore").write_text("node_modules/", encoding="utf-8")
        self.init()
        self.assertEqual(self.read(".gitignore"), "node_modules/\ncortex.local.toml\n")
        self.init()
        self.assertEqual(self.read(".gitignore"), "node_modules/\ncortex.local.toml\n")
        # A byte order mark, CRLF line endings and a byte that is no UTF-8 stay as they were.
        (self.project / ".gitignore").write_bytes(b"\xef\xbb\xbfcortex.local.toml\r\ncaf\xe9/\r\n")
        proc = self.init("--copy")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertEqual((self.project / ".gitignore").read_bytes(),
                         b"\xef\xbb\xbfcortex.local.toml\r\ncaf\xe9/\r\n/cortex\r\n/.cortex-sync-*\r\n")

    def test_a_second_init_keeps_cortex_toml_but_for_the_options_given(self):
        self.init("--theme", "acme", "--link")
        (self.project / "cortex.toml").write_text(self.read("cortex.toml") + "# the team's note\n", encoding="utf-8")
        before = self.read("cortex.toml")
        proc = self.init()
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertEqual(self.read("cortex.toml"), before)
        self.assertIn("kept", proc.out)
        self.assertTrue(os.path.islink(self.project / "cortex") or os.path.isdir(self.project / "cortex"))
        proc = self.init("--theme", "h2g2")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertEqual(self.read("cortex.toml"), before.replace('theme = "acme"', 'theme = "h2g2"'))
        self.assertIn('theme = "h2g2" — the rest kept', proc.out)
        proc = self.init("--copy", "--no-personality")
        self.assertEqual(proc.returncode, 0, proc.err)
        text = self.read("cortex.toml")
        self.assertIn('theme = "none"', text)
        self.assertIn('sync = "copy"', text)
        self.assertIn("# the team's note", text)
        self.assertTrue((self.project / "cortex" / ".synced").is_file())

    def test_force_keeps_cortex_toml(self):
        # --force replaces the instructions file, and only it: the team's theme, its sync mode and
        # its version stay, and so does the copy.
        self.init("--theme", "acme", "--copy")
        before = self.read("cortex.toml")
        proc = self.init("--force")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertEqual(self.read("cortex.toml"), before)
        self.assertTrue((self.project / "cortex" / ".synced").is_file())
        self.assertIn("PERSONALITY", self.read(".github/copilot-instructions.md"))

    def test_a_version_is_never_downgraded(self):
        (self.project / "cortex.toml").write_text('version = "99.0.0"\ntheme = "h2g2"\n', encoding="utf-8")
        for args in ([], ["--force"]):
            with self.subTest(args=args):
                proc = self.init(*args)
                self.assertEqual(proc.returncode, 1)
                self.assertIn("newer than this cortex", proc.err)
                self.assertEqual(self.read("cortex.toml"), 'version = "99.0.0"\ntheme = "h2g2"\n')
                self.assertEqual(sorted(p.name for p in self.project.iterdir()), ["cortex.toml"])

    def test_an_unreadable_cortex_toml_is_refused_and_kept(self):
        (self.project / "cortex.toml").write_text('version = "1.0.0"\ntheme = "../../templates"\n', encoding="utf-8")
        for args in ([], ["--force"]):
            with self.subTest(args=args):
                proc = self.init(*args)
                self.assertEqual(proc.returncode, 1)
                self.assertIn("fix it, or remove it to start over", proc.err)
                self.assertEqual(sorted(p.name for p in self.project.iterdir()), ["cortex.toml"])

    def test_a_theme_found_nowhere(self):
        proc = self.init("--theme", "no-such-theme")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("theme 'no-such-theme' is neither in", proc.err)
        self.assertIn("acme, h2g2", proc.err)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_a_theme_is_a_name(self):
        for theme in ("../../templates", 'a"b', "h2g2\n"):
            with self.subTest(theme=theme):
                proc = self.init("--theme", theme)
                self.assertEqual(proc.returncode, 1)
                self.assertIn("no theme name", proc.err)
                self.assertEqual(list(self.project.iterdir()), [])

    def test_a_root_that_is_no_repository_is_said_and_gets_no_gitignore(self):
        proc = self.init()
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn("is in no git repository", proc.err)
        self.assertFalse((self.project / ".gitignore").exists())
        if HAS_GIT:
            subprocess.run(["git", "init", "-q", str(self.project)], check=True)
            proc = self.init()
            self.assertNotIn("is in no git repository", proc.err)
            self.assertIn("cortex.local.toml", self.read(".gitignore").splitlines())

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_a_copy_turned_into_a_link_is_ignored_as_a_link(self):
        # Asked before the sync, git saw cortex/ still a directory, which `cortex/` matches: the
        # link that took its place was then a file git did not ignore.
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        (self.project / ".gitignore").write_text("cortex/\n", encoding="utf-8")
        self.assertEqual(self.init("--copy").returncode, 0)
        proc = self.init("--link")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertTrue(os.path.islink(self.project / "cortex") or os.name == "nt")
        self.assertEqual(subprocess.run(["git", "-C", str(self.project), "check-ignore", "-q", "cortex"]).returncode, 0)
        self.assertNotIn("git does not ignore", proc.err)

    def test_a_new_project_keeps_the_default_tool_whatever_file_is_there(self):
        # A CLAUDE.md written by hand is no reason to take Claude for the tool: it holds no Cortex
        # bootstrap, and --force would have replaced it. The script wrote copilot's file, and said nothing.
        (self.project / "CLAUDE.md").write_text("# Our own notes\n", encoding="utf-8")
        proc = self.init()
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertTrue((self.project / ".github" / "copilot-instructions.md").is_file())
        self.assertEqual(self.read("CLAUDE.md"), "# Our own notes\n")
        self.assertIn("CLAUDE.md is there and was kept: it holds no Cortex bootstrap — "
                      "cortex init --tool claude --force replaces it", proc.err)

    def test_an_older_bootstrap_is_said(self):
        # Written before cortex.toml, it reads cortex/ as the submodule it was: there is no spec there.
        older = "# Cortex AI Team\n\nRead `cortex/agents/roles/prompt-manager.md` first.\n"
        (self.project / "CLAUDE.md").write_text(older, encoding="utf-8")
        proc = self.init()
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertTrue((self.project / ".github" / "copilot-instructions.md").is_file())
        self.assertEqual(self.read("CLAUDE.md"), older)
        self.assertIn("CLAUDE.md is there and was kept: an older Cortex bootstrap, which does not read "
                      "cortex.local.toml — cortex init --tool claude --force replaces it", proc.err)
        proc = self.init("--tool", "claude")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn("CLAUDE.md is an older Cortex bootstrap: it does not read cortex.local.toml", proc.err)

    def test_a_kept_file_without_the_bootstrap_is_said(self):
        (self.project / "CLAUDE.md").write_text("# Our own notes\n", encoding="utf-8")
        proc = self.init("--tool", "claude")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn("CLAUDE.md holds no Cortex bootstrap: the tool will not find Cortex", proc.err)

    def test_a_second_init_of_a_custom_tool_says_what_it_wrote(self):
        self.assertEqual(self.init("--tool", "custom", "--instructions-file", "docs/ai.md").returncode, 0)
        proc = self.init()
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn("no instructions file of a known tool was here", proc.err)

    def test_a_bootstrap_for_the_other_layout_is_said(self):
        self.assertEqual(self.init("--tool", "claude").returncode, 0)
        proc = self.init("--tool", "claude", "--workspace")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn("was written for a single project", proc.err)

    def test_the_backup_is_said_to_be_left_to_git(self):
        (self.project / "CLAUDE.md").write_text("# mine\n", encoding="utf-8")
        proc = self.init("--tool", "claude", "--force")
        self.assertIn("CLAUDE.md.bak: the file --force replaces, as it was — git does not ignore it", proc.out)

    def test_outside_a_repository_an_existing_gitignore_is_said_to_do_nothing(self):
        (self.project / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        proc = self.init()
        self.assertIn("its .gitignore keeps nothing out of a commit", proc.err)
        self.assertNotIn("no .gitignore is written", proc.err)

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_what_a_killed_sync_leaves_is_ignored_too(self):
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.assertEqual(self.init("--link").returncode, 0)
        check = subprocess.run(["git", "-C", str(self.project), "check-ignore", "-q", ".cortex-sync-1234-abcd"])
        self.assertEqual(check.returncode, 0)

    def test_a_file_where_a_folder_is_to_be_made_is_refused_first(self):
        (self.project / "api").write_text("a file\n", encoding="utf-8")
        (self.project / ".cursor").write_text("a file\n", encoding="utf-8")
        for args in (["--workspace", "--service", "api/x"], ["--tool", "cursor"]):
            with self.subTest(args=args):
                proc = self.init(*args)
                self.assertEqual(proc.returncode, 1)
                self.assertIn("is a file, not a folder", proc.err)
                self.assertNotIn("Traceback", proc.err)
                self.assertEqual(sorted(p.name for p in self.project.iterdir()), [".cursor", "api"])
        if os.name != "nt":                                 # a link that leads nowhere is no folder either
            (self.project / ".cursor").unlink()
            (self.project / ".cursor").symlink_to(self.project / "gone")
            proc = self.init("--tool", "cursor")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("is a file, not a folder", proc.err)
            self.assertEqual(sorted(p.name for p in self.project.iterdir()), [".cursor", "api"])

    def test_force_never_overwrites_a_backup(self):
        (self.project / "CLAUDE.md").write_text("# mine, first\n", encoding="utf-8")
        self.assertEqual(self.init("--tool", "claude", "--force").returncode, 0)
        (self.project / "CLAUDE.md").write_text("# mine, second\n", encoding="utf-8")
        proc = self.init("--tool", "claude", "--force")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertEqual(self.read("CLAUDE.md.bak"), "# mine, first\n")
        self.assertEqual(self.read("CLAUDE.md.bak.1"), "# mine, second\n")
        # Already what --force writes: nothing to back up, nothing rewritten.
        proc = self.init("--tool", "claude", "--force")
        self.assertIn("is what --force would write", proc.out)
        self.assertFalse((self.project / "CLAUDE.md.bak.2").exists())

    def test_a_second_init_writes_the_instructions_file_of_the_tool_already_there(self):
        self.assertEqual(self.init("--tool", "claude").returncode, 0)
        proc = self.init()
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertFalse((self.project / ".github" / "copilot-instructions.md").exists())
        self.assertIn("CLAUDE.md kept", proc.out)
        (self.project / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
        proc = self.init("--force")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("several instructions files are there", proc.err)

    def test_a_kept_instructions_file_that_no_longer_fits_the_theme_is_said(self):
        self.assertEqual(self.init("--tool", "claude").returncode, 0)
        proc = self.init("--tool", "claude", "--no-personality")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn("was written with the personality block", proc.err)
        self.assertIn("cortex init --force writes it again", proc.err)

    def test_cortex_toml_keeps_its_comments_and_its_byte_order_mark(self):
        self.assertEqual(self.init("--theme", "acme").returncode, 0)
        text = self.read("cortex.toml").replace('theme = "acme"', 'theme = "acme"  # the team\'s choice')
        (self.project / "cortex.toml").write_bytes(("\ufeff" + text).encode("utf-8"))
        self.assertEqual(self.init("--theme", "h2g2").returncode, 0)
        written = (self.project / "cortex.toml").read_bytes().decode("utf-8")
        self.assertTrue(written.startswith("\ufeff"))
        self.assertIn('theme = "h2g2"  # the team\'s choice', written)

    def test_a_theme_of_the_projects_own(self):
        # docs/creating-a-theme.md: a custom theme lives in the project, with no base in Cortex.
        (self.project / "agents" / "personalities" / "ours").mkdir(parents=True)
        proc = self.init("--theme", "ours")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn('theme = "ours"', self.read("cortex.toml"))
        self.assertNotIn("warning: theme", proc.err)

    def test_from_a_checkout_its_templates_and_its_spec(self):
        # CONTRIBUTING's loop: a template edited in a checkout reaches the project at once.
        checkout = self.tmp / "checkout"
        shutil.copytree(self.spec, checkout)
        template = checkout / "templates" / "bootstrap-instructions.md"
        template.write_bytes(template.read_bytes().replace(b"# Cortex AI Team", b"# Cortex AI Team, edited", 1))
        proc = self.init("--tool", "claude", "--from", str(checkout))
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertTrue(self.read("CLAUDE.md").startswith("# Cortex AI Team, edited\n"))
        self.assertIn(str(checkout).replace(os.sep, "/"), self.read("cortex.local.toml"))
        self.assertIn("no version is checked (--from)", proc.err)

    def test_a_directory_given(self):
        proc = self.init("sub/app", cwd=self.project)
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertTrue((self.project / "sub" / "app" / "cortex.toml").is_file())
        self.assertTrue((self.project / "sub" / "app" / ".github" / "copilot-instructions.md").is_file())

    def test_bad_arguments(self):
        for args in (["--service", "api"], ["--tool", "vim"], ["--link", "--copy"]):
            with self.subTest(args=args):
                self.assertEqual(self.init(*args).returncode, 2)
        (self.project / "notes").write_text("mine\n", encoding="utf-8")
        (self.project / "docs").mkdir()
        for args, message in ((["--tool", "custom"], "needs --instructions-file"),
                              (["--instructions-file", "x.md"], "goes with --tool custom"),
                              (["--workspace", "--service", "api", "--service", "../out"], "a folder inside the workspace"),
                              (["--workspace", "--service", "notes"], "is a file, not a folder"),
                              (["--tool", "custom", "--instructions-file", "docs"], "a directory"),
                              (["--tool", "custom", "--instructions-file", "cortex.toml"], "writes for itself"),
                              (["--tool", "custom", "--instructions-file", ".gitignore"], "writes for itself"),
                              (["--tool", "custom", "--instructions-file", "cortex"], "writes for itself"),
                              (["--tool", "custom", "--instructions-file", "CORTEX.TOML"], "writes for itself"),
                              (["--tool", "custom", "--instructions-file", ".git/config", "--force"], "of git's own"),
                              (["--workspace", "--service", "api", "--tool", "custom", "--instructions-file",
                                "api/project-overview.md"], "writes for itself")):
            with self.subTest(args=args):
                proc = self.init(*args)
                self.assertEqual(proc.returncode, 1)
                self.assertIn(message, proc.err)
                self.assertNotIn("Traceback", proc.err)
                # Nothing is written before a refusal.
                self.assertEqual(sorted(p.name for p in self.project.iterdir()), ["docs", "notes"])
        self.assertFalse((self.tmp / "init" / "out").exists())

    @unittest.skipIf(os.name == "nt", "a backslash separates folders on Windows")
    def test_a_backslash_is_part_of_a_service_name_outside_windows(self):
        proc = self.init("--workspace", "--service", "a\\b")
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn("<!-- @alias: a\\b -->", self.read("a\\b/project-overview.md"))

    def test_services_on_stdin_without_a_terminal_are_said_to_be_ignored(self):
        proc = self.init("--workspace", stdin=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertIn("no service created — --service NAME adds one", proc.err)

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_a_submodule_is_refused_and_the_commands_printed(self):
        # A real submodule: the superproject's git state is exactly what the commands would change.
        upstream = self.tmp / "upstream"
        subprocess.run(["git", "init", "-q", str(upstream)], check=True)
        (upstream / "README.md").write_text("cortex\n", encoding="utf-8")
        git = ["git", "-c", "user.email=ci@example.com", "-c", "user.name=CI", "-c", "protocol.file.allow=always"]
        subprocess.run([*git, "-C", str(upstream), "add", "."], check=True)
        subprocess.run([*git, "-C", str(upstream), "commit", "-q", "-m", "x"], check=True)
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run([*git, "-C", str(self.project), "submodule", "add", "-q", str(upstream), "cortex"], check=True)
        before = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        for command in (["init"], ["sync"]):
            with self.subTest(command=command[0]):
                if command == ["sync"]:
                    (self.project / "cortex.toml").write_text(f'version = "{OWN}"\ntheme = "h2g2"\n', encoding="utf-8")
                    before["cortex.toml"] = (self.project / "cortex.toml").read_bytes()
                proc = harness.run(*command, cwd=self.project, env=self.env)
                err = proc.stderr.decode()
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("cortex/ is a git submodule", err)
                root = display(self.project)
                for line in (f"git -C {quote(root)} submodule deinit -f cortex", f"git -C {quote(root)} rm cortex",
                             remove(display(self.project / ".git" / "modules" / "cortex"))):
                    self.assertIn(f"    {line}\n", err)
                after = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
                self.assertEqual(after, before)

    def _submodule_stack(self):
        """A project whose cortex/ is a submodule, pushed to an origin, and a teammate's clone of it
        with the submodule initialised."""
        git = ["git", "-c", "user.email=ci@example.com", "-c", "user.name=CI", "-c", "protocol.file.allow=always"]
        upstream, origin, teammate = self.tmp / "upstream", self.tmp / "origin.git", self.tmp / "teammate"
        subprocess.run(["git", "init", "-q", str(upstream)], check=True)
        (upstream / "README.md").write_text("cortex\n", encoding="utf-8")
        subprocess.run([*git, "-C", str(upstream), "add", "."], check=True)
        subprocess.run([*git, "-C", str(upstream), "commit", "-q", "-m", "x"], check=True)
        subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        subprocess.run([*git, "-C", str(self.project), "submodule", "add", "-q", str(upstream), "cortex"], check=True)
        subprocess.run([*git, "-C", str(self.project), "commit", "-q", "-m", "the submodule"], check=True)
        subprocess.run([*git, "-C", str(self.project), "push", "-q", str(origin), "HEAD:refs/heads/main"], check=True)
        subprocess.run([*git, "clone", "-q", "--recurse-submodules", "-b", "main", str(origin), str(teammate)],
                       check=True, capture_output=True)
        return git, origin, teammate

    def _with_git(self):
        return dict(self.env, PATH=os.pathsep.join([os.path.dirname(shutil.which("git")), self.env["PATH"]]))

    @staticmethod
    def _shown(err):
        """The commands a refusal prints to be run, in order."""
        block = err.split("shown here, not run:\n\n", 1)[1].split("\n\n", 1)[0]
        return [line.strip() for line in block.splitlines()]

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_the_last_submodule_leaves_no_empty_gitmodules(self):
        # git rm empties .gitmodules of its last section and keeps the file, tracked.
        self._submodule_stack()
        proc = harness.run("init", cwd=self.project, env=self._with_git())
        self.assertEqual(proc.returncode, 1)
        commands = self._shown(proc.stderr.decode())
        self.assertIn(f"git -C {quote(display(self.project))} rm -f .gitmodules", commands)
        if os.name == "nt":
            return
        for command in commands:
            subprocess.run(command, shell=True, check=True, capture_output=True)
        self.assertFalse((self.project / ".gitmodules").exists())
        status = subprocess.run(["git", "-C", str(self.project), "status", "--short"], capture_output=True, text=True)
        self.assertEqual(sorted(status.stdout.splitlines()), ["D  .gitmodules", "D  cortex"])

    def _teammate_after_the_pull(self):
        """The teammate's clone once they pulled the commit that removes the submodule."""
        git, origin, teammate = self._submodule_stack()
        for command in (["submodule", "deinit", "-q", "-f", "cortex"], ["rm", "-q", "cortex"], ["rm", "-q", "-f", ".gitmodules"]):
            subprocess.run([*git, "-C", str(self.project), *command], check=True)
        self._rmtree(self.project / ".git" / "modules" / "cortex")
        (self.project / "cortex.toml").write_text(f'version = "{OWN}"\ntheme = "h2g2"\n', encoding="utf-8")
        subprocess.run([*git, "-C", str(self.project), "add", "cortex.toml"], check=True)
        subprocess.run([*git, "-C", str(self.project), "commit", "-q", "-m", "the store"], check=True)
        subprocess.run([*git, "-C", str(self.project), "push", "-q", str(origin), "HEAD:refs/heads/main"], check=True)
        subprocess.run([*git, "-C", str(teammate), "pull", "-q"], capture_output=True)       # warns: cortex/ is not empty
        self.assertTrue((teammate / "cortex" / ".git").is_file())
        return teammate

    @staticmethod
    def _rmtree(path):
        # git's objects are read-only, and Windows removes no read-only file.
        writable = {"onexc" if sys.version_info >= (3, 12) else "onerror":
                    lambda remove, name, _: (os.chmod(name, 0o700), remove(name))}
        shutil.rmtree(path, **writable)

    def _sync_after_running(self, teammate, err):
        """Run what a refusal printed, then sync again: it must pass."""
        if os.name == "nt":
            return
        for command in self._shown(err):
            subprocess.run(command, shell=True, check=True, capture_output=True)
        proc = harness.run("sync", cwd=teammate, env=self._with_git())
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_a_teammate_who_pulled_the_removal_is_given_commands_that_work(self):
        # After the pull, git has dropped cortex from the index and kept the directory, the
        # submodule's repository and its settings: deinit and rm have nothing to act on.
        teammate = self._teammate_after_the_pull()
        without_git = harness.run("sync", cwd=teammate, env=self.env)
        self.assertIn("submodule deinit", without_git.stderr.decode())      # no git to ask: the migrator's commands

        proc = harness.run("sync", cwd=teammate, env=self._with_git())
        err = proc.stderr.decode()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("was removed by a commit you pulled", err)
        target = quote(display(teammate / "cortex"))
        # What changed in it, ignored files included, and the commits nobody pushed.
        self.assertIn(f"    git -C {target} status --short --ignored\n    git -C {target} log --oneline HEAD --not --remotes\n", err)
        for check in (["status", "--short", "--ignored"], ["log", "--oneline", "HEAD", "--not", "--remotes"]):
            listed = subprocess.run(["git", "-C", str(teammate / "cortex"), *check], capture_output=True, text=True)
            self.assertEqual((listed.returncode, listed.stdout), (0, ""), check)      # a clean clone: nothing listed
        self.assertNotIn("submodule deinit", err)
        root = quote(display(teammate))
        self.assertEqual(self._shown(err), [f"git -C {root} config --remove-section submodule.cortex",
                                            remove(display(teammate / "cortex")),
                                            remove(display(teammate / ".git" / "modules" / "cortex"))])
        self._sync_after_running(teammate, err)

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_a_teammate_who_ran_the_commands_1_0_0_printed(self):
        # Of the three, only the removal of .git/modules/cortex ran: cortex/.git names a repository
        # that is gone, and git cannot show what changed in cortex/.
        teammate = self._teammate_after_the_pull()
        self._rmtree(teammate / ".git" / "modules" / "cortex")
        proc = harness.run("sync", cwd=teammate, env=self._with_git())
        err = proc.stderr.decode()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Its repository is already gone, so git cannot show what changed in it", err)
        self.assertNotIn("status --short", err)
        self.assertNotIn("with the submodule's repository", err)
        self.assertEqual(self._shown(err), [f"git -C {quote(display(teammate))} config --remove-section submodule.cortex",
                                            remove(display(teammate / "cortex"))])
        self._sync_after_running(teammate, err)

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_a_teammate_whose_settings_hold_no_submodule_section(self):
        teammate = self._teammate_after_the_pull()
        subprocess.run(["git", "-C", str(teammate), "config", "--remove-section", "submodule.cortex"], check=True)
        proc = harness.run("sync", cwd=teammate, env=self._with_git())
        err = proc.stderr.decode()
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self._shown(err), [remove(display(teammate / "cortex")),
                                            remove(display(teammate / ".git" / "modules" / "cortex"))])
        self._sync_after_running(teammate, err)

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_a_second_submodule_keeps_gitmodules(self):
        # .gitmodules is removed only when cortex was its last section.
        git, _, _ = self._submodule_stack()
        other = self.tmp / "other"
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        subprocess.run([*git, "-C", str(other), "commit", "-q", "--allow-empty", "-m", "x"], check=True)
        subprocess.run([*git, "-C", str(self.project), "submodule", "add", "-q", str(other), "libs/other"], check=True)
        proc = harness.run("init", cwd=self.project, env=self._with_git())
        self.assertEqual(proc.returncode, 1)
        commands = self._shown(proc.stderr.decode())
        self.assertIn(f"git -C {quote(display(self.project))} rm cortex", commands)
        self.assertFalse(any(".gitmodules" in command for command in commands), commands)

    def test_a_clone_is_refused_and_its_removal_printed(self):
        (self.project / "cortex" / ".git").mkdir(parents=True)
        proc = self.init()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cortex/ is a git clone", proc.err)
        self.assertIn(f"    {remove(display(self.project / 'cortex'))}\n", proc.err)
        self.assertEqual(sorted(p.name for p in self.project.iterdir()), ["cortex"])

    def test_the_commands_run_from_any_directory_and_hold_any_path(self):
        # Shown from ~ for projects/foo, `rm -rf cortex` would remove ~/cortex; a space would split it.
        project = self.tmp / "init" / "my app"
        (project / "cortex" / ".git").mkdir(parents=True)
        proc = self.init("my app", cwd=self.tmp / "init")
        self.assertEqual(proc.returncode, 1)
        command = remove(display(project / "cortex"))
        self.assertIn(f"    {command}\n", proc.err)
        if os.name != "nt":
            self.assertEqual(shlex.split(command), ["rm", "-rf", str(project / "cortex")])

    def test_a_submodule_with_its_own_git_directory(self):
        # Older git kept a submodule's repository in its .git directory: .gitmodules still says so.
        (self.project / "cortex" / ".git").mkdir(parents=True)
        (self.project / ".gitmodules").write_text('[submodule "cortex"]\n\tpath = cortex\n\turl = x\n',
                                                  encoding="utf-8")
        proc = self.init()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cortex/ is a git submodule", proc.err)
        self.assertIn(f"git -C {quote(display(self.project))} rm cortex", proc.err)
        self.assertNotIn("rm -rf", proc.err.replace("git -C", ""))

    @unittest.skipUnless(HAS_GIT, "needs git")
    def test_a_worktree_is_no_submodule(self):
        other = self.tmp / "other"
        git = ["git", "-c", "user.email=ci@example.com", "-c", "user.name=CI"]
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        subprocess.run([*git, "-C", str(other), "commit", "-q", "--allow-empty", "-m", "x"], check=True)
        subprocess.run(["git", "-C", str(other), "worktree", "add", "-q", str(self.project / "cortex")], check=True)
        proc = self.init()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("cortex/ is a git worktree", proc.err)
        self.assertIn(f"worktree remove {quote(display(self.project / 'cortex'))}", proc.err)
        self.assertNotIn("submodule deinit", proc.err)

    def test_the_team_tier_is_its_own_repository_not_the_projects(self):
        # The setup script asked git whether agents/ was in a working tree — true inside the project's own
        # repository too. The team tier is for an agents/ that is a repository of its own.
        if not HAS_GIT:
            self.skipTest("needs git")
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        (self.project / "agents").mkdir()
        self.init("--workspace", "--service", "api")
        self.assertFalse((self.project / "agents" / "project-overview.md").exists())


if __name__ == "__main__":
    unittest.main()
