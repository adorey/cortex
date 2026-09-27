"""Prompt assembly — an agent's system prompt, built from the cascade (ADR-002 §3.1, ADR-007).

Order: personality identity → role protocol → capabilities → project overview → workspace
services → project context — the editor's bootstrap order for the last three. Each part of the
cascade is resolved and merged per its semantic; distinct parts are joined by ``LAYER_SEPARATOR``.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .resolver import character_for_role, find_role_relpath, read_resolved

# Separator inserted between two distinct cascade layers when assembling a prompt.
# Matches the ADR-002 §3.1 sketch ("\n\n---\n\n").
LAYER_SEPARATOR = "\n\n---\n\n"


def layers_for(
    role: str,
    theme: Optional[str],
    root: Path,
    *,
    base_root: Optional[Path] = None,
) -> List[Tuple[str, str]]:
    """Ordered (layer, file) pairs that make up an agent's identity + protocol.

    Order: personality identity → role protocol. Capabilities are resolved separately
    by ``build_system_prompt`` because their selection depends on the project stack
    (``project-context.md``), not on the role name alone.
    """
    pairs: List[Tuple[str, str]] = []

    if theme and theme.strip().lower() not in ("", "none"):
        pairs.append(("personalities", f"{theme}/theme.md"))
        character = character_for_role(role, theme, root, base_root=base_root)
        if character:
            pairs.append(("personalities", character))

    role_rel = find_role_relpath(role, root, base_root=base_root)
    if role_rel:
        pairs.append(("roles", role_rel))

    return pairs


def build_system_prompt(
    role: str,
    service: Optional[str],
    theme: Optional[str],
    root: Path,
    capabilities: Optional[Sequence[str]] = None,
    *,
    base_root: Optional[Path] = None,
    project_overview: str = "",
    workspace_services: str = "",
    project_context: str = "",
) -> str:
    """Assemble the resolved system prompt — additive merge per ADR-001 §3.2 / ADR-002 §3.1.

    ``capabilities`` are cascade-relative paths under ``capabilities/`` (e.g.
    ``"languages/php.md"``); the stack→capability mapping lives upstream. The project's own
    view, read upstream, closes the prompt: ``project_overview`` (its ``project-overview.md``
    tiers), ``workspace_services`` (the index of the workspace's services) and ``project_context``
    (its ``project-context.md`` tiers), each under its own heading. An empty one is left out.
    """
    parts: List[str] = []
    for layer, file in layers_for(role, theme, root, base_root=base_root):
        merged = read_resolved(layer, file, service, root, base_root=base_root)
        if merged.strip():
            parts.append(merged)

    for cap in capabilities or []:
        merged = read_resolved("capabilities", cap, service, root, base_root=base_root)
        if merged.strip():
            parts.append(merged)

    for heading, text in (("# Project overview", project_overview), ("# Workspace services", workspace_services),
                          ("# Project context", project_context)):
        if text.strip():
            parts.append(f"{heading}\n\n{text}")

    return LAYER_SEPARATOR.join(parts)
