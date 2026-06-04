"""API security — the ordered boundary chain (ADR-004 §2).

`SecurityGate` runs every cheap, deterministic, pre-AI check **in the fixed order the ADR
mandates**, short-circuiting on the first failure, and writes exactly **one** ``auth_log``
row per attempt with the decisive reason:

    authenticate (+HMAC replay) → idempotency → rate-limit → budget cap → ALLOW
    ↑──────────────── a rejection here costs zero model credit ───────────────↑

It composes the pieces already built and tested in isolation — :class:`AuthPolicy`
(authenticate/authorize/replay), :func:`check_rate` (ephemeral), :func:`check_budget`
(StateStore cost) — and stays framework-agnostic: the FastAPI layer adapts an HTTP request
into an :class:`AuthRequest`, calls :meth:`authorize`, and maps the verdict to a status code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Optional

from .auth import AuthMethod, AuthOutcome, AuthReason
from .auth_policy import AuthPolicy, AuthRequest, DEFAULT_REPLAY_WINDOW_S
from .budget import BudgetDecision, check_budget
from .ephemeral import EphemeralStore, InMemoryEphemeralStore, check_rate
from .secret_provider import SecretProvider
from .state_store import StateStore

IDEMPOTENCY_TTL_S = 24 * 60 * 60   # remember a delivery's outcome for a day (ADR-004 §3.3)

# Verdict → HTTP status. Auth failures are 401; authorization failures 403; the wallet
# guards get their own codes so a caller (and a monitoring host) can tell *why* it was shed.
_STATUS = {
    AuthReason.OK: 200,
    AuthReason.INVALID_SIGNATURE: 401,
    AuthReason.STALE_TIMESTAMP: 401,
    AuthReason.REPLAY: 401,
    AuthReason.UNKNOWN_TOKEN: 401,
    AuthReason.REVOKED_TOKEN: 401,
    AuthReason.OUT_OF_SCOPE: 403,
    AuthReason.TENANT_DISABLED: 403,
    AuthReason.FORBIDDEN: 403,
    AuthReason.RATE_LIMITED: 429,
    AuthReason.BUDGET_EXCEEDED: 402,
}


def status_for(reason: AuthReason) -> int:
    return _STATUS.get(reason, 401)


@dataclass(frozen=True)
class GateDecision:
    """The boundary's final word on a request."""
    outcome: AuthOutcome
    status: int
    retry_after_s: Optional[int] = None        # set on RATE_LIMITED
    budget: Optional[BudgetDecision] = None     # populated when a budget was evaluated
    idempotent_entry: Optional[dict] = None     # a duplicate: the existing claim {"run_id","result"}

    @property
    def allowed(self) -> bool:
        return self.outcome.ok

    @property
    def is_duplicate(self) -> bool:
        return self.idempotent_entry is not None


