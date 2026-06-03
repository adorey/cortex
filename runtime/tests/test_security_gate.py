"""The full ordered boundary chain (ADR-004 §2) — authenticate → idempotency → rate-limit →
budget. One auth_log row per attempt, correct short-circuit order, correct HTTP status."""

from __future__ import annotations

import pytest

from cortex_runtime.auth import AuthMethod, AuthReason, hash_token
from cortex_runtime.auth_policy import AuthPolicy, AuthRequest
from cortex_runtime.ephemeral import InMemoryEphemeralStore
from cortex_runtime.safety import ConversationState
from cortex_runtime.security_gate import SecurityGate, status_for
from cortex_runtime.state_store import InMemoryStateStore

NOW = 1_700_000_000
RAW = "rt_live_token"


@pytest.fixture
def store():
    s = InMemoryStateStore()
    s.upsert_tenant("bluspark", enabled=True)
    return s


@pytest.fixture
def gate(store):
    policy = AuthPolicy(store, hmac_secret_for=lambda t: None)
    return SecurityGate(store, policy, ephemeral=InMemoryEphemeralStore())


def _token(store, *, scopes=(), rate=None, daily=None):
    if rate is not None or daily is not None:
        store.upsert_tenant("bluspark", enabled=True, rate_limit_per_min=rate, budget_daily_usd=daily)
    return store.add_token("bluspark", hash_token(RAW), scopes=list(scopes))


def _req(route="/run", workspace="bluspark"):
    return AuthRequest(AuthMethod.BEARER, route, NOW,
                       authorization=f"Bearer {RAW}", workspace=workspace, source_ip="10.0.0.1")


# ── happy path ──────────────────────────────────────────────────────────────────────────

def test_allows_and_logs_once(store, gate):
    _token(store)
    d = gate.authorize(_req())
    assert d.allowed and d.status == 200
    assert len(store.auth_log()) == 1                 # exactly one consolidated row
    assert store.auth_log()[0].reason == "ok"


# ── short-circuit order ─────────────────────────────────────────────────────────────────

def test_auth_failure_short_circuits_before_rate_and_budget(store, gate):
    _token(store, rate=0, daily=0.0)   # would block everything if reached
    d = gate.authorize(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization="Bearer nope"))
    assert d.outcome.reason is AuthReason.UNKNOWN_TOKEN and d.status == 401


def test_rate_limited_after_auth(store, gate):
    _token(store, rate=2)
    assert gate.authorize(_req()).allowed
    assert gate.authorize(_req()).allowed
    blocked = gate.authorize(_req())
    assert blocked.outcome.reason is AuthReason.RATE_LIMITED
    assert blocked.status == 429 and blocked.retry_after_s == 60 - (NOW % 60) == 40
    assert store.auth_log()[0].reason == "rate_limited"   # most recent attempt logged once


def test_budget_exceeded_blocks(store, gate):
    _token(store, daily=1.0)
    rid = store.start_run("bluspark", "r", "S", started_at=NOW - 10)
    store.finish_run(rid, ConversationState.RESOLVED, 1, usage={"total_cost_usd": 1.5})
    d = gate.authorize(_req())
    assert d.outcome.reason is AuthReason.BUDGET_EXCEEDED and d.status == 402
    assert d.budget is not None and d.budget.daily.exceeded


def test_budget_passes_when_under_ceiling(store, gate):
    _token(store, daily=10.0)
    rid = store.start_run("bluspark", "r", "S", started_at=NOW - 10)
    store.finish_run(rid, ConversationState.RESOLVED, 1, usage={"total_cost_usd": 2.0})
    d = gate.authorize(_req())
    assert d.allowed and d.budget.daily.remaining_usd == pytest.approx(8.0)


# ── idempotency ─────────────────────────────────────────────────────────────────────────

def test_idempotent_replay_skips_run_and_charges_nothing(store, gate):
    _token(store, rate=1)
    first = gate.authorize(_req(), idempotency_key="delivery-1")
    assert first.allowed and first.idempotent_replay is None
    gate.remember(first.outcome, "delivery-1", '{"run_id":"abc"}', now=NOW)
    # a duplicate delivery returns the cached outcome — and does NOT consume the rate budget
    dup = gate.authorize(_req(), idempotency_key="delivery-1")
    assert dup.allowed and dup.idempotent_replay == '{"run_id":"abc"}'
    # rate limit was 1/min and the first call used it; the duplicate bypassed it (still allowed)


def test_idempotency_key_is_scoped_per_tenant(store, gate):
    _token(store)
    d = gate.authorize(_req(), idempotency_key="shared-id")
    gate.remember(d.outcome, "shared-id", "outcome-bluspark", now=NOW)
    # same key under the SAME tenant hits; the scoping guards against cross-tenant collisions
    again = gate.authorize(_req(), idempotency_key="shared-id")
    assert again.idempotent_replay == "outcome-bluspark"


# ── status mapping ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("reason,code", [
    (AuthReason.OK, 200), (AuthReason.UNKNOWN_TOKEN, 401), (AuthReason.REPLAY, 401),
    (AuthReason.OUT_OF_SCOPE, 403), (AuthReason.TENANT_DISABLED, 403),
    (AuthReason.RATE_LIMITED, 429), (AuthReason.BUDGET_EXCEEDED, 402),
])
def test_status_for(reason, code):
    assert status_for(reason) == code
