"""The version a release job makes (ADR-009 §3.3, §3.7, §3.11) — or why it makes none.

- **A push** to the default branch, or to a line's branch ``N.x``, releases the version whose note
  it adds between ``before`` and ``after``, of a version with no release yet. Not exactly one: the
  push bypassed the gate, and the job fails, creating nothing. On ``N.x``, the version is ``N``'s,
  and never ``latest``. Its date in the changelog is compared with the commit's day, in UTC: a
  difference is a warning, never a failure, which would spend the version over a date.
- **A run started by hand** cuts a pre-release, ``X.Y.Z-(alpha|beta|rc).N``, from a ``release/**``
  branch. ``X.Y.Z`` is higher than every release of its major version — and than every release,
  while no ``X.x`` branch exists — the pre-release higher than every pre-release of ``X.Y.Z``, its
  name taken by nothing, and no draft waiting.

A draft of the same version is the job's own when it targets the very commit the job releases: a
run that failed left it, and the draft action makes it again. Of another commit, it stops the job.

Writes the release's body: its note, and for a pre-release a banner first, over the note of
``X.Y.Z`` when the branch has it, else the ``[Unreleased]`` section of the changelog.
Standard library only.
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
from changelog import DEFAULT_SECTION, first_after_unreleased, note_version, section_text  # noqa: E402
from github import GitHub, GitHubError  # noqa: E402
from semver import Version, highest, is_prerelease, is_release  # noqa: E402

LINE = re.compile(r"(0|[1-9][0-9]*)\.x")


class Refused(Exception):
    """Why the job makes no release; it creates and changes nothing."""


@dataclass
class State:
    tags: List[str]
    releases: List[Dict[str, Any]]      # tag_name, name, draft, prerelease, target_commitish, id
    branches: List[str] = field(default_factory=list)


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


def for_push(added: Sequence[str], ref: str, default_branch: str, after: str, state: State, attempt: int = 1) -> Plan:
    line = line_of(ref)
    if ref != default_branch and line is None:
        raise Refused(f"a push to {ref} makes no release: only {default_branch} and a line's branch N.x do")
    published = {r["tag_name"] for r in state.releases if not r.get("draft")}
    released = set(state.tags) | published
    new = sorted({v for v in added if v not in released}, key=Version)
    if not new and added and attempt > 1:
        # A second attempt, once the release is published, has nothing left to do. A first one whose notes
        # are all released bypassed the gate — a carry-up with no note of its own, or a tag pushed by hand.
        # A second attempt of such a run says re-run too: its first attempt said why, and stays in the run.
        raise Refused(f"{', '.join(sorted(set(added), key=Version))} is already released: a re-run changes nothing, "
                      f"and a new commit is a new version")
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


def for_dispatch(version: str, ref: str, sha: str, state: State) -> Plan:
    if not ref.startswith("release/"):
        raise Refused(f"a pre-release is cut from a release/** branch, not from {ref}")
    if not is_prerelease(version):
        raise Refused(f"{version!r} is no pre-release as one is cut: X.Y.Z-alpha.N, X.Y.Z-beta.N or X.Y.Z-rc.N")
    candidate = Version(version)
    release = candidate.release
    releases = [Version(t) for t in state.tags if is_release(t)]
    of_major = [r for r in releases if r.major == release.major]
    top = highest(of_major)
    if top is not None and not release > top:
        raise Refused(f"{release} is not higher than {top}, the highest release of {release.major}.x")
    if f"{release.major}.x" not in state.branches:
        top_all = highest(releases)
        if top_all is not None and not release > top_all:
            raise Refused(f"{release} is not higher than {top_all}, and no {release.major}.x branch exists to release it on")
    if version in state.tags:
        raise Refused(f"the tag {version} already exists")
    earlier = highest(v for v in (Version.parse(t) for t in state.tags) if v is not None and v.pre and v.release == release)
    if earlier is not None and not candidate > earlier:
        raise Refused(f"{version} is not higher than {earlier}, already cut for {release}")
    own = _own_or_refuse(state, version, sha)
    waiting = sorted(r.get("name") or r.get("tag_name") for r in state.releases
                     if r.get("draft") and r.get("id") != own)
    if waiting:
        raise Refused(f"a draft is waiting, {', '.join(waiting)}: publish it or delete it — one release is in flight at a time")
    return Plan(version, prerelease=True, latest=False, target=sha, own_draft=own)


def banner(version: str) -> str:
    release = Version(version).release
    return (f"> [!WARNING]\n> **A pre-release of {release}, not for production.** Nothing installs `{version}` unless "
            f"asked for it by its version, and it is never the latest release.\n")


def body(plan: Plan, note: Optional[str], unreleased: Optional[str]) -> str:
    if not plan.prerelease:
        if note is None:
            raise Refused(f"the note of {plan.version} is missing")
        return note
    text = note if note is not None else (unreleased or "")
    return banner(plan.version) + ("\n" + text if text.strip() else "")


def date_warning(changelog: str, section: "re.Pattern[str]", version: str, committed: str, sha: str) -> Optional[str]:
    """Why ``version``'s date in the changelog is not the day, in UTC, its commit was made
    (``committed``, ISO 8601); None when it is, or when the first section is not ``version``'s."""
    heading = first_after_unreleased(changelog)
    match = section.fullmatch(heading) if heading else None
    if match is None or match.group("version") != version:
        return None
    day = dt.datetime.fromisoformat(committed).astimezone(dt.timezone.utc).date().isoformat()
    if match.group("date") == day:
        return None
    return (f"{version} is dated {match.group('date')}, and the commit it releases, {sha[:12]}, was made on {day} "
            f"(UTC): the release goes on, since failing would spend the version over a date")


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
    return State(tags=github.tags(), branches=github.branches(), releases=[
        {k: r.get(k) for k in ("id", "tag_name", "name", "draft", "prerelease", "target_commitish")}
        for r in github.releases()])


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--event", required=True, choices=["push", "workflow_dispatch"])
    parser.add_argument("--ref", required=True, help="the branch, as github.ref_name")
    parser.add_argument("--sha", required=True, help="the commit the job builds: the push's `after`, the branch's head")
    parser.add_argument("--before", default="", help="a push's `before`")
    parser.add_argument("--version", default="", help="the pre-release asked for, by a run started by hand")
    parser.add_argument("--changelog", default="CHANGELOG.md")
    parser.add_argument("--notes", default="changelog")
    parser.add_argument("--section", default=DEFAULT_SECTION)
    parser.add_argument("--body-file", required=True, help="where the release's body is written")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--default-branch", help="for tests: the API's otherwise")
    parser.add_argument("--state", help="a JSON file of tags, releases and branches, for tests: the API otherwise")
    args = parser.parse_args(argv)

    try:
        if args.state:
            raw = json.loads(Path(args.state).read_text(encoding="utf-8"))
            state, default_branch = State(raw.get("tags", []), raw.get("releases", []), raw.get("branches", [])), args.default_branch
        else:
            github = GitHub(args.repository)
            state, default_branch = fetch_state(github), args.default_branch or github.get(github.repo())["default_branch"]
        if args.event == "push":
            added = added_between(args.before, args.sha, args.notes)
            if added is None:
                # Red, not skipped, when a line is cut: a green run would need an output and conditions on
                # the jobs after this one, for an event of once per major version. The message says why.
                raise Refused("the push has no `before` to compare with: a new branch is no release")
            plan = for_push(added, args.ref, default_branch, args.sha, state,
                            attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT") or 1))
        else:
            plan = for_dispatch(args.version.strip(), args.ref, args.sha, state)
        note = show(args.sha, f"{args.notes.rstrip('/')}/{Version(plan.version).release}.md")
        changelog = show(args.sha, args.changelog) or ""
        text = body(plan, note, section_text(changelog, "Unreleased"))
        warning = (date_warning(changelog, re.compile(args.section), plan.version,
                                git("show", "-s", "--format=%cI", args.sha).strip(), args.sha)
                   if args.event == "push" else None)
    except Refused as why:
        print(f"::error title=release version::{why}")
        _summary(f"No release: {why}.")
        return 1
    except (GitHubError, OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        print(f"::error title=release version::could not read the repository: {detail}")
        return 2

    Path(args.body_file).write_text(text, encoding="utf-8")
    if warning:
        print(f"::warning title=release version::{warning}")
    kind = "pre-release" if plan.prerelease else "release"
    own = f"; the draft {plan.own_draft} a failed run left is made again" if plan.own_draft else ""
    print(f"This run makes the {kind} {plan.version}, from {plan.target[:12]}, "
          f"{'the latest' if plan.latest else 'not the latest'}{own}.")
    _summary(f"This run makes the **{kind} {plan.version}**, from `{plan.target[:12]}`, "
             f"{'the latest' if plan.latest else 'not the latest'}{own}."
             + (f"\n\n**Warning:** {warning}." if warning else ""))
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
