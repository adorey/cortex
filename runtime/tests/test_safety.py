"""Tests for the deterministic safety rails — ADR-002 §3.3.

Autonomy is per-request (an allowlist of action kinds), not a hard-coded phase.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.safety import (  # noqa: E402
    SAFE_DEFAULT_ACTIONS,
    ActionKind,
    ActionPolicy,
    ConversationState,
    StateMachine,
)


class ActionPolicyTests(unittest.TestCase):
    def test_default_is_least_privilege(self):
        p = ActionPolicy()  # no autonomy granted
        # reads + internal comment allowed
        for kind in (ActionKind.CODE_READ, ActionKind.DB_READ, ActionKind.ISSUE_READ,
                     ActionKind.GIT_READ, ActionKind.INTERNAL_COMMENT):
            self.assertTrue(p.is_allowed(kind), kind)
        # every external effect gated
        for kind in (ActionKind.DB_WRITE, ActionKind.GIT_PUSH, ActionKind.CODE_WRITE,
                     ActionKind.ISSUE_EDIT, ActionKind.ISSUE_CREATE, ActionKind.CUSTOMER_REPLY,
                     ActionKind.DELETE):
            self.assertFalse(p.is_allowed(kind), kind)

    def test_explicit_allowlist_grants_exactly_those(self):
        p = ActionPolicy({ActionKind.CODE_READ, ActionKind.GIT_PUSH})
        self.assertTrue(p.is_allowed(ActionKind.CODE_READ))   # explicitly granted
        self.assertTrue(p.is_allowed(ActionKind.GIT_PUSH))    # explicitly granted
        self.assertFalse(p.is_allowed(ActionKind.DB_READ))    # NOT granted, even though a read

    def test_from_names_parses_request_strings(self):
        p = ActionPolicy.from_names(["code-read", "code-write", "git-push"])
        self.assertTrue(p.is_allowed(ActionKind.CODE_WRITE))
        self.assertTrue(p.is_allowed(ActionKind.GIT_PUSH))
        self.assertFalse(p.is_allowed(ActionKind.DELETE))

    def test_from_names_none_is_safe_default(self):
        self.assertEqual(ActionPolicy.from_names(None).allowed, SAFE_DEFAULT_ACTIONS)

    def test_from_names_unknown_action_raises(self):
        with self.assertRaises(ValueError):
            ActionPolicy.from_names(["read-everything"])


class StateMachineTests(unittest.TestCase):
    def test_starts_ready_for_agent(self):
        self.assertTrue(StateMachine().can_trigger_agent())

    def test_anti_recursion_blocks_self_trigger(self):
        m = StateMachine()
        m.transition(ConversationState.AWAITING_HUMAN)
        self.assertFalse(m.can_trigger_agent())

    def test_human_reply_re_arms_agent(self):
        m = StateMachine(ConversationState.AWAITING_HUMAN)
        m.human_replied()
        self.assertTrue(m.can_trigger_agent())

    def test_illegal_transition_raises(self):
        m = StateMachine(ConversationState.RESOLVED)
        with self.assertRaises(ValueError):
            m.transition(ConversationState.AWAITING_AGENT)


if __name__ == "__main__":
    unittest.main()
