"""Thin FastAPI shell over the Runtime — the engine's entry contract (ADR-002 §3.2).

Intentionally minimal: HTTP, validation, routing. All logic lives in runtime.py / run.py /
app.py (testable without FastAPI). FastAPI is imported here only, so the rest of the package
and its test suite need no web framework.

- POST /resolve      → the resolved identity bundle (resolution only)
- POST /run          → resolve AND execute the agentic loop (durable state + audit)
- POST /{alias}      → manifest-declared domain endpoints, alias to /run
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Mapping, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .runtime import Runtime
from .session import mark_human_reply

logger = logging.getLogger("cortex_runtime.api")


class RunPayload(BaseModel):
    workspace: str
    role: Optional[str] = None          # may come from an endpoint alias instead
    service: Optional[str] = None
    workflow: Optional[str] = None
    subject: Optional[str] = None       # correlation key (ADR-003); defaults per host
    input: Dict[str, Any] = {}
    model: Optional[str] = None
    autonomy: Optional[List[str]] = None  # action kinds allowed without human validation
    handoff: bool = False                 # end in AWAITING_HUMAN (analysis/triage flows)


class ReplyPayload(BaseModel):
    workspace: str
    subject: str


def create_app(runtime: Runtime) -> FastAPI:
    """Build the API over a configured ``Runtime`` (workspaces, store, model backend, manifest)."""
    app = FastAPI(title="cortex-runtime", version="0.0.1")
    manifest = dict(runtime.cfg.manifest)

    def _require_role(payload: RunPayload, alias: Optional[Mapping[str, Any]]):
        if payload.role is None and not (alias and alias.get("role")):
            raise HTTPException(status_code=422, detail="`role` is required (in the payload or the endpoint alias)")

    def _guard(fn):
        try:
            return fn()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown workspace: {exc}")
        except (TypeError, ValueError) as exc:  # missing role / unknown autonomy action
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:  # unexpected: log it, return a clean error (no raw stack)
            logger.exception("request failed")
            raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")

    store = runtime.cfg.store

    @app.get("/health")
    def health():
        return {"status": "ok", "backend": runtime.cfg.model_backend,
                "workspaces": sorted(runtime.cfg.workspaces), "endpoints": sorted(manifest)}

    # — monitoring (read-only): run history, run detail, audit trail —
    @app.get("/runs")
    def runs(workspace: str, limit: int = 50):
        return {"runs": [asdict(r) for r in store.list_runs(workspace, limit=limit)]}

    @app.get("/runs/{run_id}")
    def run_detail(run_id: str):
        record = store.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
        return asdict(record)

    @app.get("/audit")
    def audit(workspace: Optional[str] = None, subject: Optional[str] = None):
        return {"audit": [asdict(e) for e in store.audit_trail(workspace=workspace, subject=subject)]}

    @app.post("/resolve")
    def resolve(payload: RunPayload):
        _require_role(payload, None)
        return _guard(lambda: asdict(runtime.resolve(payload.model_dump())))

    @app.post("/run")
    def run(payload: RunPayload):
        _require_role(payload, None)
        return _guard(lambda: runtime.run(payload.model_dump()))

    @app.post("/reply")
    def reply(payload: ReplyPayload):
        """Signal that a human acted on an awaiting-human subject → re-arm the agent for the
        next round-trip (anti-recursion exit)."""
        mark_human_reply(store, payload.workspace, payload.subject)
        state = store.get_conversation_state(payload.workspace, payload.subject)
        return {"workspace": payload.workspace, "subject": payload.subject,
                "state": state.value if state else None}

    for path, alias in manifest.items():
        def _make(alias_defaults: Mapping[str, Any]):
            def handler(payload: RunPayload):
                _require_role(payload, alias_defaults)
                return _guard(lambda: runtime.run(payload.model_dump(), alias_defaults))
            return handler
        app.add_api_route(path, _make(alias), methods=["POST"], name=path.strip("/").replace("/", "_"))

    return app
