"""Executable cascade resolver — ADR-001 §3.1/§3.2 compiled to code (ADR-002 §3.1).

This is *the singularity* of Cortex: the one part we build rather than buy. It MUST
stay behaviourally identical to ``bin/validate-overlays.sh`` (the existing partial
resolver) — ``tests/test_parity.py`` guards against drift.

Layout consumed (a host-project root):

    {root}/cortex/agents/{layer}/{file}      ← base       (shipped with cortex)
    {root}/agents/{layer}/{file}             ← workspace  (workspace overlay)
    {root}/{service}/agents/{layer}/{file}   ← service    (service overlay)

Resolution is a pure path cascade; merging applies a per-layer semantic.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# Separator inserted between two distinct cascade layers when assembling a prompt.
# Matches the ADR-002 §3.1 sketch ("\n\n---\n\n").
LAYER_SEPARATOR = "\n\n---\n\n"
# Separator inserted between base and overlays of the SAME additive layer.
ADDITIVE_SEPARATOR = "\n\n"

_CHARACTER_LINK = re.compile(r"\[📄\]\(([^)]+)\)")


class MergeSemantic(str, Enum):
    """Per-layer merge mode — ADR-001 §3.2."""

    REPLACEMENT = "replacement"        # workflows: most specific wins entirely
    ADDITIVE = "additive"              # roles / capabilities / personalities: concatenate
    NOT_OVERRIDABLE = "not-overridable"  # personalities/{theme}/characters.md: base only


# --------------------------------------------------------------------------- #
# §3.1 — Resolution algorithm (the cascade)
# --------------------------------------------------------------------------- #
def resolve_layer(
    layer: str,
    file: str,
    service: Optional[str],
    root: Path,
) -> List[Path]:
    """Return existing cascade files for one (layer, file), ordered base → workspace → service.

    Faithful port of ADR-001 §3.1 ``resolveLayer`` and the ADR-002 §3.1 Python sketch.
    The only value that varies between deployments is ``root`` (ADR-002 §3.4).
    """
    root = Path(root)
    candidates = [
        root / "cortex" / "agents" / layer / file,   # base
        root / "agents" / layer / file,               # workspace overlay
    ]
    if service:
        candidates.append(root / service / "agents" / layer / file)  # service overlay
    return [p for p in candidates if p.is_file()]


# --------------------------------------------------------------------------- #
# §3.2 — Merge semantics
# --------------------------------------------------------------------------- #
def semantic_for(layer: str, file: str) -> MergeSemantic:
    """Pick the merge semantic for a (layer, file) pair — ADR-001 §3.2 table."""
    if layer == "workflows":
        return MergeSemantic.REPLACEMENT
    if layer == "personalities" and Path(file).name == "characters.md":
        return MergeSemantic.NOT_OVERRIDABLE
    return MergeSemantic.ADDITIVE


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_resolved(
    layer: str,
    file: str,
    service: Optional[str],
    root: Path,
) -> str:
    """Resolve a (layer, file) through the cascade and merge per its semantic.

    Returns ``""`` if the file exists at no level — callers treat that as "skip".
    """
    paths = resolve_layer(layer, file, service, root)
    if not paths:
        return ""

    semantic = semantic_for(layer, file)
    if semantic is MergeSemantic.REPLACEMENT:
        return _read(paths[-1])              # most specific wins entirely
    if semantic is MergeSemantic.NOT_OVERRIDABLE:
        return _read(paths[0])               # base only — overlays ignored by contract
    return ADDITIVE_SEPARATOR.join(_read(p) for p in paths)  # additive: base → … → service


# --------------------------------------------------------------------------- #
# Helpers for prompt assembly
# --------------------------------------------------------------------------- #
def find_role_relpath(role: str, root: Path) -> Optional[str]:
    """Locate a role's category by globbing the base roles tree.

    Roles live at ``roles/{category}/{role}.md`` but the API payload carries only the
    bare role name. Returns the cascade-relative path ``{category}/{role}.md`` or
    ``None`` if the role ships in no category (e.g. not authored yet).
    """
    base_roles = Path(root) / "cortex" / "agents" / "roles"
    for match in sorted(base_roles.glob(f"*/{role}.md")):
        return f"{match.parent.name}/{role}.md"
    return None


def character_for_role(role: str, theme: str, root: Path) -> Optional[str]:
    """Find the character card assigned to ``role`` in a theme's ``characters.md``.

    ``characters.md`` is NOT overridable (ADR-001 §3.2), so only the base mapping is read.
    Returns the cascade-relative path ``{theme}/{Card}.md`` or ``None``.
    """
    table = read_resolved("personalities", f"{theme}/characters.md", None, root)
    if not table:
        return None
    for line in table.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        role_cell = cells[0].strip().strip("`").strip()
        if role_cell != role:
            continue
        link = _CHARACTER_LINK.search(line)
        if link:
            return f"{theme}/{link.group(1)}"
    return None


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
