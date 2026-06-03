"""Thin FastAPI shell over the Runtime — the engine's entry contract (ADR-002 §3.2).

Intentionally minimal: HTTP, validation, routing. All logic lives in runtime.py / run.py /
app.py (testable without FastAPI). FastAPI is imported here only, so the rest of the package
and its test suite need no web framework.

- POST /resolve      → the resolved identity bundle (resolution only)
- POST /run          → resolve AND execute the agentic loop (durable state + audit)
- POST /{alias}      → manifest-declared domain endpoints, alias to /run
- GET  /auth-log     → the perimeter connection log (monitoring, e.g. wbtb)
- GET  /budget       → a tenant's remaining rolling budget (monitoring)

Security (ADR-004) is **opt-in**: pass a :class:`SecurityGate` to enable Bearer auth on the
direct + monitoring routes (and the full rate/budget/idempotency chain on ``/run``). With no
gate the API is open — the local-dev / demo default, and what the existing tests exercise.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from typing import Any, Dict, List, Mapping, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from .auth import AuthMethod
from .auth_policy import AuthRequest
from .runtime import Runtime
from .security_gate import SecurityGate
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
    force: bool = False                   # testing: bypass anti-recursion (re-run same subject)


class ReplyPayload(BaseModel):
    workspace: str
    subject: str


def create_app(runtime: Runtime, *, gate: Optional[SecurityGate] = None) -> FastAPI:
    """Build the API over a configured ``Runtime`` (workspaces, store, model backend, manifest).

    ``gate`` enables ADR-004 security; ``None`` leaves the API open (local dev / demo)."""
    app = FastAPI(title="cortex-runtime", version="0.0.1")
    manifest = dict(runtime.cfg.manifest)

    def _client_ip(request: Request) -> Optional[str]:
        # Honour a single proxy hop (Traefik) then fall back to the socket peer.
        fwd = request.headers.get("x-forwarded-for")
        return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)

    def _bearer_request(request: Request, *, workspace: Optional[str] = None) -> AuthRequest:
        return AuthRequest(
            method=AuthMethod.BEARER, route=request.url.path, now=int(time.time()),
            source_ip=_client_ip(request), request_id=request.headers.get("x-request-id"),
            authorization=request.headers.get("authorization"), workspace=workspace,
        )

    def _require_read(request: Request, workspace: Optional[str] = None):
        """Monitoring/read routes: authenticate + authorize (Bearer + scope) — no spend guards."""
        if gate is None:
            return
        outcome = gate.policy.check(_bearer_request(request, workspace=workspace))
        if not outcome.ok:
            from .security_gate import status_for
            raise HTTPException(status_code=status_for(outcome.reason), detail=outcome.reason.value)

    def _authorize_run(request: Request, workspace: str):
        """The full spend-guarding chain for ``/run`` (auth → idempotency → rate → budget).
        Returns ``(decision, idempotency_key)`` or raises with the verdict's status code."""
        if gate is None:
            return None, None
        idem_key = request.headers.get("idempotency-key")
        decision = gate.authorize(_bearer_request(request, workspace=workspace),
                                  idempotency_key=idem_key)
        if not decision.allowed:
            headers = {"Retry-After": str(decision.retry_after_s)} if decision.retry_after_s else None
            raise HTTPException(status_code=decision.status,
                                detail=decision.outcome.reason.value, headers=headers)
        return decision, idem_key

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

    # — monitoring (read-only, Bearer-protected when a gate is set): for wbtb dashboards —
    @app.get("/runs")
    def runs(request: Request, workspace: str, limit: int = 50):
        _require_read(request, workspace)
        return {"runs": [asdict(r) for r in store.list_runs(workspace, limit=limit)]}

    @app.get("/runs/{run_id}")
    def run_detail(request: Request, run_id: str):
        _require_read(request)
        record = store.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
        return asdict(record)

    @app.get("/audit")
    def audit(request: Request, workspace: Optional[str] = None, subject: Optional[str] = None):
        _require_read(request, workspace)
        return {"audit": [asdict(e) for e in store.audit_trail(workspace=workspace, subject=subject)]}

    @app.get("/auth-log")
    def auth_log(request: Request, tenant: Optional[str] = None,
                 result: Optional[str] = None, limit: int = 100):
        """The perimeter connection log (ADR-004 §3.7) — every auth attempt + verdict + reason."""
        _require_read(request, tenant)
        return {"auth_log": [asdict(e) for e in store.auth_log(tenant=tenant, result=result, limit=limit)]}

    @app.get("/budget")
    def budget(request: Request, workspace: str):
        """A tenant's rolling spend vs ceilings (ADR-004 §3.5) — for cost dashboards."""
        _require_read(request, workspace)
        from .budget import check_budget

        def _window(w):
            if w is None:
                return None
            return {"spent_usd": w.spent_usd, "ceiling_usd": w.ceiling_usd,
                    "remaining_usd": w.remaining_usd, "exceeded": w.exceeded}

        decision = check_budget(store, store.get_tenant(workspace), now=int(time.time()))
        return {"workspace": workspace, "allowed": decision.allowed,
                "daily": _window(decision.daily), "monthly": _window(decision.monthly)}

    @app.post("/resolve")
    def resolve(payload: RunPayload, request: Request):
        _require_read(request, payload.workspace)   # resolution is read-only: auth + scope, no spend
        _require_role(payload, None)
        return _guard(lambda: asdict(runtime.resolve(payload.model_dump())))

    @app.post("/run")
    def run(payload: RunPayload, request: Request):
        _require_role(payload, None)
        decision, idem_key = _authorize_run(request, payload.workspace)
        if decision is not None and decision.idempotent_replay is not None:
            return json.loads(decision.idempotent_replay)   # duplicate delivery → cached outcome
        result = _guard(lambda: runtime.run(payload.model_dump()))
        if gate is not None and idem_key:
            gate.remember(decision.outcome, idem_key, json.dumps(result), now=int(time.time()))
        return result

    @app.post("/reply")
    def reply(payload: ReplyPayload, request: Request):
        """Signal that a human acted on an awaiting-human subject → re-arm the agent for the
        next round-trip (anti-recursion exit)."""
        _require_read(request, payload.workspace)
        mark_human_reply(store, payload.workspace, payload.subject)
        state = store.get_conversation_state(payload.workspace, payload.subject)
        return {"workspace": payload.workspace, "subject": payload.subject,
                "state": state.value if state else None}

    for path, alias in manifest.items():
        def _make(alias_defaults: Mapping[str, Any]):
            def handler(payload: RunPayload, request: Request):
                _require_role(payload, alias_defaults)
                decision, idem_key = _authorize_run(request, payload.workspace)
                if decision is not None and decision.idempotent_replay is not None:
                    return json.loads(decision.idempotent_replay)
                result = _guard(lambda: runtime.run(payload.model_dump(), alias_defaults))
                if gate is not None and idem_key:
                    gate.remember(decision.outcome, idem_key, json.dumps(result), now=int(time.time()))
                return result
            return handler
        app.add_api_route(path, _make(alias), methods=["POST"], name=path.strip("/").replace("/", "_"))

    return app
