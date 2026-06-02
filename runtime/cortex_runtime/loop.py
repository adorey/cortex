"""Agentic loop driver with the safety rails wrapped around it (ADR-002 §3.3).

The loop *mechanism* (tool_use → result → repeat) is what an Agent SDK provides — we
EMBED it, we do not reinvent it. The ``ModelClient`` protocol is the boundary where the
real SDK plugs in (its adapter implements ``propose``); this minimal driver exists so the
**rails** — iteration cap, action gating, state transitions — are deterministic and
testable without a live model.

What is uniquely ours and enforced here, never in the prompt:
  • a gated action (phase 1: anything beyond read + internal comment) HALTS the run and
    hands off to a human (state → AWAITING_HUMAN) — "no external action without validation";
  • exceeding the iteration cap forces ESCALATED;
  • the agent only ever runs when the state machine says an input awaits it (anti-recursion).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .safety import ActionPolicy, ConversationState, StateMachine
from .tools import ToolRegistry


@dataclass
class ToolCall:
    name: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelTurn:
    """One model step: either it requests tool calls, or it gives a final answer."""

    tool_calls: List[ToolCall] = field(default_factory=list)
    final_text: Optional[str] = None

    @property
    def is_final(self) -> bool:
        return self.final_text is not None


class ModelClient(Protocol):
    """The Agent SDK boundary. The real adapter delegates to the SDK; tests use a fake."""

    def propose(self, system_prompt: str, history: List[Dict[str, Any]]) -> ModelTurn:
        ...


@dataclass
class RunOutcome:
    state: ConversationState
    iterations: int
    actions_taken: List[Tuple[str, str]] = field(default_factory=list)   # (tool, kind)
    gated_action: Optional[Tuple[str, str]] = None                       # the one awaiting a human
    final_text: Optional[str] = None
    transcript: List[Dict[str, Any]] = field(default_factory=list)


class AgentLoop:
    def __init__(self, registry: ToolRegistry, policy: ActionPolicy, max_iterations: int = 12):
        self.registry = registry
        self.policy = policy
        self.max_iterations = max_iterations

    def run(self, system_prompt: str, initial_input: Dict[str, Any], model: ModelClient,
            machine: Optional[StateMachine] = None) -> RunOutcome:
        machine = machine or StateMachine()
        if not machine.can_trigger_agent():
            raise RuntimeError(f"agent may not run in state {machine.state.value} (anti-recursion)")

        history: List[Dict[str, Any]] = [{"role": "input", "content": initial_input}]
        actions: List[Tuple[str, str]] = []

        for i in range(1, self.max_iterations + 1):
            turn = model.propose(system_prompt, history)

            if turn.is_final:
                machine.transition(ConversationState.RESOLVED)
                history.append({"role": "agent", "content": turn.final_text})
                return RunOutcome(machine.state, i, actions, None, turn.final_text, history)

            for call in turn.tool_calls:
                tool = self.registry.get(call.name)
                if tool is None:
                    history.append({"role": "tool-error", "tool": call.name, "content": "unknown tool"})
                    continue

                if not self.policy.is_allowed(tool.kind):
                    # External effect without human validation is forbidden in phase 1.
                    machine.transition(ConversationState.AWAITING_HUMAN)
                    return RunOutcome(machine.state, i, actions, (call.name, tool.kind.value),
                                      None, history)

                result = tool.fn(**call.args)
                actions.append((call.name, tool.kind.value))
                history.append({"role": "tool-result", "tool": call.name, "content": result})

        # Ran out of iterations without resolving → forced escalation (§3.3).
        machine.transition(ConversationState.ESCALATED)
        return RunOutcome(machine.state, self.max_iterations, actions, None, None, history)
