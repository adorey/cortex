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

from cortex_core.catalog import capability_catalog  # noqa: F401 — re-exported, part of this module's API

_CONTEXT_FILE = "project-context.md"


def read_project_context(root: Path, service: Optional[str] = None) -> str:
    """The project context, tier by tier: team, developer, then the service's own.

    ADR-006 splits the workspace context in two: the **team** tier ``agents/project-context.md``
    and the **developer** tier ``project-context.md`` at the root, read in that order. When both
    exist, each is labelled by scope (ADR-006 §3.3); with a single tier there is no scope to tell
    apart, and the text stays exactly as it was.
    """
    root = Path(root)
    team = root / "agents" / _CONTEXT_FILE
    developer = root / _CONTEXT_FILE
    parts = []
    if team.is_file() and developer.is_file():
        parts.append("## Team context\n\n" + team.read_text(encoding="utf-8"))
        parts.append("## Developer notes\n\n" + developer.read_text(encoding="utf-8"))
    else:
        for ctx in (team, developer):
            if ctx.is_file():
                parts.append(ctx.read_text(encoding="utf-8"))
    if service and (root / service / _CONTEXT_FILE).is_file():
        parts.append((root / service / _CONTEXT_FILE).read_text(encoding="utf-8"))
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
