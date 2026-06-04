"""API security — ephemeral, TTL-native state (ADR-004 §3.3–3.4, ADR-005 §2.2).

Three perimeter controls share one trait: their state is **short-lived and high-churn** —
rate-limit counters, the anti-replay nonce cache, and idempotency keys. They do not belong
in the durable StateStore long-term; ADR-005 pins them to **Redis** in production. Here they
sit behind a small :class:`EphemeralStore` boundary (the SecretProvider / JobQueue
discipline) with an **in-process backend** for a single node and tests — a Redis backend is
a drop-in later.

Every method takes ``now`` (unix seconds) as an injected clock, so expiry/windowing is
fully deterministic under test. Nothing here reaches the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

RATE_WINDOW_S = 60   # rate limits are expressed per-minute (TenantRecord.rate_limit_per_min)


class EphemeralStore(Protocol):
    """The three TTL primitives the perimeter needs. A Redis backend maps each to a native
    op (``INCR``+``EXPIRE``, ``SET NX EX``, ``GET``/``SETEX``)."""

    def incr_window(self, key: str, *, now: int, window_s: int) -> int: ...
    def seen_nonce(self, key: str, *, now: int, ttl_s: int) -> bool: ...
    def get_idempotent(self, key: str, *, now: int) -> Optional[str]: ...
    def put_idempotent(self, key: str, value: str, *, now: int, ttl_s: int) -> None: ...
    def claim_idempotent(self, key: str, value: str, *, now: int, ttl_s: int) -> Optional[str]: ...


class InMemoryEphemeralStore:
    """Single-node / test backend. Bounded by lazy pruning of expired entries; for multi-node
    deployments swap in Redis (TTLs there evict automatically)."""

    def __init__(self):
        self._counters: dict = {}   # (key, bucket) -> count
        self._nonces: dict = {}     # key -> expires_at
        self._idem: dict = {}       # key -> (value, expires_at)

    # — fixed-window counter (rate-limit) —
    def incr_window(self, key: str, *, now: int, window_s: int) -> int:
        bucket = now // window_s
        self._counters = {k: v for k, v in self._counters.items() if k[1] >= bucket}  # prune old
        k = (key, bucket)
        self._counters[k] = self._counters.get(k, 0) + 1
        return self._counters[k]

    # — one-shot nonce (anti-replay): True iff already seen within its TTL —
    def seen_nonce(self, key: str, *, now: int, ttl_s: int) -> bool:
        self._nonces = {n: exp for n, exp in self._nonces.items() if exp > now}  # prune expired
        if key in self._nonces:
            return True
        self._nonces[key] = now + ttl_s
        return False

    # — idempotency (key -> prior outcome) —
    def get_idempotent(self, key: str, *, now: int) -> Optional[str]:
        entry = self._idem.get(key)
        if entry and entry[1] > now:
            return entry[0]
        return None

    def put_idempotent(self, key: str, value: str, *, now: int, ttl_s: int) -> None:
        self._idem = {k: v for k, v in self._idem.items() if v[1] > now}  # prune expired
        self._idem[key] = (value, now + ttl_s)

    # — atomic claim (SET NX): None ⇒ we claimed it; else the value already on file (a duplicate).
    #   This is what lets the boundary dedup duplicates *before* they spawn a run — the expensive
    #   thing — instead of only after one completes (ADR-004 §3.3, the in-flight gap).
    def claim_idempotent(self, key: str, value: str, *, now: int, ttl_s: int) -> Optional[str]:
        self._idem = {k: v for k, v in self._idem.items() if v[1] > now}  # prune expired
        existing = self._idem.get(key)
        if existing is not None:
            return existing[0]
        self._idem[key] = (value, now + ttl_s)
        return None


@dataclass(frozen=True)
class RateDecision:
    """The verdict of a rate-limit check. ``retry_after_s`` is meaningful only when blocked."""
    allowed: bool
    count: int
    limit: int
    retry_after_s: int


def check_rate(store: EphemeralStore, key: str, limit_per_min: Optional[int], *, now: int) -> RateDecision:
    """Fixed-window per-minute rate-limit. ``limit_per_min`` falsy/≤0 ⇒ unlimited (allowed).

    The counter increments on every call (including over-limit ones) — a caller that keeps
    hammering stays blocked until the window rolls over, which is the intended back-off."""
    if not limit_per_min or limit_per_min <= 0:
        return RateDecision(True, 0, 0, 0)
    count = store.incr_window(f"rl:{key}", now=now, window_s=RATE_WINDOW_S)
    allowed = count <= limit_per_min
    retry_after = 0 if allowed else RATE_WINDOW_S - (now % RATE_WINDOW_S)
    return RateDecision(allowed, count, limit_per_min, retry_after)
