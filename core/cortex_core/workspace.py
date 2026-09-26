"""The workspace's layout on disk — what the validator walks and the prompt shows (ADR-007, #88).

``find`` walks a tree the way the validator's script ran ``find``; ``services`` is the one
discovery of a workspace's services — a folder with a ``project-overview.md``, as setup.sh
scaffolds one — for the validator's overlay roots and for the index an agent is shown.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

_ALIAS = re.compile(r"<!--\s*@alias:\s*([^\s>]+)\s*-->")


def find(top: str, name: str, *, maxdepth: Optional[int] = None, regular_files: bool = False,
         prune_names: Tuple[str, ...] = (), prune_paths: Tuple[str, ...] = (),
         follow_links: bool = False) -> List[str]:
    """``find TOP [-maxdepth N] -name NAME [-type f]``, in ``find``'s order, without entering the
    directories below ``TOP`` that are named in ``prune_names`` or located at ``prune_paths``.

    Depth first, each directory's entries in the order the file system returns them — the
    order ``find`` prints, so the report lists files in the same sequence as the script did.
    Pruning looks below ``TOP`` only: what the directories above it are called changes nothing.
    With ``follow_links``, files and directories behind symbolic links count as the resolver
    reads them — ``find -L`` — and a directory reached twice, a link loop, is entered once.
    """
    found: List[str] = []
    pruned = {os.path.normpath(p) for p in prune_paths}
    entered = set()

    def visit(directory: str, depth: int) -> None:
        if follow_links:
            try:
                key = (os.stat(directory).st_dev, os.stat(directory).st_ino)
            except OSError:
                return
            if key in entered:
                return
            entered.add(key)
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return                    # find reports it on stderr, which the script discards
        for entry in entries:
            path = f"{directory}/{entry.name}"
            if (maxdepth is None or depth + 1 <= maxdepth) and fnmatch.fnmatchcase(entry.name, name) \
                    and (not regular_files or entry.is_file(follow_symlinks=follow_links)):
                found.append(path)
            if entry.is_dir(follow_symlinks=follow_links) and (maxdepth is None or depth + 1 < maxdepth) \
                    and entry.name not in prune_names and os.path.normpath(path) not in pruned:
                visit(path, depth + 1)

    visit(top, 0)
    return found


def same_directory(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normpath(a) == os.path.normpath(b)


def services(project_root: str, base_root: Optional[str] = None) -> List[str]:
    """Every service of the workspace: a folder below the project root, five levels deep at most,
    holding a ``project-overview.md`` — in ``find``'s order.

    Services are looked for outside the base, wherever it is mounted and whatever it is called,
    and outside any directory named ``cortex`` or ``.git`` below the project root — a service may
    mount its own Cortex.
    """
    project_root = str(project_root)
    base_root = str(base_root) if base_root is not None else f"{project_root}/cortex"
    found = find(project_root, "project-overview.md", maxdepth=5,
                 prune_names=("cortex", ".git"), prune_paths=(base_root,))
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
