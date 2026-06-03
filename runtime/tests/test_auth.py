"""The auth core (ADR-004 §3.1–3.2) — pure, deterministic, clock-injected. No DB, no HTTP."""

from __future__ import annotations

import pytest

from cortex_runtime.auth import (
    AuthMethod,
    AuthOutcome,
    AuthReason,
    hash_token,
    hmac_signature,
    parse_bearer,
    timestamp_in_window,
    token_matches,
    verify_hmac,
)

SECRET = "whsec_super_secret"
BODY = '{"issue":"BLUSUPP-3197","event":"created"}'
NOW = 1_700_000_000


# ── HMAC sign/verify ──────────────────────────────────────────────────────────────────

def test_signature_is_deterministic_and_hex():
    sig = hmac_signature(SECRET, str(NOW), BODY)
    assert sig == hmac_signature(SECRET, str(NOW), BODY)
    assert len(sig) == 64 and all(c in "0123456789abcdef" for c in sig)


def test_verify_roundtrip_ok():
    sig = hmac_signature(SECRET, str(NOW), BODY)
    assert verify_hmac(SECRET, str(NOW), BODY, sig, now=NOW) is AuthReason.OK


def test_verify_accepts_sha256_prefix():
    sig = hmac_signature(SECRET, str(NOW), BODY)
    assert verify_hmac(SECRET, str(NOW), BODY, f"sha256={sig}", now=NOW) is AuthReason.OK


@pytest.mark.parametrize("mutate", [
    lambda s: s[:-1] + ("0" if s[-1] != "0" else "1"),  # flip last hex char
    lambda s: "",                                         # empty
    lambda s: "sha256=deadbeef",                          # wrong
])
def test_verify_rejects_bad_signature(mutate):
    good = hmac_signature(SECRET, str(NOW), BODY)
    assert verify_hmac(SECRET, str(NOW), BODY, mutate(good), now=NOW) is AuthReason.INVALID_SIGNATURE


def test_verify_rejects_tampered_body():
    sig = hmac_signature(SECRET, str(NOW), BODY)
    assert verify_hmac(SECRET, str(NOW), BODY + " ", sig, now=NOW) is AuthReason.INVALID_SIGNATURE


def test_verify_rejects_wrong_secret():
    sig = hmac_signature(SECRET, str(NOW), BODY)
    assert verify_hmac("other", str(NOW), BODY, sig, now=NOW) is AuthReason.INVALID_SIGNATURE


# ── replay window ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("skew", [0, 299, -299, 300, -300])
def test_timestamp_within_window(skew):
    assert timestamp_in_window(str(NOW + skew), NOW) is True


@pytest.mark.parametrize("skew", [301, -301, 10_000])
def test_timestamp_outside_window(skew):
    assert timestamp_in_window(str(NOW + skew), NOW) is False


def test_malformed_timestamp_is_out_of_window():
    assert timestamp_in_window("not-a-number", NOW) is False
    assert timestamp_in_window("", NOW) is False


def test_verify_rejects_stale_before_checking_signature():
    # A correct signature but a stale timestamp is still rejected — window is checked first.
    stale = str(NOW - 600)
    sig = hmac_signature(SECRET, stale, BODY)
    assert verify_hmac(SECRET, stale, BODY, sig, now=NOW) is AuthReason.STALE_TIMESTAMP


# ── Bearer tokens (stored hashed) ─────────────────────────────────────────────────────

def test_hash_token_is_sha256_hex_and_never_the_raw():
    h = hash_token("rt_live_abc123")
    assert len(h) == 64 and h != "rt_live_abc123"
    assert h == hash_token("rt_live_abc123")


def test_token_matches_constant_time():
    h = hash_token("rt_live_abc123")
    assert token_matches("rt_live_abc123", h) is True
    assert token_matches("rt_live_wrong", h) is False
    assert token_matches("rt_live_abc123", "") is False


@pytest.mark.parametrize("header,expected", [
    ("Bearer rt_live_abc123", "rt_live_abc123"),
    ("bearer rt_live_abc123", "rt_live_abc123"),   # case-insensitive scheme
    ("Bearer    spaced_token", "spaced_token"),
    ("Basic abc", None),
    ("rt_live_no_scheme", None),
    ("Bearer ", None),
    ("", None),
    (None, None),
])
def test_parse_bearer(header, expected):
    assert parse_bearer(header) == expected


# ── outcome value object ──────────────────────────────────────────────────────────────

def test_outcome_ok_mirrors_reason():
    ok = AuthOutcome(AuthReason.OK, AuthMethod.BEARER, tenant="bluspark", token_id="t1")
    assert ok.ok is True and ok.tenant == "bluspark"
    bad = AuthOutcome(AuthReason.UNKNOWN_TOKEN, AuthMethod.BEARER)
    assert bad.ok is False and bad.tenant is None
