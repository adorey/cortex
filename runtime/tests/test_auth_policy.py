"""The store-backed AuthPolicy boundary (ADR-004 §3.6/§3.7) — authenticate + authorize +
log. Clock-injected, store = InMemory, HMAC secret = an in-memory dict. No HTTP, no DB."""

from __future__ import annotations

import pytest

from cortex_runtime.auth import AuthMethod, AuthReason, hash_token, hmac_signature
from cortex_runtime.auth_policy import AuthPolicy, AuthRequest
from cortex_runtime.ephemeral import InMemoryEphemeralStore
from cortex_runtime.state_store import InMemoryStateStore

NOW = 1_700_000_000
HMAC_SECRET = "whsec_acme"
BODY = '{"issue":"BLUSUPP-3197"}'


@pytest.fixture
def store():
    s = InMemoryStateStore()
    s.upsert_tenant("acme", enabled=True)
    return s


@pytest.fixture
def policy(store):
    secrets = {"acme": HMAC_SECRET}
    return AuthPolicy(store, hmac_secret_for=secrets.get)


def _bearer(store, *, tenant="acme", scopes=(), revoked=False, expires_at=None):
    raw = "rt_live_secret_token"
    tid = store.add_token(tenant, hash_token(raw), scopes=list(scopes), expires_at=expires_at)
    if revoked:
        store.revoke_token(tid)
    return raw, tid


# ── Bearer path ───────────────────────────────────────────────────────────────────────

def test_bearer_ok(store, policy):
    raw, tid = _bearer(store)
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW,
                                   authorization=f"Bearer {raw}", workspace="acme"))
    assert out.ok and out.tenant == "acme" and out.token_id == tid
    assert out.admin is False   # a normal token carries no admin privilege


def test_bearer_admin_flag_propagates(store, policy):
    raw = "rt_live_master"
    store.add_token("acme", hash_token(raw), scopes=["acme"], admin=True)
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/tokens", NOW,
                                   authorization=f"Bearer {raw}", workspace="acme"))
    assert out.ok and out.admin is True


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer wrong-token", "Bearer "])
def test_bearer_unknown_token(store, policy, header):
    _bearer(store)
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization=header))
    assert out.reason is AuthReason.UNKNOWN_TOKEN and not out.ok


def test_bearer_revoked(store, policy):
    raw, _ = _bearer(store, revoked=True)
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization=f"Bearer {raw}"))
    assert out.reason is AuthReason.REVOKED_TOKEN


def test_bearer_expired(store, policy):
    raw, _ = _bearer(store, expires_at=str(NOW - 1))
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization=f"Bearer {raw}"))
    assert out.reason is AuthReason.REVOKED_TOKEN


def test_bearer_not_yet_expired(store, policy):
    raw, _ = _bearer(store, expires_at=str(NOW + 60))
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization=f"Bearer {raw}",
                                   workspace="acme"))
    assert out.ok


def test_bearer_disabled_tenant(store, policy):
    raw, _ = _bearer(store)
    store.upsert_tenant("acme", enabled=False)
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization=f"Bearer {raw}",
                                   workspace="acme"))
    assert out.reason is AuthReason.TENANT_DISABLED


def test_bearer_out_of_scope(store, policy):
    raw, _ = _bearer(store, scopes=["acme"])
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization=f"Bearer {raw}",
                                   workspace="other-workspace"))
    assert out.reason is AuthReason.OUT_OF_SCOPE


def test_bearer_scope_allows_listed_workspace(store, policy):
    raw, _ = _bearer(store, scopes=["acme", "monitoring"])
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/runs", NOW, authorization=f"Bearer {raw}",
                                   workspace="monitoring"))
    assert out.ok


def test_bearer_no_workspace_is_in_scope(store, policy):
    # a global monitoring call names no workspace → scope check passes
    raw, _ = _bearer(store, scopes=["acme"])
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/auth-log", NOW,
                                   authorization=f"Bearer {raw}"))
    assert out.ok


# ── HMAC path ─────────────────────────────────────────────────────────────────────────

def _hmac_req(route="/webhook/acme", *, ts=NOW, body=BODY, secret=HMAC_SECRET, tenant="acme"):
    sig = hmac_signature(secret, str(ts), body)
    return AuthRequest(AuthMethod.HMAC, route, NOW, tenant=tenant,
                       timestamp=str(ts), signature=sig, body=body)


def test_hmac_ok(policy):
    out = policy.check(_hmac_req())
    assert out.ok and out.tenant == "acme"


def test_hmac_unknown_tenant(policy):
    out = policy.check(_hmac_req(tenant="ghost"))
    assert out.reason is AuthReason.UNKNOWN_TOKEN


def test_hmac_no_tenant_claimed(policy):
    out = policy.check(_hmac_req(tenant=None))
    assert out.reason is AuthReason.UNKNOWN_TOKEN


def test_hmac_disabled_tenant(store, policy):
    store.upsert_tenant("acme", enabled=False)
    out = policy.check(_hmac_req())
    assert out.reason is AuthReason.TENANT_DISABLED


def test_hmac_bad_signature(policy):
    out = policy.check(_hmac_req(secret="wrong-secret"))
    assert out.reason is AuthReason.INVALID_SIGNATURE


def test_hmac_stale_timestamp(policy):
    out = policy.check(_hmac_req(ts=NOW - 600))
    assert out.reason is AuthReason.STALE_TIMESTAMP


def test_hmac_no_secret_configured(store):
    pol = AuthPolicy(store, hmac_secret_for=lambda t: None)
    out = pol.check(_hmac_req())
    assert out.reason is AuthReason.UNKNOWN_TOKEN


def test_hmac_replay_rejected_when_nonce_cache_present(store):
    pol = AuthPolicy(store, hmac_secret_for={"acme": HMAC_SECRET}.get,
                     ephemeral=InMemoryEphemeralStore())
    req = _hmac_req()                       # same timestamp+body+secret → same signature
    assert pol.check(req).ok                # first delivery accepted
    assert pol.check(req).reason is AuthReason.REPLAY   # exact replay caught


def test_hmac_no_replay_check_without_nonce_cache(policy):
    # Without an ephemeral store the window still bounds replay, but exact replays inside it pass.
    req = _hmac_req()
    assert policy.check(req).ok
    assert policy.check(req).ok


# ── logging: every attempt lands in auth_log with the verdict ───────────────────────────

def test_every_attempt_is_logged(store, policy):
    raw, _ = _bearer(store)
    policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization=f"Bearer {raw}",
                             workspace="acme", source_ip="10.0.0.1", request_id="req-1"))
    policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization="Bearer nope",
                             source_ip="10.0.0.2"))
    log = store.auth_log()
    assert [(e.result, e.reason) for e in log] == [
        ("rejected", "unknown_token"), ("accepted", "ok")]   # recent first
    accepted = [e for e in log if e.result == "accepted"][0]
    assert (accepted.route, accepted.method, accepted.source_ip, accepted.request_id) == \
           ("/run", "bearer", "10.0.0.1", "req-1")


def test_log_uses_at_or_falls_back_to_now(store, policy):
    raw, _ = _bearer(store)
    policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization=f"Bearer {raw}",
                             workspace="acme", at="2026-06-03T10:00:00Z"))
    policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW, authorization="Bearer nope"))
    ats = [e.at for e in store.auth_log()]
    assert ats == [str(NOW), "2026-06-03T10:00:00Z"]   # recent first: fallback, then explicit
