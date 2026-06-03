"""The admin CLI (ADR-004 §3.7) — minted tokens verify through the gate; only a hash is stored."""

from __future__ import annotations

import re

import pytest

from cortex_runtime import admin
from cortex_runtime.auth import AuthMethod, AuthReason, hash_token
from cortex_runtime.auth_policy import AuthPolicy, AuthRequest
from cortex_runtime.state_store import InMemoryStateStore

NOW = 1_700_000_000


def test_minted_token_is_prefixed_and_unique():
    a, b = admin._mint_raw_token(), admin._mint_raw_token()
    assert a.startswith("rt_live_") and b.startswith("rt_live_") and a != b


def test_minted_token_authenticates_and_is_stored_hashed(monkeypatch, capsys):
    store = InMemoryStateStore()
    store.upsert_tenant("bluspark", enabled=True)
    monkeypatch.setattr(admin, "store_from_env", lambda: store)

    assert admin.main(["token", "bluspark", "--scope", "bluspark"]) == 0
    raw = re.search(r"(rt_live_[\w-]+)", capsys.readouterr().out).group(1)

    # the raw token never lands in the DB — only its hash
    rec = store.get_token_by_hash(hash_token(raw))
    assert rec is not None and rec.tenant == "bluspark" and rec.scopes == ["bluspark"]
    assert all(t.token_hash != raw for t in store.list_tokens("bluspark"))

    # and it authenticates through the policy
    policy = AuthPolicy(store, hmac_secret_for=lambda t: None)
    out = policy.check(AuthRequest(AuthMethod.BEARER, "/run", NOW,
                                   authorization=f"Bearer {raw}", workspace="bluspark"))
    assert out.reason is AuthReason.OK


def test_token_for_unknown_tenant_errors(monkeypatch):
    store = InMemoryStateStore()
    monkeypatch.setattr(admin, "store_from_env", lambda: store)
    assert admin.main(["token", "ghost"]) == 2


def test_tenant_command_upserts(monkeypatch, capsys):
    store = InMemoryStateStore()
    monkeypatch.setattr(admin, "store_from_env", lambda: store)
    assert admin.main(["tenant", "bluspark", "--daily", "20", "--rate", "60"]) == 0
    t = store.get_tenant("bluspark")
    assert (t.budget_daily_usd, t.rate_limit_per_min, t.enabled) == (20.0, 60, True)
