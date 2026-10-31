"""The release gate, rule by rule (ADR-009 §3.2, §3.11) — on fixtures, then on a real history."""

import datetime as dt
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
import gate  # noqa: E402
from changelog import DEFAULT_SECTION  # noqa: E402

TODAY = dt.date(2026, 11, 3)
SECTION = re.compile(DEFAULT_SECTION)


def changelog(*sections):
    """A CHANGELOG.md with these sections under [Unreleased]: ("1.4.0", "2026-11-03") or a raw heading."""
    lines = ["# Changelog", "", "## [Unreleased]", ""]
    for item in sections:
        heading = item if isinstance(item, str) else f"## [{item[0]}] - {item[1]} — A Name _(Released)_"
        lines += [heading, "[Full notes](changelog/x.md)", "", "### Fixed", "- something", ""]
    return "\n".join(lines)


def release(tag, draft=False, prerelease=None):
    return {"tag_name": tag, "name": tag, "draft": draft, "prerelease": "-" in tag if prerelease is None else prerelease}


def state(*tags, drafts=()):
    return gate.State(tags=list(tags), releases=[release(t) for t in tags] + [release(d, draft=True) for d in drafts])


def decide(added, head, base, base_ref="main", repo=None, today=TODAY):
    return gate.decide(added, head, base, base_ref, repo or state("1.2.2", "1.3.0"), today, SECTION)


BASE = changelog(("1.3.0", "2026-11-01"), ("1.2.2", "2026-10-31"))
HEAD = changelog(("1.4.0", "2026-11-03"), ("1.3.0", "2026-11-01"), ("1.2.2", "2026-10-31"))


class PassingTests(unittest.TestCase):
    def test_a_release_pull_request_passes_and_names_its_version(self):
        verdict = decide(["1.4.0"], HEAD, BASE)
        self.assertEqual(verdict.errors, [])
        self.assertTrue(verdict.passed)
        self.assertEqual(verdict.version, "1.4.0")

    def test_a_major_version_passes(self):
        head = changelog(("2.0.0", "2026-11-03"), ("1.3.0", "2026-11-01"))
        self.assertTrue(decide(["2.0.0"], head, BASE).passed)

    def test_the_first_release_of_a_repository_passes(self):
        head = changelog(("0.1.0", "2026-11-03"))
        self.assertTrue(decide(["0.1.0"], head, changelog(), repo=state()).passed)


class NotesTests(unittest.TestCase):
    def test_no_release_note_fails(self):
        verdict = decide([], HEAD, BASE)
        self.assertIsNone(verdict.version)
        self.assertEqual(verdict.errors, ["it adds no release note of a version with no release yet: changelog/X.Y.Z.md"])

    def test_two_release_notes_fail(self):
        verdict = decide(["1.4.0", "1.5.0"], HEAD, BASE)
        self.assertIsNone(verdict.version)
        self.assertEqual(verdict.errors, ["it adds 2 release notes, changelog/1.4.0.md, changelog/1.5.0.md: one release at a time"])

    def test_a_note_of_a_released_version_does_not_count(self):
        # Only 1.3.0's note, already released: nothing new.
        self.assertIsNone(decide(["1.3.0"], HEAD, BASE).version)


class ChangelogTests(unittest.TestCase):
    def test_the_first_section_of_another_version_fails(self):
        head = changelog(("1.3.0", "2026-11-01"), ("1.4.0", "2026-11-03"))
        self.assertIn("the first section of CHANGELOG.md after [Unreleased] is 1.3.0's, not 1.4.0's",
                      decide(["1.4.0"], head, BASE).errors)

    def test_an_unreleased_heading_fails(self):
        head = changelog("## [1.4.0] - 2026-11-03 — A Name", ("1.3.0", "2026-11-01"))
        self.assertIn("is no released section", decide(["1.4.0"], head, BASE).errors[0])

    def test_no_section_at_all_fails(self):
        self.assertEqual(decide(["1.4.0"], changelog(), BASE).errors[0],
                         "CHANGELOG.md has no section after [Unreleased]: 1.4.0's is missing")

    def test_a_section_the_base_already_has_fails(self):
        base = changelog(("1.4.0", "2026-11-02"), ("1.3.0", "2026-11-01"))
        self.assertIn("the base's CHANGELOG.md already has a section for 1.4.0: that version is spent",
                      decide(["1.4.0"], HEAD, base).errors)

    def test_a_release_dated_another_day_fails(self):
        verdict = decide(["1.4.0"], HEAD, BASE, today=dt.date(2026, 11, 4))
        self.assertEqual(verdict.errors, ["1.4.0 is dated 2026-11-03, and the gate runs on 2026-11-04 (UTC): "
                                          "date it the day it merges"])


