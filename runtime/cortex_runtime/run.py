"""The /run contract, framework-agnostic — ADR-002 §3.2.

``resolve_run`` is the deterministic core (ADR-002 §8.1 pre-resolution): given a request
and a bound ``root`` (§3.4), it assembles everything the agentic loop (Phase 3) needs —
the system prompt (identity), the derived capabilities, and the advisory workflow recipe.

This module imports no web framework on purpose: the API layer (api.py) is a thin shell
over it, so the contract stays testable with zero install.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple, Union

from cortex_core.workspace import service_index

from .base import Pin, base_for, read_pin
from .context import derive_capabilities, read_project_context, read_project_overview
from .resolver import build_system_prompt, find_workflow_relpath, layers_for, read_resolved
from .safety import ActionPolicy


@dataclass
class RunRequest:
    """The generic /run payload (ADR-002 §3.2). ``model`` is optional."""

    workspace: str
    role: str
    service: Optional[str] = None
    workflow: Optional[str] = None
    input: Dict[str, Any] = field(default_factory=dict)
    model: Optional[str] = None
    # Agnostic correlation key for this flow's conversation/anti-recursion state (ADR-003):
    # an issue key, a dashboard correlation id, a scheduled-run key. Falls back per host.
    subject: Optional[str] = None
    # When true, a normal completion ends in AWAITING_HUMAN (a hand-off) instead of RESOLVED —
    # the natural end of analysis/triage flows (e.g. support-engineer). Default: resolve.
    handoff: bool = False
    # Testing/override: bypass the anti-recursion guard and run even if the subject is not
    # awaiting-agent (re-run the same ticket without re-arming). Never use in production.
    force: bool = False
    # Actions the agent may take WITHOUT human validation, for THIS run (action-kind
    # strings, e.g. ["code-read", "internal-comment"]). None → least-privilege default. The
    # autonomy level is a per-request decision, never hard-coded (ADR-002 §3.3).
    autonomy: Optional[List[str]] = None


@dataclass
class ResolvedRun:
    """Everything the agentic loop needs, pre-resolved (identity given, work improvised)."""

    system_prompt: str
    capabilities: List[str]
    workflow: Optional[str]              # advisory recipe text, or None
    layers: List[Tuple[str, str]]        # (layer, file) pairs that built the identity
    model: Optional[str]
    allowed_actions: List[str]           # autonomy granted for this run (gating allowlist)
    cortex_version: Optional[str] = None  # the version cortex.toml pins; None: the base is {root}/cortex


def _service_inside(service: Optional[str]) -> Optional[str]:
    """The service as a folder of the workspace — relative, normalised, never climbing out of it.
    Its files reach the prompt: a service naming ``../elsewhere`` would read a neighbour's."""
    if not service:
        return service
    path = PurePosixPath(service.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", service):
        raise ValueError(f"service must be a folder inside the workspace, got {service!r}")
    if not path.parts:
        return None                  # "." is the workspace itself: no service
    if path.parts[0] == "agents":
        raise ValueError(f"service must be a folder of the workspace other than agents/, got {service!r}")
    return str(path)


class _ReadNow:
    def __repr__(self) -> str:
        return "READ_NOW"


# resolve_run's default pin: the project's cortex.toml, read as it is now.
READ_NOW: Any = _ReadNow()


def resolve_run(req: RunRequest, root: Path, theme: Optional[str] = None, *,
                pin: Union[Pin, None, _ReadNow] = READ_NOW) -> ResolvedRun:
    """Compile a request into a resolved bundle. ``theme`` is the workspace's active theme
    (deployment config — never a developer's own, in ``cortex.local.toml``); without one, the
    theme the project's ``cortex.toml`` names. The base is the store's copy of the version
    ``cortex.toml`` pins, or ``{root}/cortex`` without one (ADR-008 §3.6): a version the store
    lacks is a ``ValueError``, as a bad service is.

    ``pin`` is what ``cortex.toml`` said when the run was accepted — a queued run resolves as it
    was checked, whatever the file says by the time a worker takes it (``None``: it had none)."""
    root = Path(root)
    req = replace(req, service=_service_inside(req.service))
    if pin is READ_NOW:
        pin = read_pin(root)
    base_root = base_for(pin)
    if theme is None and pin is not None:
        theme = pin.theme

    capabilities = derive_capabilities(root, req.service, base_root=base_root)
    system_prompt = build_system_prompt(
        role=req.role,
        service=req.service,
        theme=theme,
        root=root,
        base_root=base_root,
        capabilities=capabilities,
        project_overview=read_project_overview(root, req.service),
        workspace_services=service_index(root, base_root, active=req.service),
        project_context=read_project_context(root, req.service),
    )

    workflow_text: Optional[str] = None
    if req.workflow:
        wf_rel = find_workflow_relpath(req.workflow, root, base_root=base_root)
        if wf_rel:
            workflow_text = read_resolved("workflows", wf_rel, req.service, root, base_root=base_root) or None

    # Validate & normalise the per-request autonomy (raises ValueError on an unknown action).
    policy = ActionPolicy.from_names(req.autonomy)

    return ResolvedRun(
        system_prompt=system_prompt,
        capabilities=capabilities,
        workflow=workflow_text,
        layers=layers_for(req.role, theme, root, base_root=base_root),
        model=req.model,
        allowed_actions=sorted(k.value for k in policy.allowed),
        cortex_version=pin.version if pin is not None else None,
    )
