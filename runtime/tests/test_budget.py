"""Budget cap (ADR-004 §3.5) — rolling-window spend vs per-tenant ceiling. Pure evaluator
over a store's ``spent_since``; exercised with a real InMemoryStateStore + injected clock."""

from __future__ import annotations

import pytest

from cortex_runtime.budget import DAY_S, MONTH_S, BudgetWindow, check_budget
from cortex_runtime.safety import ConversationState
from cortex_runtime.state_store import InMemoryStateStore, TenantRecord

NOW = 1_700_000_000


def _spend(store, workspace, amount, *, at):
    rid = store.start_run(workspace, "r", "S", started_at=at)
    store.finish_run(rid, ConversationState.RESOLVED, 1, usage={"total_cost_usd": amount})


# ── spent_since on the store ────────────────────────────────────────────────────────────

def test_spent_since_windows_by_started_at():
    store = InMemoryStateStore()
    _spend(store, "acme", 1.0, at=NOW - 10)            # inside 24h
    _spend(store, "acme", 2.0, at=NOW - DAY_S - 100)   # outside 24h
    _spend(store, "other", 5.0, at=NOW)                    # different workspace
    assert store.spent_since("acme", NOW - DAY_S) == pytest.approx(1.0)
    assert store.spent_since("acme", NOW - MONTH_S) == pytest.approx(3.0)
    assert store.spent_since("acme", NOW + 1) == 0.0


# ── pure window arithmetic ──────────────────────────────────────────────────────────────

def test_budget_window_remaining_and_exceeded():
    w = BudgetWindow(spent_usd=3.0, ceiling_usd=5.0)
    assert w.remaining_usd == 2.0 and w.exceeded is False
    full = BudgetWindow(spent_usd=5.0, ceiling_usd=5.0)
    assert full.remaining_usd == 0.0 and full.exceeded is True   # >= is the cap


# ── check_budget verdicts ───────────────────────────────────────────────────────────────

def test_no_tenant_or_no_ceiling_is_allowed():
    store = InMemoryStateStore()
    assert check_budget(store, None, now=NOW).allowed
    bare = TenantRecord("acme")   # no ceilings configured
    d = check_budget(store, bare, now=NOW)
    assert d.allowed and d.daily is None and d.monthly is None


def test_daily_cap_blocks_when_exceeded():
    store = InMemoryStateStore()
    _spend(store, "acme", 4.0, at=NOW - 100)
    _spend(store, "acme", 1.5, at=NOW - 100)
    tenant = TenantRecord("acme", budget_daily_usd=5.0)
    d = check_budget(store, tenant, now=NOW)
    assert d.allowed is False
    assert d.daily.spent_usd == pytest.approx(5.5) and d.daily.exceeded


def test_daily_cap_allows_under_ceiling_and_reports_remaining():
    store = InMemoryStateStore()
    _spend(store, "acme", 2.0, at=NOW - 100)
    tenant = TenantRecord("acme", budget_daily_usd=5.0)
    d = check_budget(store, tenant, now=NOW)
    assert d.allowed and d.daily.remaining_usd == pytest.approx(3.0)


def test_old_spend_outside_window_does_not_count():
    store = InMemoryStateStore()
    _spend(store, "acme", 100.0, at=NOW - DAY_S - 1)   # yesterday+ → outside daily window
    tenant = TenantRecord("acme", budget_daily_usd=5.0)
    assert check_budget(store, tenant, now=NOW).allowed


def test_monthly_cap_independent_of_daily():
    store = InMemoryStateStore()
    # spread spend across the month, under daily each day but over the monthly ceiling
    for i in range(1, 6):
        _spend(store, "acme", 3.0, at=NOW - i * 2 * DAY_S)
    tenant = TenantRecord("acme", budget_daily_usd=5.0, budget_monthly_usd=10.0)
    d = check_budget(store, tenant, now=NOW)
    assert d.daily.exceeded is False        # nothing in the last 24h
    assert d.monthly.spent_usd == pytest.approx(15.0) and d.monthly.exceeded
    assert d.allowed is False               # monthly alone blocks