class SecurityGate:
    """Runs the full pre-AI check chain and logs one verdict per attempt."""

    def __init__(self, store: StateStore, policy: AuthPolicy, *,
                 ephemeral: Optional[EphemeralStore] = None,
                 idempotency_ttl: int = IDEMPOTENCY_TTL_S):
        self._store = store
        self._policy = policy
        self._ephemeral = ephemeral
        self._idem_ttl = idempotency_ttl

    @property
    def policy(self) -> AuthPolicy:
        """The underlying authenticate/authorize policy — used directly for read-only routes
        (monitoring) that need identity + scope but not the rate/budget spend guards."""
        return self._policy

    def authorize(self, req: AuthRequest, *, idempotency_key: Optional[str] = None,
                  run_id: Optional[str] = None) -> GateDecision:
        # 1. authenticate + authorize (+ HMAC exact-replay) — no logging yet; the gate logs once.
        outcome = self._policy.check(req, record=False)
        if not outcome.ok:
            return self._finish(req, outcome)

        tenant_rec = self._store.get_tenant(outcome.tenant) if outcome.tenant else None

        # 2. idempotency — an ATOMIC CLAIM on the key, scoped to the tenant. The FIRST delivery
        #    reserves the key with its (pre-minted) ``run_id``; any concurrent or later duplicate
        #    finds the key taken and short-circuits HERE — before rate/budget, and crucially
        #    before a single run is spawned. This closes the in-flight gap: a spammed delivery
        #    can no longer fan out into N parallel model calls (ADR-004 §3.3).
        if idempotency_key and run_id and self._ephemeral is not None:
            claim = json.dumps({"run_id": run_id, "result": None})
            existing = self._ephemeral.claim_idempotent(
                self._idem_key(outcome, idempotency_key), claim, now=req.now, ttl_s=self._idem_ttl)
            if existing is not None:
                return self._finish(req, outcome, idempotent_entry=json.loads(existing))

        # 3. rate-limit — per token when identified, else per IP. Tenant ceiling drives it.
        if self._ephemeral is not None and tenant_rec is not None:
            key = outcome.token_id or outcome.tenant or req.source_ip or "anon"
            rl = check_rate(self._ephemeral, key, tenant_rec.rate_limit_per_min, now=req.now)
            if not rl.allowed:
                return self._finish(req, replace(outcome, reason=AuthReason.RATE_LIMITED),
                                    retry_after_s=rl.retry_after_s)

        # 4. budget cap — refuse if the tenant is already over its rolling ceiling.
        budget = check_budget(self._store, tenant_rec, now=req.now)
        if not budget.allowed:
            return self._finish(req, replace(outcome, reason=AuthReason.BUDGET_EXCEEDED), budget=budget)

        return self._finish(req, outcome, budget=budget)

    def remember(self, *, idempotency_key: str, tenant: Optional[str], run_id: str,
                 result: dict, now: int) -> None:
        """Overwrite a run's idempotency claim with its completed result, so a later duplicate
        gets the cached outcome inline (not just the run_id). Call after a SYNCHRONOUS run; an
        async run leaves the claim at ``{run_id, result:None}`` and a duplicate polls the run."""
        if self._ephemeral is not None:
            self._ephemeral.put_idempotent(
                self._idem_key_for(tenant, idempotency_key),
                json.dumps({"run_id": run_id, "result": result}), now=now, ttl_s=self._idem_ttl)

    # — internals ————————————————————————————————————————————————————————————————————————

    def _idem_key(self, outcome: AuthOutcome, key: str) -> str:
        return self._idem_key_for(outcome.tenant, key)

    def _idem_key_for(self, tenant: Optional[str], key: str) -> str:
        # Scope the key to the tenant so two tenants' identical delivery ids never collide.
        return f"idem:{tenant or 'anon'}:{key}"

    def _finish(self, req: AuthRequest, outcome: AuthOutcome, **extra) -> GateDecision:
        self._policy.log_attempt(req, outcome)
        return GateDecision(outcome, status_for(outcome.reason), **extra)


def build_gate(store: StateStore, secrets: SecretProvider, *,
               ephemeral: Optional[EphemeralStore] = None,
               replay_window: int = DEFAULT_REPLAY_WINDOW_S) -> SecurityGate:
    """Assemble a production gate from a store + SecretProvider.

    Per-tenant HMAC secrets are read from the provider as ``<tenant>_webhook_hmac`` (e.g.
    ``ACME_WEBHOOK_HMAC``) — raw, never the DB (ADR-004 §3.7). The ephemeral state
    (rate-limit / nonce / idempotency) defaults to an in-process store for a single node;
    pass a Redis-backed :class:`EphemeralStore` for multi-replica (ADR-005 §2.2)."""
    eph = ephemeral or InMemoryEphemeralStore()   # shared: nonce (policy) + rate/idem (gate)
    policy = AuthPolicy(
        store,
        hmac_secret_for=lambda tenant: secrets.get_optional(f"{tenant}_webhook_hmac"),
        replay_window=replay_window,
        ephemeral=eph,
    )
    return SecurityGate(store, policy, ephemeral=eph)
