"""Thin FastAPI shell over the Runtime — the engine's entry contract (ADR-002 §3.2).

Intentionally minimal: HTTP, validation, routing. All logic lives in runtime.py / run.py /
app.py (testable without FastAPI). FastAPI is imported here only, so the rest of the package
and its test suite need no web framework.

- POST /resolve      → the resolved identity bundle (resolution only)
- POST /run          → enqueue the agentic loop, return 202 + run_id (sync via ?wait=true)
- POST /{alias}      → manifest-declared domain endpoints, alias to /run
- GET  /runs/{id}    → poll a run's lifecycle + outcome
- GET  /auth-log     → the perimeter connection log (read-only, for monitoring hosts)
- GET  /budget       → a tenant's remaining rolling budget (read-only, for monitoring hosts)
- POST /tenants · POST|GET /tokens · DELETE /tokens/{id}  → admin (admin-token only)

Two orthogonal opt-ins, composable:
  • **Security (ADR-004)** — pass a :class:`SecurityGate` to enable Bearer auth on the direct +
    monitoring routes and the rate/budget/idempotency chain on ``/run``.
  • **Async (ADR-005)** — pass a started :class:`JobQueue` to accept-then-process (``/run`` → 202
    + run_id), with ``?wait=true`` preserving the synchronous path.
With neither, the API is open and synchronous (the local-dev / demo default).
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from typing import Any, Dict, List, Mapping, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth import AuthMethod, AuthReason, hash_token
from .auth_policy import AuthRequest
from .job_queue import JobQueue, QueueFull
from .runtime import Runtime
from .security_gate import SecurityGate, status_for
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


class TokenCreatePayload(BaseModel):
    tenant: str
    scopes: Optional[List[str]] = None    # workspaces the token may invoke (default: its tenant)
    label: Optional[str] = None
    expires_at: Optional[str] = None      # unix seconds (default: never)
    admin: bool = False                   # grant admin privilege (manage tenants/tokens)


class TenantUpsertPayload(BaseModel):
    tenant: str
    enabled: bool = True
    budget_daily_usd: Optional[float] = None
    budget_monthly_usd: Optional[float] = None
    rate_limit_per_min: Optional[int] = None


def create_app(runtime: Runtime, *, gate: Optional[SecurityGate] = None,
               queue: Optional[JobQueue] = None) -> FastAPI:
    """Build the API over a configured ``Runtime`` (workspaces, store, model backend, manifest).

    ``gate`` enables ADR-004 security; ``queue`` enables ADR-005 async execution. Both default
    to ``None`` (open + synchronous)."""
    lifespan = None
    if queue is not None:
        @asynccontextmanager
        async def lifespan(app):
            queue.start()                    # idempotent — fine if already started by the host
            try:
                yield
            finally:
                queue.shutdown(drain=True)   # graceful: finish in-flight runs on SIGTERM (§2.5)

    app = FastAPI(title="cortex-runtime", version="0.1.0", lifespan=lifespan)
    manifest = dict(runtime.cfg.manifest)
    store = runtime.cfg.store

    # ── security helpers (no-ops when gate is None) ─────────────────────────────────────────
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
            raise HTTPException(status_code=status_for(outcome.reason), detail=outcome.reason.value)

    def _require_admin(request: Request):
        """Admin routes (tenant/token management): require an authenticated token carrying the
        **admin** privilege. Admin is global, not workspace-scoped. Logs exactly one auth_log row
        with the decisive reason (the auth failure, or ``forbidden`` for a valid-but-non-admin)."""
        if gate is None:
            return None
        req = _bearer_request(request)        # workspace=None → no scope check; admin is global
        outcome = gate.policy.check(req, record=False)
        if not outcome.ok:
            gate.policy.log_attempt(req, outcome)
            raise HTTPException(status_code=status_for(outcome.reason), detail=outcome.reason.value)
        if not outcome.admin:
            gate.policy.log_attempt(req, replace(outcome, reason=AuthReason.FORBIDDEN))
            raise HTTPException(status_code=403, detail=AuthReason.FORBIDDEN.value)
        gate.policy.log_attempt(req, outcome)
        return outcome

    def _authorize_run(request: Request, workspace: str, run_id: str):
        """The full spend-guarding chain for ``/run`` (auth → idempotency claim → rate → budget).
        Returns ``(decision, idempotency_key)``; raises on a hard rejection. A *duplicate* is not
        a rejection — it comes back on ``decision.is_duplicate`` for the caller to short-circuit."""
        if gate is None:
            return None, None
        idem_key = request.headers.get("idempotency-key")
        decision = gate.authorize(_bearer_request(request, workspace=workspace),
                                  idempotency_key=idem_key, run_id=run_id)
        if not decision.is_duplicate and not decision.allowed:
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

    def _dispatch_run(payload: Mapping[str, Any], alias: Optional[Mapping[str, Any]],
                      request: Request, wait: bool):
        """The integrated /run path. A ``run_id`` is **pre-minted** so the security chain can
        atomically *claim* it as the idempotency key BEFORE any record or model call exists —
        a duplicate (in-flight or completed) short-circuits here, never spawning a second run.
        Then sync and async share one path (``prepare`` → ``execute`` | enqueue)."""
        run_id = runtime.new_run_id()
        decision, idem_key = _authorize_run(request, payload["workspace"], run_id)

        if decision is not None and decision.is_duplicate:
            entry = decision.idempotent_entry                   # {"run_id": ..., "result": ...}
            if entry.get("result") is not None:
                return entry["result"]                          # completed earlier → cached result
            return JSONResponse(status_code=202,                # still in flight → poll the original
                                content={"run_id": entry["run_id"], "status": "duplicate",
                                         "detail": "already accepted; poll the run"})

        # We hold the claim (or there is no gate). Create the queued record with OUR run_id.
        prepared = _guard(lambda: runtime.prepare(payload, alias, run_id=run_id))
        job = {"run_id": run_id, "payload": dict(payload), "alias": dict(alias) if alias else None}

        if queue is not None and not wait:                      # async: accept-then-process
            try:
                queue.submit(job)
            except QueueFull:
                raise HTTPException(status_code=429, detail="queue at capacity",
                                    headers={"Retry-After": "5"})
            return JSONResponse(status_code=202,
                                content={"run_id": run_id, "subject": prepared["subject"],
                                         "status": "queued"})

        result = _guard(lambda: runtime.execute(job))           # sync (no queue, or ?wait=true)
        if gate is not None and idem_key:                       # cache the result for later duplicates
            gate.remember(idempotency_key=idem_key, tenant=decision.outcome.tenant,
                          run_id=run_id, result=result, now=int(time.time()))
        return result

    @app.get("/health")
    def health():
        """Liveness (ADR-005 §2.5): the process is up. Cheap, dependency-free."""
        return {"status": "ok", "backend": runtime.cfg.model_backend,
                "workspaces": sorted(runtime.cfg.workspaces), "endpoints": sorted(manifest)}

    @app.get("/ready")
    def ready():
        """Readiness (ADR-005 §2.5): safe to receive traffic — the store answers and (if async)
        the worker pool is alive. K8s gates rollouts/routing on this; `503` keeps a not-ready
        replica out of the pool."""
        try:
            store.get_run("__readiness_probe__")    # cheap round-trip; None is a fine answer
            db_ok = True
        except Exception:
            logger.exception("readiness: store unreachable")
            db_ok = False
        worker_ok = queue.healthy() if queue is not None else True
        body: Dict[str, Any] = {"ready": db_ok and worker_ok, "db": db_ok, "worker": worker_ok}
        if queue is not None:
            body["queue"] = queue.stats()
        if not body["ready"]:
            return JSONResponse(status_code=503, content=body)
        return body

    # — monitoring (read-only, Bearer-protected when a gate is set): for monitoring hosts —
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

    # — admin (tenant/token management, ADR-004 §3.7): admin-token only. The "master" token is
    #   minted by hand once (`admin token … --admin`); it bootstraps every other token here. —
    @app.post("/tenants")
    def upsert_tenant(payload: TenantUpsertPayload, request: Request):
        _require_admin(request)
        store.upsert_tenant(payload.tenant, enabled=payload.enabled,
                            budget_daily_usd=payload.budget_daily_usd,
                            budget_monthly_usd=payload.budget_monthly_usd,
                            rate_limit_per_min=payload.rate_limit_per_min)
        return asdict(store.get_tenant(payload.tenant))

    @app.post("/tokens")
    def create_token(payload: TokenCreatePayload, request: Request):
        """Mint a Bearer token for a tenant. The RAW token is returned ONCE (only its hash is
        stored). Requires an admin token — this is how the master token issues all the others."""
        from .admin import mint_raw_token
        _require_admin(request)
        if store.get_tenant(payload.tenant) is None:
            raise HTTPException(status_code=404, detail=f"unknown tenant: {payload.tenant}")
        scopes = payload.scopes or [payload.tenant]
        raw = mint_raw_token()
        token_id = store.add_token(payload.tenant, hash_token(raw), scopes=scopes,
                                   label=payload.label, expires_at=payload.expires_at,
                                   admin=payload.admin)
        return {"token_id": token_id, "tenant": payload.tenant, "scopes": scopes,
                "admin": payload.admin, "token": raw}   # raw shown once — never recoverable later

    @app.get("/tokens")
    def list_tokens(request: Request, tenant: str):
        """List a tenant's tokens — metadata only, never the hash (nor the raw, which is gone)."""
        _require_admin(request)
        return {"tokens": [{k: v for k, v in asdict(t).items() if k != "token_hash"}
                           for t in store.list_tokens(tenant)]}

    @app.delete("/tokens/{token_id}")
    def revoke_token(token_id: str, request: Request):
        _require_admin(request)
        store.revoke_token(token_id)
        return {"token_id": token_id, "revoked": True}

    @app.post("/resolve")
    def resolve(payload: RunPayload, request: Request):
        _require_read(request, payload.workspace)   # resolution is read-only: auth + scope, no spend
        _require_role(payload, None)
        return _guard(lambda: asdict(runtime.resolve(payload.model_dump())))

    @app.post("/run")
    def run(payload: RunPayload, request: Request, wait: bool = False):
        _require_role(payload, None)
        return _dispatch_run(payload.model_dump(), None, request, wait)

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
            def handler(payload: RunPayload, request: Request, wait: bool = False):
                _require_role(payload, alias_defaults)
                return _dispatch_run(payload.model_dump(), alias_defaults, request, wait)
            return handler
        app.add_api_route(path, _make(alias), methods=["POST"], name=path.strip("/").replace("/", "_"))

    return app
