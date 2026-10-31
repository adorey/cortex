"""The commit messages check (ADR-009 §3.8): every commit a pull request brings, against the rules
of the repository that calls it.

Each commit, merge commits excluded since GitHub writes those, must:

- have a subject line that matches ``--pattern``, a Python regular expression. Its named group
  ``subject`` is the part whose length counts, and a group named ``emoji``, when the pattern has
  one, must hold exactly one emoji;
- keep that ``subject`` within ``--max-subject-length`` characters;
- have no body, except a ``BREAKING CHANGE:`` footer;
- carry no trailer: no ``Co-Authored-By``, no ``Signed-off-by``, nothing else.

The grammar of the subject is not checked: no script can tell an imperative from a statement.
Every commit that fails is listed, with every reason. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import unicodedata
from typing import List, Optional, Sequence, Tuple

BREAKING = re.compile(r"BREAKING[ -]CHANGE: \S")
# A trailer as git writes one: a token, a colon, a value — `Co-Authored-By: …`.
TRAILER = re.compile(r"([A-Za-z][A-Za-z0-9-]*): \S")
SKIN_TONES = range(0x1F3FB, 0x1F400)
REGIONAL_INDICATORS = range(0x1F1E6, 0x1F200)


def is_one_emoji(text: str) -> bool:
    """``text`` is a single emoji: one pictograph, with its presentation selector, its skin tone,
    or the zero-width joins of one sequence — or a flag, two regional indicators."""
    text = text.replace("\ufe0f", "").replace("\ufe0e", "")
    if not text:
        return False
    if len(text) == 2 and all(ord(c) in REGIONAL_INDICATORS for c in text):
        return True
    for part in text.split("\u200d"):
        if not part:
            return False
        base, rest = part[0], part[1:]
        if unicodedata.category(base) != "So" or ord(base) in REGIONAL_INDICATORS:
            return False
        if rest and not (len(rest) == 1 and ord(rest) in SKIN_TONES):
            return False
    return True


def check_message(message: str, pattern: "re.Pattern[str]", max_subject: int) -> List[str]:
    """Why ``message`` breaks the rules: an empty list when it does not."""
    reasons: List[str] = []
    lines = message.replace("\r\n", "\n").rstrip("\n").split("\n")
    first = lines[0]
    match = pattern.fullmatch(first)
    if match is None:
        reasons.append("its subject line does not follow the pattern")
    else:
        groups = match.groupdict()
        if "emoji" in groups and not is_one_emoji(groups["emoji"] or ""):
            reasons.append(f"{groups['emoji']!r} is not one emoji")
        subject = groups.get("subject")
        if subject is not None and len(subject) > max_subject:
            reasons.append(f"its subject is {len(subject)} characters long, over {max_subject}")

    in_footer = body = False
    for line in lines[1:]:
        if not line.strip():
            continue
        if BREAKING.match(line):
            in_footer = True
            continue
        trailer = TRAILER.match(line)
        if trailer:
            reasons.append(f"it carries a trailer, {trailer.group(1)}")
            in_footer = False
            continue
        if in_footer:
            continue   # the footer's description runs on
        if not body:
            reasons.append("it has a body")
            body = True
    return _unique(reasons)


def _unique(items: Sequence[str]) -> List[str]:
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def commits(base: str, head: str) -> List[Tuple[str, str]]:
    """``(sha, message)`` of every commit in ``head`` and not in ``base``, oldest first, merge
    commits left out."""
    shas = git("rev-list", "--no-merges", "--reverse", f"{base}..{head}").split()
    return [(sha, git("log", "-1", "--format=%B", sha)) for sha in shas]


def annotate(text: str) -> str:
    # Workflow commands take no raw newline or percent sign in their message.
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--max-subject-length", type=int, default=72)
    args = parser.parse_args(argv)

    try:
        pattern = re.compile(args.pattern)
    except re.error as error:
        print(f"::error title=commit messages::the pattern is no regular expression: {annotate(str(error))}")
        return 2
    try:
        found = commits(args.base, args.head)
    except subprocess.CalledProcessError as error:
        print(f"::error title=commit messages::git could not list {args.base}..{args.head}: "
              f"{annotate(error.stderr.strip())} — is the history fetched in full?")
        return 2

    failures = []
    for sha, message in found:
        reasons = check_message(message, pattern, args.max_subject_length)
        if reasons:
            failures.append((sha, message.split("\n", 1)[0], reasons))

    lines = [f"Checked {len(found)} commit{'s' if len(found) != 1 else ''}, merge commits left out."]
    for sha, subject, reasons in failures:
        lines.append(f"- {sha[:7]} {subject}")
        lines.extend(f"    - {reason}" for reason in reasons)
        print(f"::error title=commit message {sha[:7]}::{annotate(subject)} — {annotate('; '.join(reasons))}")
    print("\n".join(lines))

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### Commit messages\n\n")
            if not failures:
                fh.write(f"{lines[0]} Every one follows the rules.\n")
            else:
                fh.write(f"{lines[0]} {len(failures)} break the rules:\n\n| Commit | Subject | Why |\n|---|---|---|\n")
                for sha, subject, reasons in failures:
                    cell = subject.replace("|", "\\|")
                    fh.write(f"| `{sha[:7]}` | {cell} | {'; '.join(reasons)} |\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
