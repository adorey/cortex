"""The release gate again, every night (ADR-009 §3.2): a gate that passed the day before would let
a stale date merge, so each night the gate of every open pull request into the default branch, or
into a line's branch ``N.x``, runs again. A date gone stale turns red, and the pull request cannot
merge until it is corrected.

It re-runs the latest run of the gate's workflow for the pull request's head. A pull request whose
gate never ran there, or is running, is listed and left alone. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from github import GitHub, GitHubError, quote  # noqa: E402

LINE = re.compile(r"(0|[1-9][0-9]*)\.x")


@dataclass
class Outcome:
    number: int
    base: str
    what: str
    rerun: bool = False


def targets(base_ref: str, default_branch: str) -> bool:
    return base_ref == default_branch or LINE.fullmatch(base_ref) is not None


def again(github: GitHub, workflow: str) -> List[Outcome]:
    default_branch = github.get(github.repo())["default_branch"]
    outcomes = []
    for pull in github.paginate(github.repo("/pulls?state=open")):
        base = pull["base"]["ref"]
        if not targets(base, default_branch):
            continue
        number, sha = pull["number"], pull["head"]["sha"]
        runs = github.get(github.repo(f"/actions/workflows/{quote(workflow)}/runs?event=pull_request"
                                      f"&head_sha={sha}&per_page=20")).get("workflow_runs", [])
        if not runs:
            outcomes.append(Outcome(number, base, f"no run of {workflow} at {sha[:7]}: left alone"))
            continue
        latest = max(runs, key=lambda run: run["created_at"])
        if latest["status"] != "completed":
            outcomes.append(Outcome(number, base, f"its gate is {latest['status']}: left alone"))
            continue
        try:
            github.request("POST", github.repo(f"/actions/runs/{latest['id']}/rerun"))
        except GitHubError as error:
            outcomes.append(Outcome(number, base, f"could not re-run run {latest['id']}: {error}"))
            continue
        outcomes.append(Outcome(number, base, f"re-ran its gate, run {latest['id']}, which was {latest['conclusion']}", True))
    return outcomes


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workflow", required=True, help="the file name of the gate's workflow")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args(argv)
    try:
        outcomes = again(GitHub(args.repository), args.workflow)
    except GitHubError as error:
        print(f"::error title=release gate, nightly::{error}")
        return 2
    lines = [f"- #{o.number} into `{o.base}`: {o.what}" for o in outcomes] or ["No open pull request into the default branch or a line."]
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### The release gate again, today\n\n" + "\n".join(lines) + "\n")
    failed = [o for o in outcomes if o.what.startswith("could not")]
    for outcome in failed:
        print(f"::warning title=release gate, nightly::#{outcome.number}: {outcome.what}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
