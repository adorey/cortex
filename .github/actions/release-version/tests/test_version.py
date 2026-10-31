"""The version a release job makes: a push, a run started by hand, a line (ADR-009 §3.3, §3.7, §3.11)."""

import io
import json
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
import version as rv  # noqa: E402

AFTER = "a" * 40
OTHER = "b" * 40


def release(tag, draft=False, target="main", rid=None):
    return {"id": rid or abs(hash(tag)) % 10000, "tag_name": tag, "name": tag, "draft": draft,
            "prerelease": "-" in tag, "target_commitish": target}


def state(*tags, drafts=(), branches=("main",)):
    return rv.State(tags=list(tags), releases=[release(t) for t in tags] + list(drafts), branches=list(branches))


class PushTests(unittest.TestCase):
    STATE = state("1.2.2", "1.3.0")

    def test_a_push_that_adds_one_note_releases_it_as_latest(self):
        plan = rv.for_push(["1.4.0"], "main", "main", AFTER, self.STATE)
        self.assertEqual((plan.version, plan.prerelease, plan.latest, plan.target, plan.own_draft),
                         ("1.4.0", False, True, AFTER, None))

    def test_no_note_or_two_fail(self):
        for added, what in (([], "no release note"), (["1.4.0", "1.5.0"], "2 release notes (1.4.0, 1.5.0)")):
            with self.subTest(added=added):
                with self.assertRaisesRegex(rv.Refused, re.escape(f"the push adds {what} of a version with no release yet")):
                    rv.for_push(added, "main", "main", AFTER, self.STATE)

    def test_a_re_run_once_the_release_is_published_changes_nothing(self):
        # The push's note is 1.3.0's, published since: found by the end-to-end run, which said
        # "it bypassed the gate" here.
        with self.assertRaisesRegex(rv.Refused, "1.3.0 is already released: a re-run changes nothing"):
            rv.for_push(["1.3.0"], "main", "main", AFTER, self.STATE)

    def test_a_draft_of_another_commit_fails(self):
        repo = state("1.3.0", drafts=[release("1.4.0", draft=True, target=OTHER)])
        with self.assertRaisesRegex(rv.Refused, f"a draft 1.4.0 of another commit, {OTHER[:12]}, is waiting"):
            rv.for_push(["1.4.0"], "main", "main", AFTER, repo)

    def test_its_own_draft_is_made_again(self):
        repo = state("1.3.0", drafts=[release("1.4.0", draft=True, target=AFTER, rid=77)])
        self.assertEqual(rv.for_push(["1.4.0"], "main", "main", AFTER, repo).own_draft, 77)

    def test_a_push_to_another_branch_makes_no_release(self):
        with self.assertRaisesRegex(rv.Refused, "a push to release/1.4.0 makes no release"):
            rv.for_push(["1.4.0"], "release/1.4.0", "main", AFTER, self.STATE)


class LineTests(unittest.TestCase):
    STATE = state("1.5.0", "1.5.1", "2.0.0", branches=("main", "1.x"))

    def test_a_push_to_a_line_releases_its_version_not_as_latest(self):
        plan = rv.for_push(["1.6.0"], "1.x", "main", AFTER, self.STATE)
        self.assertEqual((plan.version, plan.latest), ("1.6.0", False))

    def test_another_major_on_a_line_fails(self):
        with self.assertRaisesRegex(rv.Refused, "2.1.0 is not a version of the 1.x line"):
            rv.for_push(["2.1.0"], "1.x", "main", AFTER, self.STATE)

    def test_a_carry_up_makes_the_draft_of_the_new_version_only(self):
        # The merge from 1.x brings 1.5.1's note, published, and adds 2.0.1's.
        plan = rv.for_push(["1.5.1", "2.0.1"], "main", "main", AFTER, self.STATE)
        self.assertEqual((plan.version, plan.latest), ("2.0.1", True))


class DispatchTests(unittest.TestCase):
    STATE = state("1.2.2", "1.3.0-beta.1", branches=("main", "release/adr-009-release-cycle"))

    def test_a_release_candidate_from_a_release_branch(self):
        plan = rv.for_dispatch("1.3.0-rc.1", "release/adr-009-release-cycle", AFTER, self.STATE)
        self.assertEqual((plan.version, plan.prerelease, plan.latest, plan.target), ("1.3.0-rc.1", True, False, AFTER))

    def test_each_refusal(self):
        cases = [
            ("1.3.0-rc.1", "main", self.STATE, "a pre-release is cut from a release/\\*\\* branch, not from main"),
            ("1.3.0-rc1", "release/x", self.STATE, "'1.3.0-rc1' is no pre-release as one is cut"),
            ("1.3.0-alpha.1", "release/x", self.STATE, "1.3.0-alpha.1 is not higher than 1.3.0-beta.1, already cut for 1.3.0"),
            ("1.2.2-rc.1", "release/x", self.STATE, "1.2.2 is not higher than 1.2.2, the highest release of 1.x"),
            ("1.3.0-beta.1", "release/x", self.STATE, "is not higher than 1.3.0-beta.1"),
        ]
        for version, ref, repo, message in cases:
            with self.subTest(version=version, ref=ref):
                with self.assertRaisesRegex(rv.Refused, message):
                    rv.for_dispatch(version, ref, AFTER, repo)

    def test_a_beta_after_an_rc_fails(self):
        repo = state("1.2.2", "1.3.0-rc.1")
        with self.assertRaisesRegex(rv.Refused, "1.3.0-beta.2 is not higher than 1.3.0-rc.1"):
            rv.for_dispatch("1.3.0-beta.2", "release/x", AFTER, repo)

    def test_a_taken_number_fails(self):
        repo = state("1.2.2", drafts=[release("1.3.0-rc.1", draft=True, target=OTHER)])
        with self.assertRaisesRegex(rv.Refused, "a draft 1.3.0-rc.1 of another commit"):
            rv.for_dispatch("1.3.0-rc.1", "release/x", AFTER, repo)

    def test_a_draft_waiting_fails(self):
        repo = state("1.2.2", drafts=[release("1.2.3", draft=True, target=OTHER)])
        with self.assertRaisesRegex(rv.Refused, "a draft is waiting, 1.2.3"):
            rv.for_dispatch("1.3.0-rc.1", "release/x", AFTER, repo)

    def test_an_older_major_needs_its_line(self):
        # 1.6.0-rc.1 while 2.0.0 is out: only from a world where 1.x exists.
        without = state("1.5.0", "2.0.0")
        with self.assertRaisesRegex(rv.Refused, "1.6.0 is not higher than 2.0.0, and no 1.x branch exists"):
            rv.for_dispatch("1.6.0-rc.1", "release/1.6.0", AFTER, without)
        self.assertTrue(rv.for_dispatch("1.6.0-rc.1", "release/1.6.0", AFTER,
                                        state("1.5.0", "2.0.0", branches=("main", "1.x"))).prerelease)

    def test_its_own_draft_is_made_again(self):
        repo = state("1.2.2", drafts=[release("1.3.0-rc.1", draft=True, target=AFTER, rid=5)])
        self.assertEqual(rv.for_dispatch("1.3.0-rc.1", "release/x", AFTER, repo).own_draft, 5)


