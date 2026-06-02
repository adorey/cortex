"""Tests for the reference session orchestration — durable anti-recursion + audit (ADR-003)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.loop import AgentLoop, ModelTurn, ToolCall  # noqa: E402
from cortex_runtime.safety import ActionKind, ActionPolicy, ConversationState  # noqa: E402
from cortex_runtime.session import mark_human_reply, run_session  # noqa: E402
from cortex_runtime.state_store import InMemoryStateStore  # noqa: E402
from cortex_runtime.tools import Tool, ToolRegistry  # noqa: E402


class ScriptedModel:
    def __init__(self, turns):
        self.turns = list(turns)
        self.calls = 0

    def propose(self, system_prompt, history):
        turn = self.turns[self.calls]
        self.calls += 1
        return turn


def _registry():
    reg = ToolRegistry()
    reg.register(Tool("read_db", ActionKind.DB_READ, lambda **k: "rows"))
    reg.register(Tool("open_ticket", ActionKind.ISSUE_CREATE, lambda **k: "T-1"))
    return reg


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStateStore()
        self.loop = AgentLoop(_registry(), ActionPolicy())  # least-privilege

    def _run(self, model):
        return run_session(
            self.loop, model, self.store,
            workspace="acme", role="support-engineer", subject="ACME-7",
            system_prompt="sys", initial_input={"issue": "ACME-7"}, model_id="claude-opus-4-8", at="t0",
        )

    def test_gated_action_persists_awaiting_human(self):
        model = ScriptedModel([
            ModelTurn(tool_calls=[ToolCall("read_db")]),
            ModelTurn(tool_calls=[ToolCall("open_ticket", {"title": "bug"})]),  # gated → halt
        ])
        result = self._run(model)
        self.assertFalse(result.skipped)
        self.assertEqual(result.outcome.state, ConversationState.AWAITING_HUMAN)
        # state durably persisted
        self.assertEqual(self.store.get_conversation_state("acme", "ACME-7"),
                         ConversationState.AWAITING_HUMAN)
        # audit recorded, incl. the gated action
        trail = self.store.audit_trail(subject="ACME-7")
        self.assertEqual([(e.tool, e.gated) for e in trail],
                         [("read_db", False), ("open_ticket", True)])

    def test_second_invocation_skips_anti_recursion(self):
        # first run lands AWAITING_HUMAN
        self._run(ScriptedModel([ModelTurn(tool_calls=[ToolCall("open_ticket")])]))
        # a second trigger on the SAME subject (e.g. the agent's own comment) must NOT run
        second = self._run(ScriptedModel([ModelTurn(final_text="should not happen")]))
        self.assertTrue(second.skipped)
        self.assertIsNone(second.run_id)
        self.assertEqual(len(self.store.list_runs("acme")), 1)  # no second run started

    def test_human_reply_re_arms_then_resolves(self):
        self._run(ScriptedModel([ModelTurn(tool_calls=[ToolCall("open_ticket")])]))  # → awaiting-human
        mark_human_reply(self.store, "acme", "ACME-7")
        self.assertEqual(self.store.get_conversation_state("acme", "ACME-7"),
                         ConversationState.AWAITING_AGENT)
        # now the agent can run again and resolve
        third = self._run(ScriptedModel([ModelTurn(final_text="diagnosis delivered")]))
        self.assertFalse(third.skipped)
        self.assertEqual(third.outcome.state, ConversationState.RESOLVED)
        self.assertEqual(self.store.get_conversation_state("acme", "ACME-7"),
                         ConversationState.RESOLVED)


if __name__ == "__main__":
    unittest.main()
