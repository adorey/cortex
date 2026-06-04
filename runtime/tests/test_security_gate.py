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
    s.upsert_tenant("acme", enabled=True)
    return s


@pytest.fixture
def gate(store):
    policy = AuthPolicy(store, hmac_secret_for=lambda t: None)
    return SecurityGate(store, policy, ephemeral=InMemoryEphemeralStore())


def _token(store, *, scopes=(), rate=None, daily=None):
    if rate is not None or daily is not None:
        store.upsert_tenant("acme", enabled=True, rate_limit_per_min=rate, budget_daily_usd=daily)
    return store.add_token("acme", hash_token(RAW), scopes=list(scopes))


def _req(route="/run", workspace="acme"):
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
    rid = store.start_run("acme", "r", "S", started_at=NOW - 10)
    store.finish_run(rid, ConversationState.RESOLVED, 1, usage={"total_cost_usd": 1.5})
    d = gate.authorize(_req())
    assert d.outcome.reason is AuthReason.BUDGET_EXCEEDED and d.status == 402
    assert d.budget is not None and d.budget.daily.exceeded


def test_budget_passes_when_under_ceiling(store, gate):
    _token(store, daily=10.0)
    rid = store.start_run("acme", "r", "S", started_at=NOW - 10)
    store.finish_run(rid, ConversationState.RESOLVED, 1, usage={"total_cost_usd": 2.0})
    d = gate.authorize(_req())
    assert d.allowed and d.budget.daily.remaining_usd == pytest.approx(8.0)


# ── idempotency (atomic claim) ──────────────────────────────────────────────────────────

def test_claim_dedups_in_flight_without_charging_rate(store, gate):
    _token(store, rate=1)
    # first delivery CLAIMS the key with its pre-minted run_id — not yet a duplicate
    first = gate.authorize(_req(), idempotency_key="delivery-1", run_id="runA")
    assert first.allowed and not first.is_duplicate
    # a concurrent duplicate (run still in flight, no result yet) is caught BEFORE rate-limit:
    # it points at the original run_id and carries no result.
    dup = gate.authorize(_req(), idempotency_key="delivery-1", run_id="runB")
    assert dup.is_duplicate
    assert dup.idempotent_entry == {"run_id": "runA", "result": None}
    # rate was 1/min and the first claim used it, yet the duplicate is NOT rate-limited (it
    # short-circuited before the rate step) — proof a spammed retry can't fan out into runs.


def test_completed_run_returns_cached_result(store, gate):
    _token(store)
    gate.authorize(_req(), idempotency_key="d2", run_id="runA")
    gate.remember(idempotency_key="d2", tenant="acme", run_id="runA",
                  result={"state": "resolved"}, now=NOW)
    dup = gate.authorize(_req(), idempotency_key="d2", run_id="runB")
    assert dup.is_duplicate
    assert dup.idempotent_entry == {"run_id": "runA", "result": {"state": "resolved"}}


def test_idempotency_key_is_scoped_per_tenant(store, gate):
    # same delivery id, two tenants → no collision (keys are tenant-scoped)
    _token(store)
    store.upsert_tenant("other", enabled=True)
    gate.authorize(_req(), idempotency_key="shared-id", run_id="runHost")
    # 'acme' claimed it; an identical id is a duplicate for acme…
    assert gate.authorize(_req(), idempotency_key="shared-id", run_id="runX").is_duplicate
    # …but the scoping means a different tenant would not collide (verified via the key helper)
    assert gate._idem_key_for("acme", "shared-id") != gate._idem_key_for("other", "shared-id")


# ── status mapping ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("reason,code", [
    (AuthReason.OK, 200), (AuthReason.UNKNOWN_TOKEN, 401), (AuthReason.REPLAY, 401),
    (AuthReason.OUT_OF_SCOPE, 403), (AuthReason.TENANT_DISABLED, 403),
    (AuthReason.RATE_LIMITED, 429), (AuthReason.BUDGET_EXCEEDED, 402),
])
def test_status_for(reason, code):
    assert status_for(reason) == code
