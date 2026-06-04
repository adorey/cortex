"""API security — the authentication core (ADR-004 §3.1–3.2, §3.6).

The boundary checks the ADR mandates are split the same way the safety rails are: the
**deterministic, pure substance lives here, in code** — HMAC sign/verify, Bearer hashing,
the replay-window predicate, the reason taxonomy — with **no framework, no DB, no clock,
no secrets storage**. The FastAPI middleware and the StateStore tables (tenants / api_tokens
/ auth_log) are thin shells wired on top (increments #2–#3).

Every primitive is constant-time where it compares secrets (``hmac.compare_digest``) and
takes ``now`` as a parameter (a caller-supplied clock) so it is fully testable without
patching time. Nothing here reaches the network or the database.

    request → authenticate → replay/idempotency → rate-limit → budget cap → run
              ↑──────────────── all cheap, deterministic, pre-AI ──────────↑
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AuthMethod(str, Enum):
    """Which door a request came through — fixed per entry point (ADR-004 §2.1)."""

    HMAC = "hmac"        # webhook path: signed body + timestamp (Jira/GitHub/Stripe style)
    BEARER = "bearer"    # direct path: ``Authorization: Bearer <token>``


class AuthReason(str, Enum):
    """The verdict on an auth attempt — recorded verbatim in ``auth_log`` (§3.7).

    ``OK`` is the only accepting value; every other member is a rejection cause. The set is
    closed and stable so monitoring dashboards can group on it.
    """

    OK = "ok"
    INVALID_SIGNATURE = "invalid_signature"   # HMAC mismatch
    STALE_TIMESTAMP = "stale_timestamp"       # outside the ±window (or unpar.seable)
    REPLAY = "replay"                         # exact signature seen again inside the window
    UNKNOWN_TOKEN = "unknown_token"           # Bearer token (or webhook source) not on file
    REVOKED_TOKEN = "revoked_token"           # token revoked or expired
    OUT_OF_SCOPE = "out_of_scope"             # token not scoped to this workspace
    TENANT_DISABLED = "tenant_disabled"       # tenant exists but is turned off
    FORBIDDEN = "forbidden"                   # authenticated but lacks the privilege (e.g. non-admin)
    RATE_LIMITED = "rate_limited"             # sliding-window ceiling hit
    BUDGET_EXCEEDED = "budget_exceeded"       # tenant over its cost ceiling


DEFAULT_REPLAY_WINDOW_S = 300   # ±5 min tolerance on the signed timestamp (ADR-004 §3.1)


@dataclass(frozen=True)
class AuthOutcome:
    """The result of an auth check: the verdict plus the identity it resolved (if any).

    ``ok`` is a convenience mirror of ``reason is AuthReason.OK``. ``tenant`` / ``token_id``
    are populated on the Bearer path once a token is matched; they stay ``None`` on a
    rejection or on an unidentified caller (which still gets logged, with ``tenant=None``).
    """

    reason: AuthReason
    method: AuthMethod
    tenant: Optional[str] = None
    token_id: Optional[str] = None
    admin: bool = False         # the resolved Bearer token carries admin privilege

    @property
    def ok(self) -> bool:
        return self.reason is AuthReason.OK


# ── HMAC: webhook authenticity + integrity + anti-replay (§3.1) ──────────────────────────

def hmac_signature(secret: str, timestamp: str, body: str) -> str:
    """The canonical signature for a webhook delivery: ``HMAC_SHA256(secret, "ts.body")``.

    ``timestamp`` is the raw header value (unix seconds, as a string) and ``body`` is the
    **raw** request body — signing the parsed/re-serialised body would not match the sender.
    Returns lowercase hex (no ``sha256=`` prefix; callers add/strip that at the header)."""
    msg = f"{timestamp}.{body}".encode("utf-8")
    return _hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _strip_sig_prefix(signature: str) -> str:
    """Accept either ``sha256=<hex>`` (GitHub/Stripe convention) or a bare ``<hex>``."""
    sig = (signature or "").strip()
    return sig.split("=", 1)[1].strip() if "=" in sig else sig


def timestamp_in_window(timestamp: str, now: int, window: int = DEFAULT_REPLAY_WINDOW_S) -> bool:
    """True iff the signed timestamp is within ±``window`` seconds of ``now``.

    A malformed (non-integer) timestamp is treated as out of window — never trusted."""
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    return abs(now - ts) <= window


def verify_hmac(
    secret: str,
    timestamp: str,
    body: str,
    signature: str,
    *,
    now: int,
    window: int = DEFAULT_REPLAY_WINDOW_S,
) -> AuthReason:
    """Verify a webhook signature, returning the precise rejection reason or ``OK``.

    Order matches the ADR: the **timestamp window is checked first** (cheap, and it bounds
    the replay surface), then the signature in **constant time**. Exact-replay rejection
    (the nonce cache) is stateful and lives in the middleware (increment #4); this pure
    function covers authenticity, integrity and the window."""
    if not timestamp_in_window(timestamp, now, window):
        return AuthReason.STALE_TIMESTAMP
    expected = hmac_signature(secret, timestamp, body)
    if not _hmac.compare_digest(expected, _strip_sig_prefix(signature)):
        return AuthReason.INVALID_SIGNATURE
    return AuthReason.OK


# ── Bearer: direct callers, tokens stored hashed (§3.2, §3.7) ────────────────────────────

def hash_token(token: str) -> str:
    """The at-rest form of a Bearer token: SHA-256 hex.

    The ``api_tokens`` table stores **only** this — never the raw value. The raw token is
    shown to the caller once at issuance; verification hashes the incoming token and compares
    (constant-time) against the stored hash, so a DB leak does not expose usable tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_matches(token: str, stored_hash: str) -> bool:
    """Constant-time check that ``token`` hashes to ``stored_hash``."""
    return _hmac.compare_digest(hash_token(token), (stored_hash or ""))


def parse_bearer(header: Optional[str]) -> Optional[str]:
    """Extract the token from an ``Authorization: Bearer <token>`` header, or ``None``.

    Case-insensitive on the scheme; returns ``None`` for a missing/malformed/empty header
    so the caller maps it to ``UNKNOWN_TOKEN`` uniformly."""
    if not header:
        return None
    parts = header.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return None
    return parts[1].strip()
