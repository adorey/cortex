"""Whether a change concerns a workflow's jobs (ADR-009 §3.10).

A required check must report on every pull request, so a workflow that gates the default branch
has no ``paths`` filter: its first job asks this script whether a changed file matches its paths,
and the jobs that no changed file concerns are skipped — which GitHub counts as passing.

The changed files are those of ``head`` against its merge base with ``base``. With no base to
compare with — the first push of a branch, a run started by hand — everything counts as changed.
Globs: ``*`` stays within a directory, ``**`` crosses directories, ``?`` is one character.
Standard library only.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import List, Optional, Sequence

NO_COMMIT = re.compile(r"0*")


def glob(pattern: str) -> "re.Pattern[str]":
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


def matching(files: Sequence[str], patterns: Sequence[str]) -> List[str]:
    compiled = [glob(p) for p in patterns]
    return [f for f in files if any(c.fullmatch(f) for c in compiled)]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def changed(base: str, head: str) -> Optional[List[str]]:
    """The files ``head`` changes against its merge base with ``base``; None with no base."""
    if not base or NO_COMMIT.fullmatch(base):
        return None
    try:
        merge_base = git("merge-base", base, head).strip()
    except subprocess.CalledProcessError:
        return None    # a base git does not have, after a force push: compare with nothing
    # A path out of ASCII as it is named: git otherwise quotes it, "cli/caf\303\251.py", and no glob matches.
    # A path with a quote, a backslash or a control character stays quoted: this repository has none.
    return [line for line in git("-c", "core.quotePath=false", "diff", "--name-only", "--no-renames", merge_base, head).split("\n") if line]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="")
    parser.add_argument("--head", required=True)
    parser.add_argument("--paths", required=True, help="one glob per line")
    args = parser.parse_args(argv)
    patterns = [p.strip() for p in args.paths.splitlines() if p.strip() and not p.strip().startswith("#")]

    files = changed(args.base, args.head)
    if files is None:
        run, why = True, "no base to compare with: every job runs"
    else:
        hits = matching(files, patterns)
        run = bool(hits)
        why = (f"{len(hits)} of {len(files)} changed files concern these jobs, {hits[0]} first" if hits
               else f"none of the {len(files)} changed files concerns these jobs: they are skipped")
    print(why)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"run={'true' if run else 'false'}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"### Changes\n\n{why[0].upper()}{why[1:]}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
