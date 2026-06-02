"""Reference orchestration tying the loop to the StateStore (ADR-002 §3.3, ADR-003 §3.3).

This is the durable wiring of one invocation: load conversation state → guard against
self-triggering (anti-recursion) → run the loop → record actions → persist the new state.
It is a *reference*: the host's trigger/queue/worker (ADR-002 §3.7) may wrap it differently,
but the load → guard → run → record → persist sequence is the contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .loop import AgentLoop, ModelClient, RunOutcome
from .safety import ConversationState, StateMachine
from .state_store import StateStore


@dataclass
class SessionResult:
    run_id: Optional[str]
    outcome: Optional[RunOutcome]
    skipped: bool = False
    reason: str = ""


def run_session(
    loop: AgentLoop,
    model: ModelClient,
    store: StateStore,
    *,
    workspace: str,
    role: str,
    subject: str,
    system_prompt: str,
    initial_input: Dict[str, Any],
    model_id: Optional[str] = None,
    at: str = "",
) -> SessionResult:
    """Run one invocation with durable conversation state + audit.

    If the persisted state is not ``awaiting-agent`` (e.g. the trigger fired off the agent's
    own previous output), the run is **skipped** — the durable anti-recursion guarantee.
    """
    persisted = store.get_conversation_state(workspace, subject)
    machine = StateMachine(persisted) if persisted is not None else StateMachine()

    if not machine.can_trigger_agent():
        return SessionResult(None, None, skipped=True,
                             reason=f"state '{machine.state.value}' is not awaiting-agent (anti-recursion)")

    run_id = store.start_run(workspace, role, subject, model_id)
    outcome = loop.run(system_prompt, initial_input, model, machine=machine)

    for tool, kind in outcome.actions_taken:
        store.record_action(run_id, tool, kind, gated=False, at=at)
    if outcome.gated_action:
        store.record_action(run_id, outcome.gated_action[0], outcome.gated_action[1], gated=True, at=at)

    store.set_conversation_state(workspace, subject, outcome.state)
    store.finish_run(run_id, outcome.state, outcome.iterations)
    return SessionResult(run_id, outcome)


def mark_human_reply(store: StateStore, workspace: str, subject: str) -> None:
    """A human acted on an awaiting-human subject → re-arm the agent (anti-recursion exit)."""
    current = store.get_conversation_state(workspace, subject) or ConversationState.AWAITING_AGENT
    machine = StateMachine(current)
    if machine.state == ConversationState.AWAITING_HUMAN:
        machine.human_replied()
        store.set_conversation_state(workspace, subject, machine.state)
