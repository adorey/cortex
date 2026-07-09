"""Reference orchestration tying the loop to the StateStore (ADR-002 §3.3, ADR-003 §3.3).

This is the durable wiring of one invocation: load conversation state → guard against
self-triggering (anti-recursion) → run the loop → record actions → persist the new state.
It is a *reference*: the host's trigger/queue/worker (ADR-002 §3.7) may wrap it differently,
but the load → guard → run → record → persist sequence is the contract.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .loop import AgentLoop, ModelClient, RunOutcome
from .safety import ConversationState, StateMachine
from .state_store import StateStore

logger = logging.getLogger("cortex_runtime.session")


@dataclass
class SessionResult:
    run_id: Optional[str]
    outcome: Optional[RunOutcome]
    skipped: bool = False
    reason: str = ""
    error: Optional[str] = None


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
    handoff: bool = False,
    force: bool = False,
    at: str = "",
    run_id: Optional[str] = None,
) -> SessionResult:
    """Run one invocation with durable conversation state + audit.

    If the persisted state is not ``awaiting-agent`` (e.g. the trigger fired off the agent's
    own previous output), the run is **skipped** — the durable anti-recursion guarantee.

    ``run_id`` lets the async worker (ADR-005) pass a **pre-created** queued run so the API can
    return its id immediately; the anti-recursion check still runs here (the state may have
    changed between enqueue and execution), and a skip is recorded on that queued run. When
    ``run_id`` is ``None`` (synchronous path) the run record is created here.
    """
    persisted = store.get_conversation_state(workspace, subject)
    # force: treat as a fresh awaiting-agent run, ignoring persisted state (testing override).
    machine = StateMachine() if force else (
        StateMachine(persisted) if persisted is not None else StateMachine())

    if not force and not machine.can_trigger_agent():
        reason = f"state '{machine.state.value}' is not awaiting-agent (anti-recursion)"
        if run_id is not None:        # record the skip on the already-queued run
            store.skip_run(run_id, reason)
        return SessionResult(run_id, None, skipped=True, reason=reason)

    if run_id is None:
        run_id = store.start_run(workspace, role, subject, model_id)
    store.mark_running(run_id)

    try:
        outcome = loop.run(system_prompt, initial_input, model, machine=machine,
                           handoff_on_complete=handoff)
    except Exception as exc:  # never leave a dangling run — record the failure + log it
        logger.exception("run %s failed (workspace=%s subject=%s)", run_id, workspace, subject)
        store.fail_run(run_id, f"{type(exc).__name__}: {exc}")
        return SessionResult(run_id, None, error=f"{type(exc).__name__}: {exc}")

    # actions performed inside OUR loop (our tools), and actions performed inside the model
    # backend itself (e.g. the Claude Code CLI's own tools, surfaced via model.last_actions).
    for tool, kind in outcome.actions_taken:
        store.record_action(run_id, tool, kind, gated=False, at=at)
    for action in getattr(model, "last_actions", None) or []:
        # tolerate (tool, kind) or (tool, kind, gated) — CLI denials come through as gated
        tool, kind = action[0], action[1]
        store.record_action(run_id, tool, kind, gated=action[2] if len(action) > 2 else False, at=at)
    if outcome.gated_action:
        store.record_action(run_id, outcome.gated_action[0], outcome.gated_action[1], gated=True, at=at)

    store.set_conversation_state(workspace, subject, outcome.state)
    store.finish_run(run_id, outcome.state, outcome.iterations,
                     usage=getattr(model, "last_usage", None))
    return SessionResult(run_id, outcome)


def mark_human_reply(store: StateStore, workspace: str, subject: str) -> None:
    """A human acted on an awaiting-human subject → re-arm the agent (anti-recursion exit)."""
    current = store.get_conversation_state(workspace, subject) or ConversationState.AWAITING_AGENT
    machine = StateMachine(current)
    if machine.state == ConversationState.AWAITING_HUMAN:
        machine.human_replied()
        store.set_conversation_state(workspace, subject, machine.state)
