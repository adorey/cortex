"""Project-context binding — solves "Nuance A" (ADR-002 §3.1, addendum §8).

Capabilities are not listed verbatim in a role; the spec says the Prompt Manager
"cross-references the stack declared in project-context.md". This module makes that
deterministic for the runtime: it intersects the **capability catalog actually present
in the cascade** with the **technologies mentioned in project-context.md**.

Naming-mismatch limitation (assumed debt): matching is a whole-word stem match, so a
capability file ``databases/postgresql.md`` matches the word "postgresql" but not the
alias "Postgres". An alias map is a later refinement; today the catalog stem is the key.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

_CONTEXT_FILE = "project-context.md"


def _capabilities_dirs(root: Path, service: Optional[str]) -> List[Path]:
    root = Path(root)
    dirs = [
        root / "cortex" / "agents" / "capabilities",   # base catalog
        root / "agents" / "capabilities",               # workspace-added capabilities
    ]
    if service:
        dirs.append(root / service / "agents" / "capabilities")  # service-added capabilities
    return dirs


def capability_catalog(root: Path, service: Optional[str] = None) -> List[str]:
    """Cascade-relative paths of every capability available (e.g. ``languages/php.md``).

    Union across base + workspace + service capability dirs; ``README.md`` excluded.
    """
    found = set()
    for cap_dir in _capabilities_dirs(root, service):
        if not cap_dir.is_dir():
            continue
        for md in cap_dir.rglob("*.md"):
            if md.name.lower() == "readme.md":
                continue
            found.add("/".join(md.relative_to(cap_dir).parts))
    return sorted(found)


def read_project_context(root: Path, service: Optional[str] = None) -> str:
    """Concatenate the workspace and (optional) service ``project-context.md`` files."""
    root = Path(root)
    parts = []
    for ctx in (root / _CONTEXT_FILE, (root / service / _CONTEXT_FILE) if service else None):
        if ctx and ctx.is_file():
            parts.append(ctx.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def derive_capabilities(root: Path, service: Optional[str] = None) -> List[str]:
    """Return cascade-relative capability paths whose techno is named in project-context.md.

    Deterministic replacement for the Prompt Manager's manual stack cross-reference.
    Role-based narrowing (a frontend role ignoring DB capabilities) is a later refinement.
    """
    context = read_project_context(root, service).lower()
    if not context.strip():
        return []
    selected = []
    for rel in capability_catalog(root, service):
        techno = Path(rel).stem.lower()
        if re.search(rf"\b{re.escape(techno)}\b", context):
            selected.append(rel)
    return selected
