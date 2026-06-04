"""API security — the per-tenant budget cap (ADR-004 §3.5).

The control that actually protects the wallet: **before a run, refuse if the tenant has
already spent its ceiling** over a rolling window. It reuses the ``cost_usd`` we already
persist per run (ADR-003) — no separate spend table — summed via ``StateStore.spent_since``.

Enforcement is **accumulated-spend based**: a run's exact cost is only known *after* it
finishes, so the cap stops the *next* run once the window is over budget; the per-run guards
(iteration cap, ``max_tokens`` — ADR-002 §3.3) bound any single run from blowing it open.

Windows are **rolling** (last 24 h / last 30 d), not calendar — simpler and clock-injected,
so the evaluation is deterministic under test. ``now`` is unix seconds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

DAY_S = 24 * 60 * 60
MONTH_S = 30 * DAY_S


class _SpendSource(Protocol):
    def spent_since(self, workspace: str, since_epoch: int) -> float: ...


@dataclass(frozen=True)
class BudgetWindow:
    """Spend vs ceiling for one rolling window."""
    spent_usd: float
    ceiling_usd: float

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.ceiling_usd - self.spent_usd)

    @property
    def exceeded(self) -> bool:
        return self.spent_usd >= self.ceiling_usd


@dataclass(frozen=True)
class BudgetDecision:
    """The verdict for a tenant. ``daily`` / ``monthly`` are populated only for the ceilings
    that are configured (``None`` ceiling ⇒ that window is not enforced and stays ``None``)."""
    allowed: bool
    daily: Optional[BudgetWindow] = None
    monthly: Optional[BudgetWindow] = None


def check_budget(source: _SpendSource, tenant, *, now: int) -> BudgetDecision:
    """Evaluate a tenant's rolling spend against its daily/monthly ceilings.

    ``tenant`` is a :class:`~cortex_runtime.state_store.TenantRecord` (or ``None``). With no
    tenant config, or no ceilings set, there is nothing to enforce → ``allowed=True``."""
    if tenant is None:
        return BudgetDecision(True)

    daily = monthly = None
    exceeded = False
    if tenant.budget_daily_usd:
        daily = BudgetWindow(source.spent_since(tenant.tenant, now - DAY_S), tenant.budget_daily_usd)
        exceeded = exceeded or daily.exceeded
    if tenant.budget_monthly_usd:
        monthly = BudgetWindow(source.spent_since(tenant.tenant, now - MONTH_S), tenant.budget_monthly_usd)
        exceeded = exceeded or monthly.exceeded
    return BudgetDecision(not exceeded, daily, monthly)
