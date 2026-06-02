"""Application logic for the agnostic API — framework-agnostic (ADR-002 §3.2).

Two responsibilities, both pure and testable without a web framework:
  • workspace → binding: map a workspace name to its bound ``root`` + active theme (§3.4)
  • endpoint → request: merge a project-declared alias with the request body into a
    ``RunRequest`` (the project DECLARES endpoints; it does not write engine code)

api.py is a thin FastAPI shell over ``resolve_endpoint``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .run import ResolvedRun, RunRequest, resolve_run


@dataclass
class WorkspaceConfig:
    """Deployment-level binding for one workspace (the warm mirror path + active theme)."""

    root: Path
    theme: Optional[str] = None


def build_run_request(payload: Mapping[str, Any], alias: Optional[Mapping[str, Any]] = None) -> RunRequest:
    """Merge a project-declared alias (path → payload defaults) with the request body.

    The body overrides the alias for any field it provides (non-None). ``POST /run`` uses
    ``alias=None``; a domain endpoint like ``POST /support/analyze`` passes its manifest entry.
    """
    merged: Dict[str, Any] = dict(alias or {})
    for key, value in payload.items():
        if value is not None:
            merged[key] = value
    return RunRequest(
        workspace=merged["workspace"],
        role=merged["role"],
        service=merged.get("service"),
        workflow=merged.get("workflow"),
        input=merged.get("input") or {},
        model=merged.get("model"),
        autonomy=merged.get("autonomy"),
        subject=merged.get("subject"),
        handoff=bool(merged.get("handoff", False)),
    )


def resolve_endpoint(
    registry: Mapping[str, WorkspaceConfig],
    payload: Mapping[str, Any],
    alias: Optional[Mapping[str, Any]] = None,
) -> ResolvedRun:
    """Resolve a request against the workspace registry. Raises ``KeyError`` if the
    workspace is unknown (the API layer maps that to 404)."""
    req = build_run_request(payload, alias)
    if req.workspace not in registry:
        raise KeyError(req.workspace)
    cfg = registry[req.workspace]
    return resolve_run(req, cfg.root, cfg.theme)