class VersionTests(unittest.TestCase):
    def test_a_version_not_higher_than_every_release_fails(self):
        head = changelog(("1.2.3", "2026-11-03"), ("1.3.0", "2026-11-01"))
        self.assertIn("1.2.3 is not higher than 1.3.0, the highest release of main", decide(["1.2.3"], head, BASE).errors)

    def test_a_published_prerelease_of_a_later_major_does_not_block(self):
        verdict = decide(["1.4.0"], HEAD, BASE, repo=state("1.2.2", "1.3.0", "2.0.0-alpha.1"))
        self.assertTrue(verdict.passed, verdict.errors)

    def test_precedence_is_semver_not_sort_v(self):
        # 1.10.0 is higher than 1.9.0, which sorts after it as text.
        head = changelog(("1.10.0", "2026-11-03"), ("1.9.0", "2026-11-01"))
        self.assertTrue(decide(["1.10.0"], head, changelog(("1.9.0", "2026-11-01")), repo=state("1.9.0")).passed)

    def test_a_tag_pushed_by_hand_takes_the_version(self):
        # A tag 1.4.0 without its release: the note's version counts as released, nothing is new.
        verdict = decide(["1.4.0"], HEAD, BASE, repo=state("1.2.2", "1.3.0", "1.4.0"))
        self.assertIsNone(verdict.version)

    def test_a_draft_of_the_same_name_takes_it(self):
        verdict = decide(["1.4.0"], HEAD, BASE, repo=state("1.2.2", "1.3.0", drafts=["1.4.0"]))
        self.assertIn("a draft named 1.4.0 already exists", verdict.errors)

    def test_a_draft_waiting_fails(self):
        verdict = decide(["1.4.0"], HEAD, BASE, repo=state("1.2.2", "1.3.0", drafts=["1.3.1"]))
        self.assertEqual(verdict.errors, ["a draft is waiting, 1.3.1: publish it or delete it — one release is in flight at a time"])


class LineTests(unittest.TestCase):
    """A fixture with a published 2.0.0 on main and 1.x beside it (ADR-009 §3.11)."""

    REPO = state("1.4.0", "1.5.1", "2.0.0", "2.0.0-alpha.1")
    ONE_BASE = changelog(("1.5.1", "2026-11-01"), ("1.4.0", "2026-10-01"))
    ONE_HEAD = changelog(("1.6.0", "2026-11-03"), ("1.5.1", "2026-11-01"), ("1.4.0", "2026-10-01"))

    def test_a_minor_of_the_line_passes_into_its_branch(self):
        verdict = decide(["1.6.0"], self.ONE_HEAD, self.ONE_BASE, "1.x", self.REPO)
        self.assertTrue(verdict.passed, verdict.errors)
        self.assertEqual(verdict.version, "1.6.0")

    def test_the_same_into_main_fails(self):
        verdict = decide(["1.6.0"], self.ONE_HEAD, self.ONE_BASE, "main", self.REPO)
        self.assertEqual(verdict.errors, ["1.6.0 is not higher than 2.0.0, the highest release of main"])

    def test_another_major_into_a_line_fails(self):
        head = changelog(("2.1.0", "2026-11-03"), ("1.5.1", "2026-11-01"))
        self.assertIn("2.1.0 is not a version of the 1.x line", decide(["2.1.0"], head, self.ONE_BASE, "1.x", self.REPO).errors)

    def test_a_version_below_the_line_fails(self):
        head = changelog(("1.5.0", "2026-11-03"), ("1.5.1", "2026-11-01"))
        self.assertIn("1.5.0 is not higher than 1.5.1, the highest release of the 1.x line",
                      decide(["1.5.0"], head, self.ONE_BASE, "1.x", self.REPO).errors)

    def test_a_fix_carried_up_from_the_line_passes_into_main(self):
        # The pull request from 1.x into main brings 1.5.1's note, released, and adds 2.0.1's.
        base = changelog(("2.0.0", "2026-10-20"), ("1.4.0", "2026-10-01"))
        head = changelog(("2.0.1", "2026-11-03"), ("2.0.0", "2026-10-20"), ("1.5.1", "2026-11-01"), ("1.4.0", "2026-10-01"))
        verdict = decide(["1.5.1", "2.0.1"], head, base, "main", self.REPO)
        self.assertTrue(verdict.passed, verdict.errors)
        self.assertEqual(verdict.version, "2.0.1")

    def test_a_line_number_is_a_branch_name_only(self):
        self.assertEqual(gate.line_of("1.x"), 1)
        self.assertEqual(gate.line_of("12.x"), 12)
        for ref in ("main", "release/1.x", "1.2.x", "01.x", "x"):
            with self.subTest(ref=ref):
                self.assertIsNone(gate.line_of(ref))