class BodyTests(unittest.TestCase):
    def test_a_release_is_its_note(self):
        self.assertEqual(rv.body(rv.Plan("1.4.0", False, True, AFTER), "# note", "unreleased"), "# note")

    def test_a_pre_release_opens_with_the_banner_over_the_note(self):
        text = rv.body(rv.Plan("1.3.0-rc.1", True, False, AFTER), "# 1.3.0", "unreleased")
        self.assertTrue(text.startswith("> [!WARNING]\n> **A pre-release of 1.3.0, not for production.**"))
        self.assertTrue(text.endswith("\n# 1.3.0"))

    def test_without_its_note_a_pre_release_takes_the_unreleased_section(self):
        self.assertTrue(rv.body(rv.Plan("1.3.0-alpha.1", True, False, AFTER), None, "### Added\n- x").endswith("### Added\n- x"))


@unittest.skipUnless(shutil.which("git"), "git is needed")
class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="release-version-"))
        self.out = Path(tempfile.mkdtemp(prefix="release-version-out-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.out, ignore_errors=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.write("CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n\n### Added\n- a thing\n\n## [1.3.0] - 2026-11-01 — X _(Released)_\n")
        self.write("changelog/1.3.0.md", "# 1.3.0")
        self.commit()
        self.before = self.head()
        (self.out / "state.json").write_text(json.dumps({"tags": ["1.3.0"], "releases": [release("1.3.0")],
                                                          "branches": ["main"]}), encoding="utf-8")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def write(self, name, text):
        (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / name).write_text(text, encoding="utf-8")

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")

    def head(self):
        return self.git("rev-parse", "HEAD").strip()

    def run_version(self, *args):
        out, cwd = io.StringIO(), os.getcwd()
        output = self.out / "output"
        output.write_text("", encoding="utf-8")
        os.chdir(self.repo)
        saved = os.environ.get("GITHUB_OUTPUT")
        os.environ["GITHUB_OUTPUT"] = str(output)
        try:
            with redirect_stdout(out):
                code = rv.main([*args, "--body-file", str(self.out / "body.md"), "--state", str(self.out / "state.json"),
                                "--default-branch", "main"])
        finally:
            os.chdir(cwd)
            os.environ.pop("GITHUB_OUTPUT") if saved is None else os.environ.__setitem__("GITHUB_OUTPUT", saved)
        return code, out.getvalue(), dict(line.split("=", 1) for line in output.read_text().splitlines() if "=" in line)

    def test_a_push_to_main_that_adds_a_note(self):
        self.write("changelog/1.4.0.md", "# 1.4.0, the note")
        self.commit()
        code, out, outputs = self.run_version("--event", "push", "--ref", "main", "--before", self.before, "--sha", self.head())
        self.assertEqual(code, 0, out)
        self.assertEqual((outputs["version"], outputs["prerelease"], outputs["latest"]), ("1.4.0", "false", "true"))
        self.assertEqual((self.out / "body.md").read_text(encoding="utf-8"), "# 1.4.0, the note")

    def test_a_push_with_no_note_fails(self):
        self.write("README.md", "x")
        self.commit()
        code, out, outputs = self.run_version("--event", "push", "--ref", "main", "--before", self.before, "--sha", self.head())
        self.assertEqual(code, 1)
        self.assertIn("the push adds no release note", out)
        self.assertEqual(outputs, {})

    def test_a_new_branch_push_fails(self):
        code, out, _ = self.run_version("--event", "push", "--ref", "main", "--before", "0" * 40, "--sha", self.head())
        self.assertEqual(code, 1)
        self.assertIn("no `before` to compare with", out)

    def test_a_pre_release_by_hand_takes_the_unreleased_section(self):
        code, out, outputs = self.run_version("--event", "workflow_dispatch", "--ref", "release/1.4.0",
                                              "--version", "1.4.0-rc.1", "--sha", self.head())
        self.assertEqual(code, 0, out)
        self.assertEqual((outputs["version"], outputs["prerelease"], outputs["latest"]), ("1.4.0-rc.1", "true", "false"))
        body = (self.out / "body.md").read_text(encoding="utf-8")
        self.assertIn("A pre-release of 1.4.0", body)
        self.assertTrue(body.endswith("### Added\n- a thing"))


if __name__ == "__main__":
    unittest.main()
