"""The version a release job makes (ADR-009 §3.3, §3.11) — or why it makes none.

A push to the default branch, or to a line's branch ``N.x``, releases the version whose note it
adds between ``before`` and ``after``, of a version with no release yet. Not exactly one: the push
bypassed the gate, and the job fails, creating nothing. On ``N.x``, the version is ``N``'s, and
never ``latest``.

A draft of the same version is the job's own when it targets the very commit the job releases: a
run that failed left it, and the draft action makes it again. Of another commit, it stops the job,
and so does a published release.

Writes the release's body: its note. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from changelog import note_version  # noqa: E402
from github import GitHub, GitHubError  # noqa: E402
from semver import Version, highest, is_release  # noqa: E402

LINE = re.compile(r"(0|[1-9][0-9]*)\.x")


class Refused(Exception):
    """Why the job makes no release; it creates and changes nothing."""


@dataclass
class State:
    tags: List[str]
    releases: List[Dict[str, Any]]      # tag_name, name, draft, prerelease, target_commitish, id


@dataclass
class Plan:
    version: str
    prerelease: bool
    latest: bool
    target: str
    own_draft: Optional[int] = None


def line_of(ref: str) -> Optional[int]:
    match = LINE.fullmatch(ref)
    return int(match.group(1)) if match else None


def _named(state: State, version: str) -> List[Dict[str, Any]]:
    return [r for r in state.releases if r.get("tag_name") == version or r.get("name") == version]


def _own_or_refuse(state: State, version: str, target: str) -> Optional[int]:
    """The id of the job's own draft of ``version``, if any; refused for anything else of that name."""
    own = None
    for release in _named(state, version):
        if not release.get("draft"):
            raise Refused(f"{version} is already published: a new commit is a new version")
        if release.get("target_commitish") != target:
            raise Refused(f"a draft {version} of another commit, {str(release.get('target_commitish'))[:12]}, "
                          f"is waiting: a draft is never rebuilt from another commit")
        own = release.get("id")
    return own


def for_push(added: Sequence[str], ref: str, default_branch: str, after: str, state: State) -> Plan:
    line = line_of(ref)
    if ref != default_branch and line is None:
        raise Refused(f"a push to {ref} makes no release: only {default_branch} and a line's branch N.x do")
    published = {r["tag_name"] for r in state.releases if not r.get("draft")}
    released = set(state.tags) | published
    new = sorted({v for v in added if v not in released}, key=Version)
    if len(new) != 1:
        what = "no release note" if not new else f"{len(new)} release notes ({', '.join(new)})"
        raise Refused(f"the push adds {what} of a version with no release yet: it bypassed the gate, "
                      f"and nothing is released")
    version = new[0]
    candidate = Version(version)
    if line is not None and candidate.major != line:
        raise Refused(f"{version} is not a version of the {line}.x line")
    own = _own_or_refuse(state, version, after)
    top = highest(Version(r["tag_name"]) for r in state.releases
                  if not r.get("draft") and is_release(r.get("tag_name")))
    latest = line is None and (top is None or candidate > top)
    return Plan(version, prerelease=False, latest=latest, target=after, own_draft=own)


def body(plan: Plan, note: Optional[str]) -> str:
    if note is None:
        raise Refused(f"the note of {plan.version} is missing")
    return note


# The repository, through git and the API.

def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def added_between(before: str, after: str, notes: str) -> Optional[List[str]]:
    """The versions of the notes ``after`` adds since ``before``; None with no ``before``."""
    if not before or re.fullmatch(r"0*", before):
        return None
    paths = git("diff", "--name-only", "--no-renames", "--diff-filter=A", before, after, "--", notes).split("\n")
    return [v for v in (note_version(p, notes) for p in paths if p) if v]


def show(commit: str, path: str) -> Optional[str]:
    try:
        return git("show", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return None


def fetch_state(github: GitHub) -> State:
    return State(tags=github.tags(), releases=[
        {k: r.get(k) for k in ("id", "tag_name", "name", "draft", "prerelease", "target_commitish")}
        for r in github.releases()])


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--event", required=True, choices=["push"])
    parser.add_argument("--ref", required=True, help="the branch, as github.ref_name")
    parser.add_argument("--sha", required=True, help="the commit the job builds: the push's `after`, the branch's head")
    parser.add_argument("--before", default="", help="a push's `before`")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    parser.add_argument("--notes", default="changelog")
    parser.add_argument("--body-file", required=True, help="where the release's body is written")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--default-branch", help="for tests: the API's otherwise")
    parser.add_argument("--state", help="a JSON file of tags, releases and branches, for tests: the API otherwise")
    args = parser.parse_args(argv)

    try:
        if args.state:
            raw = json.loads(Path(args.state).read_text(encoding="utf-8"))
            state, default_branch = State(raw.get("tags", []), raw.get("releases", [])), args.default_branch
        else:
            github = GitHub(args.repository)
            state, default_branch = fetch_state(github), args.default_branch or github.get(github.repo())["default_branch"]
        added = added_between(args.before, args.sha, args.notes)
        if added is None:
            raise Refused("the push has no `before` to compare with: a new branch is no release")
        plan = for_push(added, args.ref, default_branch, args.sha, state)
        text = body(plan, show(args.sha, f"{args.notes.rstrip('/')}/{plan.version}.md"))
    except Refused as why:
        print(f"::error title=release version::{why}")
        _summary(f"No release: {why}.")
        return 1
    except (GitHubError, OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        print(f"::error title=release version::could not read the repository: {detail}")
        return 2

    Path(args.body_file).write_text(text, encoding="utf-8")
    kind = "release"
    own = f"; the draft {plan.own_draft} a failed run left is made again" if plan.own_draft else ""
    print(f"This run makes the {kind} {plan.version}, from {plan.target[:12]}, "
          f"{'the latest' if plan.latest else 'not the latest'}{own}.")
    _summary(f"This run makes the **{kind} {plan.version}**, from `{plan.target[:12]}`, "
             f"{'the latest' if plan.latest else 'not the latest'}{own}.")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"version={plan.version}\nprerelease={str(plan.prerelease).lower()}\n"
                     f"latest={str(plan.latest).lower()}\ntarget={plan.target}\nbody-file={args.body_file}\n")
    return 0


def _summary(text: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### Release version\n\n{text}\n")


if __name__ == "__main__":
    sys.exit(main())