class ActionTests(unittest.TestCase):
    def test_the_action_reads_the_section_the_lib_does(self):
        action = (Path(__file__).resolve().parents[1] / "action.yml").read_text(encoding="utf-8")
        line = next(l for l in action.splitlines() if l.strip().startswith("default: '## "))
        self.assertEqual(line.strip()[len("default: '"):-1].replace("''", "'"), DEFAULT_SECTION)


@unittest.skipUnless(shutil.which("git"), "git is needed")
class HistoryTests(unittest.TestCase):
    """main(): the notes a branch adds, read from a real history, the state from a file."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="release-gate-"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.write("CHANGELOG.md", BASE)
        self.write("changelog/1.3.0.md", "# 1.3.0")
        self.commit("start")
        # Outside the repository: `git add -A` would commit it, and a checkout take it away.
        outside = Path(tempfile.mkdtemp(prefix="release-gate-state-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        self.state = outside / "state.json"
        self.state.write_text(json.dumps({"tags": ["1.2.2", "1.3.0"], "releases": [release("1.3.0")]}), encoding="utf-8")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def run_gate(self, base="main", head="topic", today="2026-11-03", base_ref="main"):
        out = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            with redirect_stdout(out):
                code = gate.main(["--base", base, "--head", head, "--base-ref", base_ref, "--today", today,
                                  "--state", str(self.state)])
        finally:
            os.chdir(cwd)
        return code, out.getvalue()

    def test_a_release_branch_passes_and_names_its_version(self):
        self.git("checkout", "-q", "-b", "topic")
        self.write("changelog/1.4.0.md", "# 1.4.0")
        self.write("CHANGELOG.md", HEAD)
        self.commit("release 1.4.0")
        # main moves on meanwhile: what the branch adds is read against the merge base.
        self.git("checkout", "-q", "main")
        self.write("README.md", "moved on")
        self.commit("elsewhere")
        code, out = self.run_gate()
        self.assertEqual(code, 0, out)
        self.assertIn("this pull request releases 1.4.0 into main", out)

    def test_a_branch_with_no_note_fails(self):
        self.git("checkout", "-q", "-b", "topic")
        self.write("README.md", "docs only")
        self.commit("docs")
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("::error title=release gate::it adds no release note", out)

    def test_a_note_edited_rather_than_added_does_not_count(self):
        self.git("checkout", "-q", "-b", "topic")
        self.write("changelog/1.3.0.md", "# 1.3.0, edited")
        self.commit("edit")
        self.assertEqual(self.run_gate()[0], 1)

    def test_a_base_git_cannot_find_is_reported(self):
        self.assertEqual(self.run_gate(base="0" * 40, head="main")[0], 2)


if __name__ == "__main__":
    unittest.main()
