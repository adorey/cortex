"""Ephemeral perimeter state (ADR-004 §3.3–3.4) — rate-limit counter, replay nonce,
idempotency. Clock-injected, in-memory backend. No DB, no Redis, no HTTP."""

from __future__ import annotations

import pytest

from cortex_runtime.ephemeral import InMemoryEphemeralStore, RATE_WINDOW_S, check_rate

NOW = 1_700_000_020   # 40s into a minute window (NOW % 60 == 40)


@pytest.fixture
def store():
    return InMemoryEphemeralStore()


# ── fixed-window counter / rate limiter ─────────────────────────────────────────────────

def test_incr_window_counts_within_bucket(store):
    assert store.incr_window("k", now=NOW, window_s=60) == 1
    assert store.incr_window("k", now=NOW + 5, window_s=60) == 2
    assert store.incr_window("k", now=NOW + 10, window_s=60) == 3


def test_incr_window_resets_next_bucket(store):
    store.incr_window("k", now=NOW, window_s=60)
    store.incr_window("k", now=NOW, window_s=60)
    # cross into the next minute → fresh count
    assert store.incr_window("k", now=NOW + 60, window_s=60) == 1


def test_check_rate_allows_then_blocks(store):
    decisions = [check_rate(store, "tok", 3, now=NOW) for _ in range(4)]
    assert [d.allowed for d in decisions] == [True, True, True, False]
    blocked = decisions[-1]
    assert blocked.count == 4 and blocked.limit == 3
    assert blocked.retry_after_s == RATE_WINDOW_S - (NOW % RATE_WINDOW_S) == 20


def test_check_rate_unlimited_when_no_limit(store):
    for _ in range(1000):
        assert check_rate(store, "tok", None, now=NOW).allowed
    assert check_rate(store, "tok", 0, now=NOW).allowed


def test_check_rate_is_per_key(store):
    check_rate(store, "a", 1, now=NOW)
    assert check_rate(store, "a", 1, now=NOW).allowed is False
    assert check_rate(store, "b", 1, now=NOW).allowed is True


# ── nonce (anti-replay) ─────────────────────────────────────────────────────────────────

def test_seen_nonce_first_false_then_true(store):
    assert store.seen_nonce("sig", now=NOW, ttl_s=300) is False
    assert store.seen_nonce("sig", now=NOW + 10, ttl_s=300) is True


def test_seen_nonce_expires_after_ttl(store):
    store.seen_nonce("sig", now=NOW, ttl_s=300)
    # past the TTL the nonce is forgotten → treated as fresh again
    assert store.seen_nonce("sig", now=NOW + 301, ttl_s=300) is False


# ── idempotency ─────────────────────────────────────────────────────────────────────────

def test_idempotency_roundtrip(store):
    assert store.get_idempotent("key", now=NOW) is None
    store.put_idempotent("key", '{"run_id":"abc"}', now=NOW, ttl_s=600)
    assert store.get_idempotent("key", now=NOW + 100) == '{"run_id":"abc"}'


def test_idempotency_expires(store):
    store.put_idempotent("key", "outcome", now=NOW, ttl_s=600)
    assert store.get_idempotent("key", now=NOW + 601) is None
