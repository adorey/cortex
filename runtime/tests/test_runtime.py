"""Tests for the executable slice — Runtime resolve + run end-to-end (Phase 5).

Uses the no-dep `demo` backend against the fixture working tree, so the whole wire
(resolve → tools → loop → durable state + audit) runs with zero install and no key.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.app import WorkspaceConfig  # noqa: E402
from cortex_runtime.runtime import build_runtime, make_model_client  # noqa: E402
from cortex_runtime.local_tools import local_tool_registry  # noqa: E402
from cortex_runtime.state_store import InMemoryStateStore  # noqa: E402

ROOT = Path(__file__).resolve().parent / "fixtures" / "host"


class MakeModelClientTests(unittest.TestCase):
    def test_demo_backend_needs_nothing(self):
        reg, _ = local_tool_registry(ROOT)
        self.assertIsNotNone(make_model_client("demo", reg))

    def test_unknown_backend_raises(self):
        reg, _ = local_tool_registry(ROOT)
        with self.assertRaises(ValueError):
            make_model_client("gpt-9000", reg)

    def test_anthropic_api_requires_secrets(self):
        reg, _ = local_tool_registry(ROOT)
        with self.assertRaises(ValueError):
            make_model_client("anthropic-api", reg, secrets=None)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStateStore()
        self.rt = build_runtime(
            {"host": WorkspaceConfig(root=ROOT, theme="h2g2")},
            store=self.store, model_backend="demo",
        )

    def test_resolve_returns_bundle(self):
        bundle = self.rt.resolve({"workspace": "host", "role": "lead-backend",
                                  "service": "svc-a", "workflow": "code-review"})
        self.assertIn("BASE-ROLE", bundle.system_prompt)
        self.assertEqual(bundle.capabilities, ["languages/php.md"])

    def test_run_executes_loop_end_to_end(self):
        out = self.rt.run({"workspace": "host", "role": "support-engineer", "subject": "ACME-7",
                           "input": {"issue": "ACME-7"}})
        self.assertFalse(out["skipped"])
        self.assertEqual(out["state"], "resolved")
        # the demo agent listed files (a read) and posted an internal comment
        kinds = [k for _, k in out["actions_taken"]]
        self.assertIn("code-read", kinds)
        self.assertIn("internal-comment", kinds)
        self.assertEqual(len(out["comments"]), 1)
        # state + audit were persisted
        self.assertEqual(len(self.store.list_runs("host")), 1)
        self.assertTrue(self.store.audit_trail(subject="ACME-7"))

    def test_subject_falls_back_to_issue_then_default(self):
        out = self.rt.run({"workspace": "host", "role": "support-engineer", "input": {"issue": "ACME-9"}})
        self.assertEqual(out["subject"], "ACME-9")

    def test_anti_recursion_skips_second_run(self):
        # gated autonomy: nothing beyond default; force AWAITING_HUMAN via a gated tool is not
        # available with demo tools, so instead drive two runs and assert the resolved one stays put.
        self.rt.run({"workspace": "host", "role": "support-engineer", "subject": "ACME-1",
                     "input": {}})
        # first run resolved; a re-trigger on a RESOLVED subject is also not awaiting-agent → skipped
        second = self.rt.run({"workspace": "host", "role": "support-engineer", "subject": "ACME-1",
                              "input": {}})
        self.assertTrue(second["skipped"])

    def test_handoff_round_trip(self):
        # the support flow: run → AWAITING_HUMAN → re-trigger skipped → human reply → run again
        from cortex_runtime.session import mark_human_reply
        first = self.rt.run({"workspace": "host", "role": "support-engineer", "subject": "RT-1",
                             "input": {}, "handoff": True})
        self.assertEqual(first["state"], "awaiting-human")        # hand-off, not resolved
        again = self.rt.run({"workspace": "host", "role": "support-engineer", "subject": "RT-1",
                             "input": {}, "handoff": True})
        self.assertTrue(again["skipped"])                         # anti-recursion holds
        mark_human_reply(self.store, "host", "RT-1")              # a human acted
        third = self.rt.run({"workspace": "host", "role": "support-engineer", "subject": "RT-1",
                             "input": {}, "handoff": True})
        self.assertEqual(third["state"], "awaiting-human")        # agent runs again

    def test_force_bypasses_anti_recursion(self):
        self.rt.run({"workspace": "host", "role": "support-engineer", "subject": "F-1", "input": {}})
        # a plain re-run on the resolved subject is skipped...
        self.assertTrue(self.rt.run({"workspace": "host", "role": "support-engineer",
                                     "subject": "F-1", "input": {}})["skipped"])
        # ...but force re-runs it anyway (testing the same ticket repeatedly)
        forced = self.rt.run({"workspace": "host", "role": "support-engineer",
                              "subject": "F-1", "input": {}, "force": True})
        self.assertFalse(forced["skipped"])
        self.assertEqual(forced["state"], "resolved")

    def test_unknown_workspace_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.rt.run({"workspace": "ghost", "role": "lead-backend"})


if __name__ == "__main__":
    unittest.main()
