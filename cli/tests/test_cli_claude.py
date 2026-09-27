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
        self.tmp = Path(tempfile.mkdtemp(prefix="cortex-claude-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "project"
        self.root.mkdir()
        self.versions = self.tmp / "home" / "versions"
        (self.versions / "1.0.0").mkdir(parents=True)
        (self.versions / "1.1.0").mkdir()
        self.settings = self.root / ".claude" / "settings.local.json"

    def read(self):
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def test_a_new_file(self):
        said = claude.update(self.root, self.versions, str(self.versions / "1.0.0"))
        self.assertEqual(self.read(), {"permissions": {"additionalDirectories": [str(self.versions / "1.0.0")]}})
        self.assertIn("reads", said)

    def test_the_rest_of_the_file_is_kept(self):
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({"model": "opus", "permissions": {
            "allow": ["Bash(ls:*)"], "additionalDirectories": ["/opt/docs", str(self.versions / "1.0.0")]}}),
            encoding="utf-8")
        claude.update(self.root, self.versions, str(self.versions / "1.1.0"))
        self.assertEqual(self.read(), {"model": "opus", "permissions": {
            "allow": ["Bash(ls:*)"], "additionalDirectories": ["/opt/docs", str(self.versions / "1.1.0")]}})

    def test_nothing_changes_when_it_is_there(self):
        claude.update(self.root, self.versions, str(self.versions / "1.0.0"))
        self.assertIsNone(claude.update(self.root, self.versions, str(self.versions / "1.0.0")))

    def test_turned_off_it_removes_only_the_stores_entries(self):
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({"permissions": {
            "additionalDirectories": ["/opt/docs", str(self.versions / "1.0.0"), "~/elsewhere"]}}), encoding="utf-8")
        claude.update(self.root, self.versions, None)
        self.assertEqual(self.read(), {"permissions": {"additionalDirectories": ["/opt/docs", "~/elsewhere"]}})

    def test_a_file_that_held_only_the_store_goes(self):
        claude.update(self.root, self.versions, str(self.versions / "1.0.0"))
        claude.update(self.root, self.versions, None)
        self.assertFalse(self.settings.exists())

    def test_no_file_and_nothing_to_allow(self):
        self.assertIsNone(claude.update(self.root, self.versions, None))
        self.assertFalse(self.settings.exists())

    def test_a_file_it_cannot_read_is_left_alone(self):
        self.settings.parent.mkdir()
        for text in ("{not json", "[1, 2]", '{"permissions": {"additionalDirectories": "x"}}'):
            with self.subTest(text=text):
                self.settings.write_text(text, encoding="utf-8")
                with self.assertRaises(claude.ClaudeSettingsError):
                    claude.update(self.root, self.versions, str(self.versions / "1.0.0"))
                self.assertEqual(self.settings.read_text(encoding="utf-8"), text)


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
        return json.loads(path.read_text(encoding="utf-8"))["permissions"]["additionalDirectories"]

    def toml(self, extra=""):
        (self.project / "cortex.toml").write_text(f'version = "{OWN}"\ntheme = "h2g2"\n{extra}', encoding="utf-8")

    def test_the_teams_setting_allows_the_store(self):
        self.toml("claude_access = true\n")
        proc = self.run_cortex("sync")
        self.assertEqual(self.allowed(), [display(self.home / "versions" / OWN)])
        self.assertIn("Claude Code reads", proc.out)
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
        self.assertIsNone(self.allowed())

    def test_the_developer_turns_it_on_and_off_for_themself(self):
        self.toml()
        self.run_cortex("sync", "--claude-access")
        self.assertIn("claude_access = true", (self.project / "cortex.local.toml").read_text(encoding="utf-8"))
        self.assertEqual(self.allowed(), [display(self.home / "versions" / OWN)])
        self.run_cortex("sync", "--no-claude-access")
        self.assertIsNone(self.allowed())
        self.run_cortex("sync")                     # the choice is kept
        self.assertIsNone(self.allowed())

    def test_init_writes_the_teams_setting(self):
        proc = self.run_cortex("init", "--tool", "claude", "--claude-access")
        self.assertIn("claude_access = true", (self.project / "cortex.toml").read_text(encoding="utf-8"))
        self.assertEqual(self.allowed(), [display(self.home / "versions" / OWN)])
        self.assertNotIn("tip:", proc.out)

    def test_init_unattended_says_how(self):
        proc = self.run_cortex("init", "--tool", "claude")
        self.assertIn("tip: Claude Code asks before it reads the spec", proc.out)
        self.assertNotIn("claude_access", (self.project / "cortex.toml").read_text(encoding="utf-8"))
        self.assertIsNone(self.allowed())

    def test_init_for_another_tool_says_nothing_of_claude(self):
        proc = self.run_cortex("init")
        self.assertNotIn("Claude", proc.out)

    @unittest.skipIf(os.name == "nt", "a pseudo-terminal is POSIX's")
    def test_init_on_a_terminal_asks(self):
        import pty

        # Enter says yes; no, and a stdin that ends before any answer (Ctrl-D), say no.
        for answer, expected in ((b"\n", True), (b"n\n", False), (b"\x04", False)):
            with self.subTest(answer=answer):
                shutil.rmtree(self.project)
                self.project.mkdir()
                primary, secondary = pty.openpty()
                try:
                    os.write(primary, answer)
                    proc = self.run_cortex("init", "--tool", "claude", stdin=secondary)
                finally:
                    os.close(primary)
                    os.close(secondary)
                self.assertIn("Let Claude Code read the Cortex spec without asking", proc.out)
                self.assertEqual("claude_access = true" in (self.project / "cortex.toml").read_text(encoding="utf-8"),
                                 expected)


if __name__ == "__main__":
    unittest.main()
