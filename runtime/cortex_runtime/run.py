"""The /run contract, framework-agnostic — ADR-002 §3.2.

``resolve_run`` is the deterministic core (ADR-002 §8.1 pre-resolution): given a request
and a bound ``root`` (§3.4), it assembles everything the agentic loop (Phase 3) needs —
the system prompt (identity), the derived capabilities, and the advisory workflow recipe.

This module imports no web framework on purpose: the API layer (api.py) is a thin shell
over it, so the contract stays testable with zero install.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .context import derive_capabilities
from .resolver import build_system_prompt, find_workflow_relpath, layers_for, read_resolved


@dataclass
class RunRequest:
    """The generic /run payload (ADR-002 §3.2). ``model`` is optional."""

    workspace: str
    role: str
    service: Optional[str] = None
    workflow: Optional[str] = None
    input: Dict[str, Any] = field(default_factory=dict)
    model: Optional[str] = None


@dataclass
class ResolvedRun:
    """Everything the agentic loop needs, pre-resolved (identity given, work improvised)."""

    system_prompt: str
    capabilities: List[str]
    workflow: Optional[str]              # advisory recipe text, or None
    layers: List[Tuple[str, str]]        # (layer, file) pairs that built the identity
    model: Optional[str]


def resolve_run(req: RunRequest, root: Path, theme: Optional[str] = None) -> ResolvedRun:
    """Compile a request into a resolved bundle. ``theme`` is the workspace's active theme
    (deployment config — NOT the gitignored local ``.active-theme`` marker)."""
    root = Path(root)

    capabilities = derive_capabilities(root, req.service)
    system_prompt = build_system_prompt(
        role=req.role,
        service=req.service,
        theme=theme,
        root=root,
        capabilities=capabilities,
    )

    workflow_text: Optional[str] = None
    if req.workflow:
        wf_rel = find_workflow_relpath(req.workflow, root)
        if wf_rel:
            workflow_text = read_resolved("workflows", wf_rel, req.service, root) or None

    return ResolvedRun(
        system_prompt=system_prompt,
        capabilities=capabilities,
        workflow=workflow_text,
        layers=layers_for(req.role, theme, root),
        model=req.model,
    )
