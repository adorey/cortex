"""Tests for the agentic loop driver + rails — ADR-002 §3.3. Uses a scripted fake model
so the loop is deterministic without a live LLM (the real Agent SDK plugs in via ModelClient)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.loop import AgentLoop, ModelTurn, ToolCall  # noqa: E402
from cortex_runtime.safety import (  # noqa: E402
    ActionKind,
    ActionPolicy,
    ConversationState,
    StateMachine,
)
from cortex_runtime.tools import Tool, ToolRegistry  # noqa: E402


class ScriptedModel:
    """Returns pre-baked turns in order, ignoring the actual prompt/history."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = 0

    def propose(self, system_prompt, history):
        turn = self.turns[self.calls]
        self.calls += 1
        return turn


def _registry():
    reg = ToolRegistry()
    reg.register(Tool("read_db", ActionKind.DB_READ, lambda **k: "rows: 3"))
    reg.register(Tool("comment", ActionKind.INTERNAL_COMMENT, lambda **k: "posted"))
    reg.register(Tool("open_ticket", ActionKind.ISSUE_CREATE, lambda **k: "TICKET-9"))
    return reg


class LoopTests(unittest.TestCase):
    def test_read_comment_then_resolve(self):
        model = ScriptedModel([
            ModelTurn(tool_calls=[ToolCall("read_db")]),
            ModelTurn(tool_calls=[ToolCall("comment", {"body": "diagnosis"})]),
            ModelTurn(final_text="done, awaiting nothing"),
        ])
        loop = AgentLoop(_registry(), ActionPolicy())  # least-privilege default
        out = loop.run("sys", {"issue": "X-1"}, model)

        self.assertEqual(out.state, ConversationState.RESOLVED)
        self.assertEqual(out.actions_taken, [("read_db", "db-read"), ("comment", "internal-comment")])
        self.assertIsNone(out.gated_action)
        self.assertEqual(out.final_text, "done, awaiting nothing")

    def test_gated_action_halts_for_human(self):
        model = ScriptedModel([
            ModelTurn(tool_calls=[ToolCall("read_db")]),
            ModelTurn(tool_calls=[ToolCall("open_ticket", {"title": "bug"})]),  # gated in phase 1
            ModelTurn(final_text="should never reach here"),
        ])
        loop = AgentLoop(_registry(), ActionPolicy())  # default: issue-create gated
        out = loop.run("sys", {"issue": "X-2"}, model)

        self.assertEqual(out.state, ConversationState.AWAITING_HUMAN)
        self.assertEqual(out.gated_action, ("open_ticket", "issue-create"))
        self.assertEqual(out.actions_taken, [("read_db", "db-read")])  # ticket NOT created
        self.assertEqual(model.calls, 2)                              # loop stopped, never reached final

    def test_iteration_cap_forces_escalation(self):
        # model never finalizes: always asks for a read
        never_ends = ScriptedModel([ModelTurn(tool_calls=[ToolCall("read_db")])] * 10)
        loop = AgentLoop(_registry(), ActionPolicy(), max_iterations=3)
        out = loop.run("sys", {"issue": "X-3"}, never_ends)

        self.assertEqual(out.state, ConversationState.ESCALATED)
        self.assertEqual(out.iterations, 3)

    def test_explicit_allowlist_enables_a_gated_action(self):
        reg = ToolRegistry()
        reg.register(Tool("write_code", ActionKind.CODE_WRITE, lambda **k: "branch pushed"))
        model = ScriptedModel([
            ModelTurn(tool_calls=[ToolCall("write_code", {"branch": "fix/X-4"})]),
            ModelTurn(final_text="ok"),
        ])
        # the caller grants code-write for THIS run
        out = AgentLoop(reg, ActionPolicy.from_names(["code-write"])).run("sys", {}, model)
        self.assertEqual(out.state, ConversationState.RESOLVED)
        self.assertEqual(out.actions_taken, [("write_code", "code-write")])

    def test_unknown_tool_is_skipped_not_executed(self):
        model = ScriptedModel([
            ModelTurn(tool_calls=[ToolCall("ghost_tool")]),
            ModelTurn(final_text="recovered"),
        ])
        out = AgentLoop(_registry(), ActionPolicy()).run("sys", {}, model)
        self.assertEqual(out.state, ConversationState.RESOLVED)
        self.assertEqual(out.actions_taken, [])

    def test_handoff_ends_in_awaiting_human(self):
        model = ScriptedModel([ModelTurn(final_text="analysis delivered")])
        out = AgentLoop(_registry(), ActionPolicy()).run("sys", {}, model, handoff_on_complete=True)
        self.assertEqual(out.state, ConversationState.AWAITING_HUMAN)
        self.assertEqual(out.final_text, "analysis delivered")  # the analysis is still returned

    def test_refuses_to_run_when_not_awaiting_agent(self):
        model = ScriptedModel([ModelTurn(final_text="x")])
        loop = AgentLoop(_registry(), ActionPolicy())
        machine = StateMachine(ConversationState.AWAITING_HUMAN)  # agent already acted
        with self.assertRaises(RuntimeError):
            loop.run("sys", {}, model, machine=machine)


if __name__ == "__main__":
    unittest.main()
