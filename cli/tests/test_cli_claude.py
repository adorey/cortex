"""``claude_access`` — Claude Code reads the spec without asking, on request (ADR-008 §9).

In process: what ``.claude/settings.local.json`` becomes. Through the command: ``sync`` and
``init`` keeping it, and asking on a terminal.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parents[1] / "core"), str(HERE)]
from cortex_cli import claude  # noqa: E402
import cli_harness as harness  # noqa: E402

OWN = harness.EXPECTED_VERSION if harness.BINARY else "9.9.9"


def display(path):
    return str(path).replace(os.sep, "/")


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-claude-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "project"
        self.root.mkdir()
        self.v1 = str(self.tmp / "home" / "versions" / "1.0.0")
        self.v2 = str(self.tmp / "home" / "versions" / "1.1.0")
        os.makedirs(self.v1)
        os.makedirs(self.v2)
        self.settings = self.root / ".claude" / "settings.local.json"

    def read(self):
        return json.loads(self.settings.read_text(encoding="utf-8-sig"))

    def write(self, data):
        self.settings.parent.mkdir(exist_ok=True)
        self.settings.write_text(json.dumps(data), encoding="utf-8")

    def test_a_new_file(self):
        said, owned = claude.update(self.root, self.v1, None)
        self.assertEqual(self.read(), {"permissions": {"additionalDirectories": [self.v1]}})
        self.assertIn("reads", said)
        self.assertEqual(owned, self.v1)

    def test_the_rest_of_the_file_is_kept_and_only_the_owned_entry_moves(self):
        self.write({"model": "opus", "permissions": {"allow": ["Bash(ls:*)"],
                                                     "additionalDirectories": ["/opt/docs", self.v1]}})
        said, owned = claude.update(self.root, self.v2, self.v1)
        self.assertEqual(self.read(), {"model": "opus", "permissions": {
            "allow": ["Bash(ls:*)"], "additionalDirectories": ["/opt/docs", self.v2]}})
        self.assertEqual(owned, self.v2)

    def test_nothing_changes_when_it_is_there(self):
        _, owned = claude.update(self.root, self.v1, None)
        self.assertEqual(claude.update(self.root, self.v1, owned), (None, self.v1))

    def test_the_developers_own_entry_is_theirs_even_in_the_store(self):
        # Claude Code's own "always allow" writes the store's path: Cortex neither owns nor removes it.
        self.write({"permissions": {"additionalDirectories": [self.v1, "~/elsewhere"]}})
        self.assertEqual(claude.update(self.root, self.v1, None), (None, None))
        self.assertEqual(claude.update(self.root, None, None), (None, None))
        self.assertEqual(self.read(), {"permissions": {"additionalDirectories": [self.v1, "~/elsewhere"]}})

    def test_turned_off_it_removes_only_the_owned_entry_and_keeps_the_file(self):
        self.write({"permissions": {"additionalDirectories": ["/opt/docs", self.v1, self.v2]}})
        said, owned = claude.update(self.root, None, self.v1)
        self.assertEqual(self.read(), {"permissions": {"additionalDirectories": ["/opt/docs", self.v2]}})
        self.assertIsNone(owned)
        claude.update(self.root, self.v1, None)
        claude.update(self.root, None, self.v1)
        self.assertTrue(self.settings.is_file())

    def test_no_file_and_nothing_to_allow(self):
        self.assertEqual(claude.update(self.root, None, None), (None, None))
        self.assertFalse(self.settings.exists())

    def test_the_file_keeps_its_format(self):
        self.settings.parent.mkdir()
        text = '\ufeff{\r\n    "model": "opus",\r\n    "permissions": {\r\n        "allow": []\r\n    }\r\n}\r\n'
        self.settings.write_bytes(text.encode("utf-8"))
        claude.update(self.root, self.v1, None)
        written = self.settings.read_bytes().decode("utf-8")
        self.assertTrue(written.startswith("\ufeff{\r\n    \"model\": \"opus\""), written)
        self.assertTrue(written.endswith("}\r\n"))
        self.assertNotIn("\n", written.replace("\r\n", ""))

    @unittest.skipIf(os.name == "nt", "a symbolic link needs a privilege on Windows")
    def test_a_link_to_the_file_stays_a_link(self):
        dotfiles = self.tmp / "dotfiles" / "settings.local.json"
        dotfiles.parent.mkdir()
        dotfiles.write_text('{"model": "opus"}\n', encoding="utf-8")
        self.settings.parent.mkdir()
        self.settings.symlink_to(dotfiles)
        claude.update(self.root, self.v1, None)
        self.assertTrue(self.settings.is_symlink())
        self.assertEqual(json.loads(dotfiles.read_text(encoding="utf-8")),
                         {"model": "opus", "permissions": {"additionalDirectories": [self.v1]}})

    def test_the_entry_is_the_path_the_spec_resolves_to(self):
        if os.name == "nt":
            self.skipTest("a symbolic link needs a privilege on Windows")
        through = self.tmp / "through"
        through.symlink_to(self.tmp / "home")
        self.assertEqual(claude.entry_for(through / "versions" / "1.0.0"), self.v1.replace(os.sep, "/"))

    def test_a_file_it_cannot_read_or_write_is_left_alone(self):
        self.settings.parent.mkdir()
        for text in ("{not json", "[1, 2]", '{"permissions": {"additionalDirectories": "x"}}'):
            with self.subTest(text=text):
                self.settings.write_text(text, encoding="utf-8")
                with self.assertRaises(claude.ClaudeSettingsError):
                    claude.update(self.root, self.v1, None)
                self.assertEqual(self.settings.read_text(encoding="utf-8"), text)
        self.settings.unlink()
        self.settings.mkdir()
        with self.assertRaises(claude.ClaudeSettingsError):
            claude.update(self.root, self.v1, None)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-claude-")).resolve()
        self.addCleanup(self.cleanup)
        self.home = self.tmp / "cortex-home"
        self.env = harness.environment(CORTEX_HOME=str(self.home), CORTEX_SOURCE_VERSION=OWN)
        self.project = self.tmp / "project"
        self.project.mkdir()

    def cleanup(self):
        for directory, subdirs, files in os.walk(self.tmp):
            for name in subdirs + files:
                path = os.path.join(directory, name)
                if not os.path.islink(path):
                    os.chmod(path, 0o700)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cortex(self, *args, stdin=subprocess.DEVNULL):
        proc = harness.run(*args, cwd=self.project, env=self.env, stdin=stdin)
        proc.out, proc.err = proc.stdout.decode(), proc.stderr.decode()
        self.assertEqual(proc.returncode, 0, proc.err)
        return proc

    def allowed(self):
        path = self.project / ".claude" / "settings.local.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8")).get("permissions", {}).get("additionalDirectories", [])

    def local(self):
        return (self.project / "cortex.local.toml").read_text(encoding="utf-8")

    def settings(self, data):
        (self.project / ".claude").mkdir(exist_ok=True)
        (self.project / ".claude" / "settings.local.json").write_text(json.dumps(data), encoding="utf-8")

    def toml(self, extra=""):
        (self.project / "cortex.toml").write_text(f'version = "{OWN}"\ntheme = "h2g2"\n{extra}', encoding="utf-8")

    def test_the_teams_setting_allows_the_store(self):
        if shutil.which("git"):         # a repository for .gitignore to keep the settings out of
            subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        self.toml("claude_access = true\n")
        proc = self.run_cortex("sync")
        self.assertEqual(self.allowed(), [display(self.home / "versions" / OWN)])
        self.assertIn("Claude Code reads", proc.out)
        if shutil.which("git"):
            self.assertIn(".claude/settings.local.json", (self.project / ".gitignore").read_text(encoding="utf-8"))

    def test_off_by_default(self):
        self.toml()
        self.run_cortex("sync")
        self.assertIsNone(self.allowed())

    def test_a_link_is_allowed_where_it_leads(self):
        # Claude Code checks the path a link resolves to: the store's is the one to allow.
        self.toml('sync = "link"\nclaude_access = true\n')
        self.run_cortex("sync")
        self.assertEqual(self.allowed(), [display(self.home / "versions" / OWN)])

    def test_a_copy_needs_nothing(self):
        self.toml("claude_access = true\n")
        self.run_cortex("sync")
        self.run_cortex("sync", "--copy")
        self.assertEqual(self.allowed(), [])
        self.assertNotIn("claude_entry", self.local())

    def test_the_developer_turns_it_on_and_off_for_themself(self):
        self.toml()
        self.run_cortex("sync", "--claude-access")
        self.assertIn("claude_access = true", self.local())
        self.assertIn(f'claude_entry = "{display(self.home / "versions" / OWN)}"', self.local())
        self.assertEqual(self.allowed(), [display(self.home / "versions" / OWN)])
        self.run_cortex("sync", "--no-claude-access")
        self.assertEqual(self.allowed(), [])
        self.assertNotIn("claude_entry", self.local())
        self.run_cortex("sync")                     # the choice is kept
        self.assertEqual(self.allowed(), [])

    def test_never_set_it_leaves_claude_codes_settings_alone(self):
        # The guide's own advice: answer Claude Code's prompt with "always allow". That entry, and
        # the file, are the developer's while neither file sets claude_access.
        self.toml()
        mine = {"permissions": {"additionalDirectories": [display(self.home / "versions" / OWN)]}}
        self.settings(mine)
        self.run_cortex("sync")
        self.assertEqual(self.allowed(), mine["permissions"]["additionalDirectories"])
        self.run_cortex("sync", "--no-claude-access")
        self.assertEqual(self.allowed(), mine["permissions"]["additionalDirectories"])

    def test_an_entry_for_a_checkout_is_removed_too(self):
        checkout = self.tmp / "checkout"
        for tree in ("agents/personalities/h2g2", "templates", "docs"):
            (checkout / tree).mkdir(parents=True)
        self.toml()
        self.run_cortex("sync", "--from", str(checkout), "--claude-access")
        self.assertEqual(self.allowed(), [display(checkout)])
        self.run_cortex("sync", "--claude-access")               # back to the store: one entry, not two
        self.assertEqual(self.allowed(), [display(self.home / "versions" / OWN)])
        self.run_cortex("sync", "--from", str(checkout))
        self.run_cortex("sync", "--from", str(checkout), "--no-claude-access")
        self.assertEqual(self.allowed(), [])

    def test_a_settings_file_it_cannot_write_is_a_warning(self):
        self.toml("claude_access = true\n")
        (self.project / ".claude" / "settings.local.json").mkdir(parents=True)
        proc = self.run_cortex("sync")
        self.assertIn("warning: .claude/settings.local.json is no file", proc.err)
        self.assertNotIn("Traceback", proc.err)

    def test_init_writes_the_teams_setting(self):
        proc = self.run_cortex("init", "--tool", "claude", "--claude-access")
        self.assertIn("claude_access = true", (self.project / "cortex.toml").read_text(encoding="utf-8"))
        self.assertEqual(self.allowed(), [display(self.home / "versions" / OWN)])
        self.assertNotIn("tip:", proc.out)

    def test_a_second_init_keeps_claude_access_but_for_the_option_given(self):
        self.run_cortex("init", "--tool", "claude", "--claude-access")
        self.run_cortex("init", "--tool", "claude", "--force")
        self.assertIn("claude_access = true", (self.project / "cortex.toml").read_text(encoding="utf-8"))
        self.assertEqual(self.allowed(), [display(self.home / "versions" / OWN)])
        self.run_cortex("init", "--tool", "claude", "--no-claude-access")
        self.assertIn("claude_access = false", (self.project / "cortex.toml").read_text(encoding="utf-8"))
        self.assertEqual(self.allowed(), [])

    def test_init_unattended_says_how(self):
        proc = self.run_cortex("init", "--tool", "claude")
        self.assertIn("tip: Claude Code asks before it reads the spec", proc.out)
        self.assertNotIn("claude_access", (self.project / "cortex.toml").read_text(encoding="utf-8"))
        self.assertIsNone(self.allowed())

    def test_init_for_another_tool_says_nothing_of_claude(self):
        proc = self.run_cortex("init")
        self.assertNotIn("Claude", proc.out)

    def on_a_terminal(self, answer, *args):
        import pty

        shutil.rmtree(self.project)
        self.project.mkdir()
        primary, secondary = pty.openpty()
        try:
            os.write(primary, answer)
            return self.run_cortex("init", "--tool", "claude", *args, stdin=secondary)
        finally:
            os.close(primary)
            os.close(secondary)

    @unittest.skipIf(os.name == "nt", "a pseudo-terminal is POSIX's")
    def test_init_on_a_terminal_asks_and_no_is_the_default(self):
        # The question grants a permission: only yes says yes — Enter, no, and a stdin that ends
        # before any answer (Ctrl-D), say no.
        for answer, expected in ((b"y\n", True), (b"\n", False), (b"n\n", False), (b"\x04", False)):
            with self.subTest(answer=answer):
                proc = self.on_a_terminal(answer)
                self.assertIn("claude_access = true in cortex.toml? [y/N]", proc.out)
                self.assertEqual("claude_access = true" in (self.project / "cortex.toml").read_text(encoding="utf-8"),
                                 expected)

    @unittest.skipIf(os.name == "nt", "a pseudo-terminal is POSIX's")
    def test_init_with_a_copy_neither_asks_nor_advises(self):
        proc = self.on_a_terminal(b"y\n", "--copy")
        self.assertNotIn("Let Claude Code read", proc.out)
        self.assertNotIn("tip:", proc.out)
        self.assertNotIn("claude_access", (self.project / "cortex.toml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
