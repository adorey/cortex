"""The commit messages check: each rule of ADR-009 §3.8, then a real history with a merge commit."""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import commit_messages as cm  # noqa: E402

# A pattern of the kind a repository passes: gitmoji, type, optional scope, an issue, the subject.
PATTERN = re.compile(r"(?P<emoji>\S+) (?:feat|fix|docs|chore|ci)(?:\([a-z0-9][a-z0-9./-]*\))?!?: (?:#\d+ )?(?P<subject>\S.*?)(?<!\.)")


def check(message, max_subject=72):
    return cm.check_message(message, PATTERN, max_subject)


class SubjectTests(unittest.TestCase):
    def test_a_subject_that_follows_the_pattern_passes(self):
        for message in ("✨ feat(core): resolve the cascade from a configurable base root",
                        "🐛 fix: #42 keep the order of the cascade",
                        "♻️ chore: rename the templates",
                        "💥 feat(cli)!: rename the command",
                        "📝 docs(adr): mark ADR-001 as Accepted\n"):
            with self.subTest(message=message):
                self.assertEqual(check(message), [])

    def test_a_subject_off_the_pattern_fails(self):
        for message in ("update the docs", "✨ feature: add a role", "✨ feat add a role",
                        "✨ feat(core): end with a period.", "✨feat: no space"):
            with self.subTest(message=message):
                self.assertEqual(check(message), ["its subject line does not follow the pattern"])

    def test_the_emoji_group_holds_one_emoji(self):
        self.assertEqual(check("✨✨ feat: two of them"), ["'✨✨' is not one emoji"])
        self.assertEqual(check(":sparkles: feat: a shortcode"), ["':sparkles:' is not one emoji"])
        for emoji in ("✨", "♻️", "⚡", "👷", "🧑‍💻", "👍🏽", "🇫🇷"):
            with self.subTest(emoji=emoji):
                self.assertTrue(cm.is_one_emoji(emoji))
        for text in ("", "a", "✨a", "✨✨", "‍", "1"):
            with self.subTest(text=text):
                self.assertFalse(cm.is_one_emoji(text))

    def test_the_subject_counts_without_the_issue(self):
        subject = "x" * 72
        self.assertEqual(check(f"✨ feat(core): #123 {subject}"), [])
        self.assertEqual(check(f"✨ feat(core): {subject}y"), ["its subject is 73 characters long, over 72"])

    def test_the_limit_is_an_input(self):
        self.assertEqual(check("✨ feat: twelve chars", max_subject=10), ["its subject is 12 characters long, over 10"])


class BodyTests(unittest.TestCase):
    def test_a_body_fails(self):
        self.assertEqual(check("✨ feat: add a role\n\nIt is a role."), ["it has a body"])

    def test_a_breaking_change_footer_alone_passes(self):
        message = ("💥 feat(roles)!: rename lead-backend\n\nBREAKING CHANGE: host projects must update overlay "
                   "headers\nthat reference lead-backend.md\nto point to senior-backend.md instead.\n")
        self.assertEqual(check(message), [])

    def test_a_body_before_the_footer_fails(self):
        self.assertEqual(check("💥 feat!: rename\n\nWhy we did it.\n\nBREAKING CHANGE: it is renamed"), ["it has a body"])

    def test_a_trailer_fails_and_is_named(self):
        self.assertEqual(check("✨ feat: add a role\n\nCo-Authored-By: Someone <someone@example.com>"),
                         ["it carries a trailer, Co-Authored-By"])
        self.assertEqual(check("✨ feat: add a role\n\nSigned-off-by: Someone <someone@example.com>"),
                         ["it carries a trailer, Signed-off-by"])

    def test_a_trailer_after_the_footer_fails(self):
        self.assertEqual(check("💥 feat!: rename\n\nBREAKING CHANGE: it is renamed\nCo-Authored-By: A <a@example.com>"),
                         ["it carries a trailer, Co-Authored-By"])

    def test_every_reason_is_given(self):
        self.assertEqual(check("bad subject\n\nA body.\n\nCo-Authored-By: A <a@example.com>\nCo-Authored-By: B <b@example.com>"),
                         ["its subject line does not follow the pattern", "it has a body",
                          "it carries a trailer, Co-Authored-By"])


@unittest.skipUnless(shutil.which("git"), "git is needed")
class HistoryTests(unittest.TestCase):
    """A pull request's commits, from a real repository: a merge commit is never checked."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="commit-messages-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.commit("🔧 chore: start", "a")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def commit(self, message, name):
        (self.repo / name).write_text(name, encoding="utf-8")
        self.git("add", name)
        self.git("commit", "-q", "-m", message)

    def run_check(self):
        out = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            with redirect_stdout(out):
                code = cm.main(["--base", self.base, "--head", "HEAD", "--pattern", PATTERN.pattern])
        finally:
            os.chdir(cwd)
        return code, out.getvalue()

    def test_good_commits_and_a_merge_commit_pass(self):
        self.git("checkout", "-q", "-b", "topic")
        self.commit("✨ feat: add b", "b")
        self.git("checkout", "-q", "main")
        self.commit("✨ feat: add c", "c")
        # git's own merge message breaks the pattern: it is not checked.
        self.git("merge", "-q", "--no-ff", "--no-edit", "topic")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("Checked 2 commits, merge commits left out.", out)

    def test_a_bad_commit_is_named_with_its_reason(self):
        self.commit("✨ feat: add b", "b")
        self.commit("add c\n\nCo-Authored-By: A <a@example.com>", "c")
        code, out = self.run_check()
        self.assertEqual(code, 1)
        sha = self.git("rev-parse", "--short=7", "HEAD").strip()
        self.assertIn(f"::error title=commit message {sha}::add c — its subject line does not follow the pattern; "
                      "it carries a trailer, Co-Authored-By", out)
        self.assertIn(f"- {sha} add c", out)

    def test_commits_already_on_the_base_are_not_checked(self):
        self.commit("not checked: already on the base", "b")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.commit("✨ feat: add c", "c")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("Checked 1 commit,", out)

    def test_a_base_git_cannot_find_is_reported(self):
        self.base = "0" * 40
        code, out = self.run_check()
        self.assertEqual(code, 2)
        self.assertIn("is the history fetched in full?", out)


if __name__ == "__main__":
    unittest.main()
