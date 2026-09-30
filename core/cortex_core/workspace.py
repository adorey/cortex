"""The workspace's layout on disk — what the validator walks and the prompt shows (ADR-007, #88).

``find`` walks a tree the way the validator's script ran ``find``, in name order; ``services`` is the one
discovery of a workspace's services — a folder with a ``project-overview.md``, as cortex init
scaffolds one — for the validator's overlay roots and for the index an agent is shown.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

# Where a workspace keeps its dependencies: never a service, and the bulk of its files.
_DEPENDENCY_TREES = ("node_modules", "vendor", ".venv")
_ALIAS = re.compile(r"<!--\s*@alias:\s*([^\s>]+)\s*-->")


def _is(test, follow_links: bool) -> bool:
    """``entry.is_file`` or ``entry.is_dir``, false when the link cannot be followed — a loop
    (ELOOP), a target out of reach (EACCES) — as ``find -L`` treats it."""
    try:
        return test(follow_symlinks=follow_links)
    except OSError:
        return False


def find(top: str, name: str, *, maxdepth: Optional[int] = None, regular_files: bool = False,
         prune_names: Tuple[str, ...] = (), prune_paths: Tuple[str, ...] = (),
         follow_links: bool = False) -> List[str]:
    """``find TOP [-maxdepth N] -name NAME [-type f]``, without entering the directories below
    ``TOP`` that are named in ``prune_names`` or located at ``prune_paths``.

    Depth first, each directory's entries sorted by name — not in the order the file system
    returns them, as ``find`` prints them: that order is ext4's on one machine, APFS's or NTFS's on
    another, and the report must be the same on every platform (ADR-008 §3.1). The script's
    captured outputs came out sorted too. Pruning looks below ``TOP`` only: what the directories above it are called changes nothing.
    With ``follow_links``, files and directories behind symbolic links count as the resolver
    reads them — ``find -L`` — and, as there, a directory that is one of its own ancestors — a
    link loop — is not entered again, while a second path to the same directory is listed too.
    """
    found: List[str] = []
    pruned = {os.path.normpath(p) for p in prune_paths}

    def visit(directory: str, depth: int, ancestors: frozenset = frozenset()) -> None:
        if follow_links:
            try:
                st = os.stat(directory)
            except OSError:
                return
            if (st.st_dev, st.st_ino) in ancestors:
                return
            ancestors = ancestors | {(st.st_dev, st.st_ino)}
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError:
            return                    # find reports it on stderr, which the script discards
        for entry in entries:
            path = f"{directory}/{entry.name}"
            if (maxdepth is None or depth + 1 <= maxdepth) and fnmatch.fnmatchcase(entry.name, name) \
                    and (not regular_files or _is(entry.is_file, follow_links)):
                found.append(path)
            if _is(entry.is_dir, follow_links) and (maxdepth is None or depth + 1 < maxdepth) \
                    and entry.name not in prune_names and os.path.normpath(path) not in pruned:
                visit(path, depth + 1, ancestors)

    visit(top, 0)
    return found


def same_directory(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normpath(a) == os.path.normpath(b)


def services(project_root: str, base_root: Optional[str] = None) -> List[str]:
    """Every service of the workspace: a folder below the project root, five levels deep at most,
    holding a ``project-overview.md`` — in ``find``'s order, sorted by name.

    Services are looked for outside the base, wherever it is mounted and whatever it is called,
    outside the project root's own ``agents/`` — the cascade's tiers and ADR-006's team files,
    no service — outside any directory named ``cortex`` or ``.git`` below the project root — a
    service may mount its own Cortex — and outside its dependency trees, ``node_modules``,
    ``vendor``, ``.venv``.
    """
    project_root = str(project_root)
    base_root = str(base_root) if base_root is not None else f"{project_root}/cortex"
    found = find(project_root, "project-overview.md", maxdepth=5,
                 prune_names=("cortex", ".git") + _DEPENDENCY_TREES,
                 prune_paths=(base_root, f"{project_root}/agents"))
    return [d for d in (os.path.dirname(f) for f in found) if d != project_root]


def service_index(project_root, base_root=None, active: Optional[str] = None) -> str:
    """The workspace's services as an agent is shown them — one line each, by folder:
    ``- `@alias` — `folder/` — title``, the alias from the overview's ``<!-- @alias: … -->``
    marker (the folder's name without one), the title from its first heading. ``active`` — the
    service of the run — is marked. Empty when the workspace has no service.
    """
    root = Path(project_root)
    lines = []
    for folder in sorted(Path(s).relative_to(root).as_posix() for s in services(str(root), base_root)):
        text = (root / folder / "project-overview.md").read_text(encoding="utf-8", errors="replace")
        alias = _ALIAS.search(text)
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), "")
        line = f"- `@{alias.group(1) if alias else Path(folder).name}` — `{folder}/`" + (f" — {title}" if title else "")
        if active is not None and Path(folder) == Path(active):
            line += " (active)"
        lines.append(line)
    return "\n".join(lines)
