"""Cascade resolution — ADR-001 §3.1 and §3.2 compiled to code (ADR-002 §3.1, ADR-007).

It must stay behaviourally identical to ``bin/validate-overlays.sh`` until ADR-007 phase 3
turns that script into a shim over this package; ``runtime/tests/test_parity.py`` guards the
pair meanwhile.

Layout consumed:

    {base_root}/agents/{layer}/{file}              ← base       (default base_root: {project_root}/cortex)
    {project_root}/agents/{layer}/{file}           ← workspace  (workspace overlay)
    {project_root}/{service}/agents/{layer}/{file} ← service    (service overlay)

Resolution is a pure path cascade; merging applies a per-layer semantic.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import List, Optional

# Separator inserted between base and overlays of the SAME additive layer.
ADDITIVE_SEPARATOR = "\n\n"

_CHARACTER_LINK = re.compile(r"\[📄\]\(([^)]+)\)")


class MergeSemantic(str, Enum):
    """Per-layer merge mode — ADR-001 §3.2."""

    REPLACEMENT = "replacement"        # workflows: most specific wins entirely
    ADDITIVE = "additive"              # roles / capabilities / personalities: concatenate
    NOT_OVERRIDABLE = "not-overridable"  # personalities/{theme}/characters.md: base only


def default_base_root(project_root: Path) -> Path:
    """Where the base lives when nothing says otherwise: a Cortex checkout at ``{project_root}/cortex``."""
    return Path(project_root) / "cortex"


def _base(project_root: Path, base_root: Optional[Path]) -> Path:
    return Path(base_root) if base_root is not None else default_base_root(project_root)


# --------------------------------------------------------------------------- #
# §3.1 — Resolution algorithm (the cascade)
# --------------------------------------------------------------------------- #
def resolve_layer(
    layer: str,
    file: str,
    service: Optional[str],
    root: Path,
    *,
    base_root: Optional[Path] = None,
) -> List[Path]:
    """Return existing cascade files for one (layer, file), ordered base → workspace → service.

    Faithful port of ADR-001 §3.1 ``resolveLayer``. ``root`` is the project root;
    ``base_root`` locates the base (ADR-007 §3.1).
    """
    root = Path(root)
    candidates = [
        _base(root, base_root) / "agents" / layer / file,   # base
        root / "agents" / layer / file,                      # workspace overlay
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
    *,
    base_root: Optional[Path] = None,
) -> str:
    """Resolve a (layer, file) through the cascade and merge per its semantic.

    Returns ``""`` if the file exists at no level — callers treat that as "skip".
    """
    paths = resolve_layer(layer, file, service, root, base_root=base_root)
    if not paths:
        return ""

    semantic = semantic_for(layer, file)
    if semantic is MergeSemantic.REPLACEMENT:
        return _read(paths[-1])              # most specific wins entirely
    if semantic is MergeSemantic.NOT_OVERRIDABLE:
        return _read(paths[0])               # base only — overlays ignored by contract
    return ADDITIVE_SEPARATOR.join(_read(p) for p in paths)  # additive: base → … → service


# --------------------------------------------------------------------------- #
# Lookups — the API payload carries bare names, the cascade stores categorised paths
# --------------------------------------------------------------------------- #
def find_role_relpath(role: str, root: Path, *, base_root: Optional[Path] = None) -> Optional[str]:
    """Locate a role's category by globbing the base roles tree.

    Roles live at ``roles/{category}/{role}.md`` but the API payload carries only the
    bare role name. Returns the cascade-relative path ``{category}/{role}.md`` or
    ``None`` if the role ships in no category (e.g. not authored yet).
    """
    base_roles = _base(root, base_root) / "agents" / "roles"
    for match in sorted(base_roles.glob(f"*/{role}.md")):
        return f"{match.parent.name}/{role}.md"
    return None


def find_workflow_relpath(workflow: str, root: Path, *, base_root: Optional[Path] = None) -> Optional[str]:
    """Locate a workflow's category by globbing the base workflows tree.

    Like roles, workflows live at ``workflows/{category}/{workflow}.md`` but the API
    payload carries only the bare name. Returns ``{category}/{workflow}.md`` or ``None``.
    """
    base_wf = _base(root, base_root) / "agents" / "workflows"
    for match in sorted(base_wf.glob(f"*/{workflow}.md")):
        return f"{match.parent.name}/{workflow}.md"
    return None


def character_for_role(
    role: str, theme: str, root: Path, *, base_root: Optional[Path] = None
) -> Optional[str]:
    """Find the character card assigned to ``role`` in a theme's ``characters.md``.

    ``characters.md`` is NOT overridable (ADR-001 §3.2), so only the base mapping is read.
    Returns the cascade-relative path ``{theme}/{Card}.md`` or ``None``.
    """
    table = read_resolved("personalities", f"{theme}/characters.md", None, root, base_root=base_root)
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
