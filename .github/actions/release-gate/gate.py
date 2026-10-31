"""The release gate (ADR-009 §3.2): the version a pull request into the default branch adds — or
why it may not merge.

It reads the pull request's diff against its base, the two changelogs and the repository's tags and
releases. It passes only when:

1. the pull request adds exactly one release note of a version that has no release yet,
   ``<notes>/X.Y.Z.md``, ``X.Y.Z`` with no suffix. Notes of versions already released do not count;
2. the first section of the changelog after ``[Unreleased]`` is that version's, released, dated
   the day the gate runs, in UTC; the base's changelog has no section for it;
3. the version is higher than every release, and no tag or release, draft included, is named
   after it. Pre-releases do not count;
4. no draft release is waiting: one release is in flight at a time.

The name of the pull request's branch does not matter. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from changelog import DEFAULT_SECTION, first_after_unreleased, has_section, note_version  # noqa: E402
from github import GitHub, GitHubError  # noqa: E402
from semver import Version, highest, is_release  # noqa: E402

@dataclass
class State:
    """The repository's tags and releases, drafts included."""
    tags: List[str]
    releases: List[Dict[str, Any]]


@dataclass
class Verdict:
    version: Optional[str]
    errors: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.version is not None and not self.errors


def decide(added: Sequence[str], head_changelog: str, base_changelog: str, base_ref: str, state: State,
           today: dt.date, section: "re.Pattern[str]", changelog: str = "CHANGELOG.md",
           notes: str = "changelog") -> Verdict:
    """The verdict on a pull request into ``base_ref`` that adds the notes of the versions ``added``."""
    published = {r["tag_name"] for r in state.releases if not r.get("draft")}
    released = set(state.tags) | published
    new = sorted({v for v in added if v not in released}, key=Version)

    # 1. Exactly one new release note.
    if not new:
        return Verdict(None, [f"it adds no release note of a version with no release yet: {notes}/X.Y.Z.md"])
    if len(new) > 1:
        listed = ", ".join(f"{notes}/{v}.md" for v in new)
        return Verdict(None, [f"it adds {len(new)} release notes, {listed}: one release at a time"])
    version = new[0]
    candidate = Version(version)
    verdict = Verdict(version)
    errors = verdict.errors

    # 2. The changelog's section: first, released, dated today; new to the base.
    heading = first_after_unreleased(head_changelog)
    match = section.fullmatch(heading) if heading else None
    if heading is None:
        errors.append(f"{changelog} has no section after [Unreleased]: {version}'s is missing")
    elif match is None:
        errors.append(f"the first section of {changelog} after [Unreleased] is no released section: {heading!r}")
    elif match.group("version") != version:
        errors.append(f"the first section of {changelog} after [Unreleased] is {match.group('version')}'s, not {version}'s")
    elif match.group("date") != today.isoformat():
        errors.append(f"{version} is dated {match.group('date')}, and the gate runs on {today.isoformat()} (UTC): "
                      f"date it the day it merges")
    if has_section(base_changelog, version):
        errors.append(f"the base's {changelog} already has a section for {version}: that version is spent")

    # 3. Higher than every release, and a name nothing has taken.
    top = highest(Version(t) for t in state.tags if is_release(t))
    if top is not None and not candidate > top:
        errors.append(f"{version} is not higher than {top}, the highest release of {base_ref}")
    for release in state.releases:
        if release.get("tag_name") == version or release.get("name") == version:
            kind = "a draft" if release.get("draft") else "a release"
            errors.append(f"{kind} named {version} already exists")
            break

    # 4. One release in flight at a time.
    drafts = sorted(r.get("name") or r.get("tag_name") or "(untitled)" for r in state.releases if r.get("draft"))
    if drafts:
        errors.append(f"a draft is waiting, {', '.join(drafts)}: publish it or delete it — one release is in flight at a time")
    return verdict


# The repository, through git and the API.

def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def added_notes(base: str, head: str, notes: str) -> List[str]:
    """The versions of the notes ``head`` adds against its merge base with ``base``."""
    paths = git("diff", "--name-only", "--no-renames", "--diff-filter=A", f"{base}...{head}", "--", notes).split("\n")
    return [v for v in (note_version(p, notes) for p in paths if p) if v]


def show(commit: str, path: str) -> str:
    try:
        return git("show", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return ""


def fetch_state(github: GitHub) -> State:
    return State(tags=github.tags(), releases=[
        {"tag_name": r.get("tag_name"), "name": r.get("name"), "draft": r.get("draft", False),
         "prerelease": r.get("prerelease", False)} for r in github.releases()])


def annotate(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def report(verdict: Verdict, base_ref: str) -> None:
    if verdict.passed:
        print(f"The release gate passes: this pull request releases {verdict.version} into {base_ref}.")
    else:
        for error in verdict.errors:
            print(f"::error title=release gate::{annotate(error)}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### Release gate\n\n")
            if verdict.passed:
                fh.write(f"This pull request releases **{verdict.version}** into `{base_ref}`.\n")
            else:
                named = f" for **{verdict.version}**" if verdict.version else ""
                fh.write(f"This pull request may not merge into `{base_ref}`{named}:\n\n")
                fh.writelines(f"- {error}\n" for error in verdict.errors)
    output = os.environ.get("GITHUB_OUTPUT")
    if output and verdict.passed:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"version={verdict.version}\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", required=True, help="the base's commit")
    parser.add_argument("--head", required=True, help="the pull request's or the merge group's head")
    parser.add_argument("--base-ref", required=True, help="the branch it merges into")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    parser.add_argument("--notes", default="changelog")
    parser.add_argument("--section", default=DEFAULT_SECTION)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--today", help="YYYY-MM-DD, for tests: the day in UTC otherwise")
    parser.add_argument("--state", help="a JSON file of tags and releases, for tests: the API otherwise")
    args = parser.parse_args(argv)

    today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(dt.timezone.utc).date()
    base_ref = args.base_ref.removeprefix("refs/heads/")
    try:
        if args.state:
            raw = json.loads(Path(args.state).read_text(encoding="utf-8"))
            state = State(raw.get("tags", []), raw.get("releases", []))
        else:
            state = fetch_state(GitHub(args.repository))
        added = added_notes(args.base, args.head, args.notes)
    except (GitHubError, OSError) as error:
        print(f"::error title=release gate::could not read the repository: {annotate(str(error))}")
        return 2
    except subprocess.CalledProcessError as error:
        print(f"::error title=release gate::git could not diff {args.base}...{args.head}: "
              f"{annotate(error.stderr.strip())} — is the history fetched in full?")
        return 2

    verdict = decide(added, show(args.head, args.changelog), show(args.base, args.changelog), base_ref, state,
                     today, re.compile(args.section), args.changelog, args.notes)
    report(verdict, base_ref)
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    sys.exit(main())
