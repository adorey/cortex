"""Thin FastAPI shell over app.resolve_endpoint — the engine's entry contract (ADR-002 §3.2).

Intentionally minimal: it does HTTP, validation, and routing; all resolution logic lives in
app.py / run.py (testable without FastAPI). FastAPI is imported here only, so the rest of the
package — and its test suite — needs no web framework installed.

Phase 2 scope: ``/run`` (and manifest aliases) return the *resolved bundle*. Wiring the
agentic loop (§3.3) onto this resolution is Phase 3.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .app import WorkspaceConfig, resolve_endpoint


class RunPayload(BaseModel):
    workspace: str
    role: Optional[str] = None          # may come from an endpoint alias instead
    service: Optional[str] = None
    workflow: Optional[str] = None
    input: Dict[str, Any] = {}
    model: Optional[str] = None
    autonomy: Optional[List[str]] = None  # action kinds allowed without human validation


def create_app(
    registry: Mapping[str, WorkspaceConfig],
    manifest: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> FastAPI:
    """Build the API. ``registry`` binds workspaces to mirrors; ``manifest`` maps domain
    paths (e.g. ``/support/analyze``) to alias payloads that merge into ``/run``."""
    app = FastAPI(title="cortex-runtime", version="0.0.1")
    manifest = dict(manifest or {})

    def _resolve(payload: RunPayload, alias: Optional[Mapping[str, Any]] = None):
        merged = payload.model_dump()
        try:
            resolved = resolve_endpoint(registry, merged, alias)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown workspace: {payload.workspace}")
        except (TypeError, ValueError) as exc:  # missing role, or an unknown autonomy action
            raise HTTPException(status_code=422, detail=str(exc))
        return asdict(resolved)

    @app.get("/health")
    def health():
        return {"status": "ok", "workspaces": sorted(registry), "endpoints": sorted(manifest)}

    @app.post("/run")
    def run(payload: RunPayload):
        if payload.role is None:
            raise HTTPException(status_code=422, detail="`role` is required on POST /run")
        return _resolve(payload)

    # Project-declared domain endpoints — each aliases to /run with fixed defaults.
    for path, alias in manifest.items():
        def _make(alias_defaults: Mapping[str, Any]):
            def handler(payload: RunPayload):
                return _resolve(payload, alias_defaults)
            return handler
        app.add_api_route(path, _make(alias), methods=["POST"], name=path.strip("/").replace("/", "_"))

    return app
