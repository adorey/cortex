"""A changelog in the Keep a Changelog shape, and the release notes beside it.

``CHANGELOG.md`` holds one section per version, newest first, under ``## [Unreleased]``. A
release's section is written final, its date and its name included:

    ## [1.2.2] - 2026-10-31 — On Display _(Released)_

and its note is a file of its own, ``changelog/1.2.2.md``. Both paths and the section's heading
are inputs of the actions: another project names them its own way.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

# The heading of a released section. Its named groups `version` and `date` are what the actions read.
DEFAULT_SECTION = r"## \[(?P<version>[^\]]+)\] - (?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2}) — (?P<name>.+) _\(Released\)_"
UNRELEASED = re.compile(r"## \[Unreleased\]\s*")
# Any second-level section of a version, released or not: `## [X.Y.Z]…`.
ANY_SECTION = re.compile(r"## \[(?P<version>[^\]]+)\].*")
NOTE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.md", re.ASCII)


def headings(text: str) -> List[Tuple[str, str]]:
    """``(label, line)`` of every ``## [label]`` heading, in order."""
    found = []
    for line in text.splitlines():
        match = ANY_SECTION.fullmatch(line.rstrip())
        if match:
            found.append((match.group("version"), line.rstrip()))
    return found


def first_after_unreleased(text: str) -> Optional[str]:
    """The heading line of the first section after ``## [Unreleased]`` — or the first section,
    when there is no ``[Unreleased]`` one; None when there is none."""
    found = headings(text)
    if found and found[0][0] == "Unreleased":
        found = found[1:]
    return found[0][1] if found else None


def has_section(text: str, version: str) -> bool:
    return any(label == version for label, _ in headings(text))


def note_version(path: str, notes_dir: str) -> Optional[str]:
    """``X.Y.Z`` for ``<notes_dir>/X.Y.Z.md``, None for any other path."""
    prefix = notes_dir.rstrip("/") + "/"
    if not path.startswith(prefix):
        return None
    name = path[len(prefix):]
    return name[:-3] if "/" not in name and NOTE.fullmatch(name) else None


def section_text(text: str, label: str) -> Optional[str]:
    """The body of the section ``## [label]``, without its heading, up to the next one."""
    lines, inside, body = text.splitlines(), False, []
    for line in lines:
        match = ANY_SECTION.fullmatch(line.rstrip())
        if match:
            if inside:
                break
            inside = match.group("version") == label
            continue
        if inside:
            body.append(line)
    return "\n".join(body).strip("\n") if inside or body else None
