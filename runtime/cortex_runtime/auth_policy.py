"""API security — the boundary policy (ADR-004 §3.6, §3.7).

Where ``auth.py`` is the pure substance (sign/verify/hash, no I/O), ``AuthPolicy`` is the
**store-backed boundary**: it resolves a request's identity against the ``api_tokens`` /
``tenants`` tables, fetches per-tenant HMAC secrets from the ``SecretProvider``, and **writes
every attempt — accepted or rejected — to ``auth_log``** (the perimeter log, §3.7).

It is still framework-agnostic and clock-injected: the FastAPI layer (increment #6) only
adapts an HTTP request into an :class:`AuthRequest` and maps the verdict to a status code.
The replay/idempotency, rate-limit and budget layers slot into :meth:`check` in later
increments — this one covers **authentication + authorization** (the first two doors).

    request → [authenticate + authorize] → replay/idempotency → rate-limit → budget → run
              ↑──────────── this module ───────────┘   ↑──────── increments #4–#5 ───────┘
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .auth import (
    AuthMethod,
    AuthOutcome,
    AuthReason,
    DEFAULT_REPLAY_WINDOW_S,
    hash_token,
    parse_bearer,
    verify_hmac,
)
from .state_store import StateStore, TokenRecord

# How the policy obtains a tenant's *raw* HMAC secret. Injected (not a SecretProvider directly)
# so the secret layout — single-tenant, per-namespace, or a vault lookup — stays a wiring
# concern. Returns ``None`` when no secret is configured for that tenant.
HmacSecretLookup = Callable[[str], Optional[str]]


@dataclass
class AuthRequest:
    """A normalized, transport-agnostic description of an inbound request to authenticate.

    ``now`` is unix seconds (the injected clock). Bearer fields (``authorization``,
    ``workspace``) drive the direct path; HMAC fields (``tenant``, ``timestamp``,
    ``signature``, ``body``) drive the webhook path. ``at`` is the timestamp string written
    to ``auth_log`` (defaults to ``str(now)``)."""

    method: AuthMethod
    route: str
    now: int
    source_ip: Optional[str] = None
    request_id: Optional[str] = None
    at: Optional[str] = None
    # — Bearer (direct) —
    authorization: Optional[str] = None     # the raw ``Authorization`` header
    workspace: Optional[str] = None         # the workspace the caller intends to invoke (scope)
    # — HMAC (webhook) —
    tenant: Optional[str] = None            # the claimed webhook source (from the route)
    timestamp: Optional[str] = None
    signature: Optional[str] = None
    body: Optional[str] = None


def _expired(expires_at: Optional[str], now: int) -> bool:
    """A token's ``expires_at`` is stored as unix seconds (string); absent ⇒ never expires."""
    if not expires_at:
        return False
    try:
        return now > int(expires_at)
    except (TypeError, ValueError):
        return False


def _in_scope(token: TokenRecord, workspace: Optional[str]) -> bool:
    """A token may invoke its own tenant's workspace plus any workspace in ``scopes``.
    A request that names no workspace (e.g. global monitoring) is always in scope."""
    if workspace is None:
        return True
    return workspace in (set(token.scopes) | {token.tenant})


class AuthPolicy:
    """Resolves and logs the authentication/authorization verdict for an inbound request."""

    def __init__(
        self,
        store: StateStore,
        *,
        hmac_secret_for: HmacSecretLookup,
        replay_window: int = DEFAULT_REPLAY_WINDOW_S,
    ):
        self._store = store
        self._hmac_secret_for = hmac_secret_for
        self._window = replay_window

    def check(self, req: AuthRequest) -> AuthOutcome:
        """Authenticate + authorize, **log the attempt**, and return the verdict."""
        outcome = self._authenticate(req)
        self._store.record_auth(
            at=req.at or str(req.now),
            route=req.route,
            method=outcome.method.value,
            result="accepted" if outcome.ok else "rejected",
            reason=outcome.reason.value,
            tenant=outcome.tenant,
            source_ip=req.source_ip,
            request_id=req.request_id,
        )
        return outcome

    # — internals (no logging here; check() logs once) ——————————————————————————————————

    def _authenticate(self, req: AuthRequest) -> AuthOutcome:
        if req.method is AuthMethod.BEARER:
            return self._check_bearer(req)
        return self._check_hmac(req)

    def _check_bearer(self, req: AuthRequest) -> AuthOutcome:
        token = parse_bearer(req.authorization)
        if not token:
            return AuthOutcome(AuthReason.UNKNOWN_TOKEN, AuthMethod.BEARER)
        rec = self._store.get_token_by_hash(hash_token(token))
        if rec is None:
            return AuthOutcome(AuthReason.UNKNOWN_TOKEN, AuthMethod.BEARER)
        ident = dict(method=AuthMethod.BEARER, tenant=rec.tenant, token_id=rec.token_id)
        if rec.revoked or _expired(rec.expires_at, req.now):
            return AuthOutcome(AuthReason.REVOKED_TOKEN, **ident)
        tenant = self._store.get_tenant(rec.tenant)
        if tenant is not None and not tenant.enabled:
            return AuthOutcome(AuthReason.TENANT_DISABLED, **ident)
        if not _in_scope(rec, req.workspace):
            return AuthOutcome(AuthReason.OUT_OF_SCOPE, **ident)
        return AuthOutcome(AuthReason.OK, **ident)

    def _check_hmac(self, req: AuthRequest) -> AuthOutcome:
        name = req.tenant
        if not name:
            return AuthOutcome(AuthReason.UNKNOWN_TOKEN, AuthMethod.HMAC)
        tenant = self._store.get_tenant(name)
        if tenant is None:
            return AuthOutcome(AuthReason.UNKNOWN_TOKEN, AuthMethod.HMAC, tenant=name)
        if not tenant.enabled:
            return AuthOutcome(AuthReason.TENANT_DISABLED, AuthMethod.HMAC, tenant=name)
        secret = self._hmac_secret_for(name)
        if not secret:
            # No secret on file ⇒ we cannot prove authenticity ⇒ treat as unknown source.
            return AuthOutcome(AuthReason.UNKNOWN_TOKEN, AuthMethod.HMAC, tenant=name)
        reason = verify_hmac(secret, req.timestamp or "", req.body or "",
                             req.signature or "", now=req.now, window=self._window)
        return AuthOutcome(reason, AuthMethod.HMAC, tenant=name)
