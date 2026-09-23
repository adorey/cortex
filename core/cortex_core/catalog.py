"""The capability catalog — every capability card the cascade offers (ADR-007).

A union across the base, workspace and service capability directories, returned as
cascade-relative paths (``languages/php.md``). ``README.md`` files are not capabilities.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .resolver import _base


def capability_dirs(root: Path, service: Optional[str] = None, *, base_root: Optional[Path] = None) -> List[Path]:
    """The capability directories of the cascade, base first."""
    root = Path(root)
    dirs = [
        _base(root, base_root) / "agents" / "capabilities",   # base catalog
        root / "agents" / "capabilities",                      # workspace-added capabilities
    ]
    if service:
        dirs.append(root / service / "agents" / "capabilities")  # service-added capabilities
    return dirs


def capability_catalog(root: Path, service: Optional[str] = None, *, base_root: Optional[Path] = None) -> List[str]:
    """Cascade-relative paths of every capability available (e.g. ``languages/php.md``)."""
    found = set()
    for cap_dir in capability_dirs(root, service, base_root=base_root):
        if not cap_dir.is_dir():
            continue
        for md in cap_dir.rglob("*.md"):
            if md.name.lower() == "readme.md":
                continue
            found.add("/".join(md.relative_to(cap_dir).parts))
    return sorted(found)
