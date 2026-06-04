"""Safety rails — deterministic, in code, NOT in the prompt (ADR-002 §3.3).

The substance of a run is improvised by the LLM; the guardrails are not. This module
holds the three rails the ADR mandates:

  1. an **action policy** — phase 1 permits only reads + internal comments; everything
     with an external effect (dev tickets, customer replies, code writes) is gated;
  2. a **conversation state machine** with anti-recursion — the agent never reacts to its
     own output (awaiting-agent → awaiting-human → resolved);
  3. an **iteration cap** with forced escalation (enforced by the loop, see loop.py).
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional


class ActionKind(str, Enum):
    """What a tool *does*, classified by external effect — the gating axis.

    Granular on purpose: the more precise the taxonomy, the finer the autonomy a caller
    can grant per request (e.g. allow ``git-read`` but not ``git-push``; ``db-read`` but
    never ``db-write`` or ``delete``).
    """

    # ── Reads (low risk) ──────────────────────────────────────────────────
    CODE_READ = "code-read"             # read source / docs from the working tree
    DB_READ = "db-read"                 # query the DB read-only (anonymised/staging)
    ISSUE_READ = "issue-read"           # read tickets / comments
    GIT_READ = "git-read"               # clone / fetch / pull

    # ── Writes & communication (gated by default) ─────────────────────────
    INTERNAL_COMMENT = "internal-comment"  # post an internal note on a ticket
    ISSUE_EDIT = "issue-edit"           # edit issue fields / status / transition
    ISSUE_CREATE = "issue-create"       # create a (dev) ticket
    CUSTOMER_REPLY = "customer-reply"   # reply to the customer (external, visible)
    CODE_WRITE = "code-write"           # create / edit code in the working tree
    GIT_PUSH = "git-push"               # push a branch to the remote
    DB_WRITE = "db-write"               # mutate the database

    # ── Destructive (highest risk) ────────────────────────────────────────
    DELETE = "delete"                   # delete data / branches / files / tickets


# Least-privilege default when a request grants no explicit autonomy: reads + an internal
# comment only. Every write, push, mutation or deletion is gated until the caller opts in.
SAFE_DEFAULT_ACTIONS = frozenset({
    ActionKind.CODE_READ,
    ActionKind.DB_READ,
    ActionKind.ISSUE_READ,
    ActionKind.GIT_READ,
    ActionKind.INTERNAL_COMMENT,
})


class ActionPolicy:
    """Decides whether an action may run autonomously or must be gated for a human.

    Autonomy is **per request, not hard-coded**: the caller passes the set of actions the
    agent may take without human validation (see ``RunRequest.autonomy`` / the API payload).
    Omitting it falls back to ``SAFE_DEFAULT_ACTIONS`` — least privilege by default.
    """

    def __init__(self, allowed: Optional[Iterable[ActionKind]] = None):
        self.allowed = frozenset(allowed) if allowed is not None else SAFE_DEFAULT_ACTIONS

    def is_allowed(self, kind: ActionKind) -> bool:
        """True if the action may run now; False means it must await human validation."""
        return kind in self.allowed

    @classmethod
    def from_names(cls, names: Optional[Iterable[str]]) -> "ActionPolicy":
        """Build a policy from request-supplied action-kind strings (e.g. ``["code-read",
        "internal-comment"]``). ``None`` → least-privilege default. Raises ``ValueError``
        on an unknown action name."""
        if names is None:
            return cls()
        return cls({ActionKind(n) for n in names})


class ConversationState(str, Enum):
    AWAITING_AGENT = "awaiting-agent"   # a human/event input is ready for the agent
    AWAITING_HUMAN = "awaiting-human"   # the agent acted; a human must look before it runs again
    RESOLVED = "resolved"
    ESCALATED = "escalated"             # iteration cap hit → forced escalation


# Allowed transitions. Crucially, AWAITING_HUMAN cannot loop straight back to the agent
# without a human step — that is the anti-recursion guarantee.
_TRANSITIONS = {
    ConversationState.AWAITING_AGENT: {ConversationState.AWAITING_HUMAN,
                                       ConversationState.RESOLVED,
                                       ConversationState.ESCALATED},
    ConversationState.AWAITING_HUMAN: {ConversationState.AWAITING_AGENT,  # only via a human action
                                       ConversationState.RESOLVED},
    ConversationState.RESOLVED: set(),
    ConversationState.ESCALATED: {ConversationState.AWAITING_AGENT},      # human re-opens
}


class StateMachine:
    """Tracks a ticket's conversation state and refuses recursive self-triggers."""

    def __init__(self, state: ConversationState = ConversationState.AWAITING_AGENT):
        self.state = state

    def can_trigger_agent(self) -> bool:
        """The agent may run only when an input genuinely awaits it — never off its own output."""
        return self.state == ConversationState.AWAITING_AGENT

    def transition(self, to: ConversationState) -> None:
        if to not in _TRANSITIONS[self.state]:
            raise ValueError(f"illegal transition {self.state.value} → {to.value}")
        self.state = to

    def human_replied(self) -> None:
        """A human acted on an awaiting-human ticket, re-arming the agent (anti-recursion exit)."""
        self.transition(ConversationState.AWAITING_AGENT)
