"""The runtime's view of the cascade (ADR-002 §3.1).

Resolution, merge semantics and lookups live in cortex-core (ADR-007) and are re-exported
here, so every name this module offered keeps working. Prompt assembly lives here.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from cortex_core.resolver import (  # noqa: F401 — re-exported, part of this module's API
    ADDITIVE_SEPARATOR,
    MergeSemantic,
    character_for_role,
    find_role_relpath,
    find_workflow_relpath,
    read_resolved,
    resolve_layer,
    semantic_for,
)

# Separator inserted between two distinct cascade layers when assembling a prompt.
# Matches the ADR-002 §3.1 sketch ("\n\n---\n\n").
LAYER_SEPARATOR = "\n\n---\n\n"


def layers_for(
    role: str,
    theme: Optional[str],
    root: Path,
) -> List[Tuple[str, str]]:
    """Ordered (layer, file) pairs that make up an agent's identity + protocol.

    Order: personality identity → role protocol. Capabilities are resolved separately
    by ``build_system_prompt`` because their selection depends on the project stack
    (``project-context.md``), not on the role name alone.
    """
    pairs: List[Tuple[str, str]] = []

    if theme and theme.strip().lower() not in ("", "none"):
        pairs.append(("personalities", f"{theme}/theme.md"))
        character = character_for_role(role, theme, root)
        if character:
            pairs.append(("personalities", character))

    role_rel = find_role_relpath(role, root)
    if role_rel:
        pairs.append(("roles", role_rel))

    return pairs


def build_system_prompt(
    role: str,
    service: Optional[str],
    theme: Optional[str],
    root: Path,
    capabilities: Optional[Sequence[str]] = None,
) -> str:
    """Assemble the resolved system prompt — additive merge per ADR-001 §3.2 / ADR-002 §3.1.

    ``capabilities`` are cascade-relative paths under ``capabilities/`` (e.g.
    ``"languages/php.md"``); the stack→capability mapping lives upstream (Phase 2).
    """
    parts: List[str] = []
    for layer, file in layers_for(role, theme, root):
        merged = read_resolved(layer, file, service, root)
        if merged.strip():
            parts.append(merged)

    for cap in capabilities or []:
        merged = read_resolved("capabilities", cap, service, root)
        if merged.strip():
            parts.append(merged)

    return LAYER_SEPARATOR.join(parts)
