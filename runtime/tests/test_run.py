"""Tests for the /run resolution core — ADR-002 §3.2 / §8.1."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.run import RunRequest, resolve_run  # noqa: E402

ROOT = Path(__file__).resolve().parent / "fixtures" / "host"


class ResolveRunTests(unittest.TestCase):
    def test_full_bundle(self):
        req = RunRequest(
            workspace="host", role="lead-backend", service="svc-a",
            workflow="code-review", input={"issue": "ACME-42"}, model="claude-opus-4-8",
        )
        run = resolve_run(req, ROOT, theme="h2g2")

        # identity assembled: personality + role + derived capability (php), in the prompt
        for token in ("BASE-THEME", "WORKSPACE-THEME", "BASE-CHARACTER",
                      "BASE-ROLE", "WORKSPACE-RULE", "SERVICE-RULE", "BASE-CAP"):
            self.assertIn(token, run.system_prompt)
        # typescript not in the stack → not pulled in; characters.md remap never leaks
        self.assertNotIn("BASE-CAP-TS", run.system_prompt)
        self.assertNotIn("Marvin", run.system_prompt)

        # capabilities derived deterministically from project-context.md
        self.assertEqual(run.capabilities, ["languages/php.md"])

        # workflow resolved with replacement semantic (workspace overlay wins entirely)
        self.assertIsNotNone(run.workflow)
        self.assertIn("WORKSPACE-WORKFLOW", run.workflow)
        self.assertNotIn("BASE-WORKFLOW", run.workflow)

        self.assertEqual(run.model, "claude-opus-4-8")
        self.assertEqual(
            run.layers,
            [("personalities", "h2g2/theme.md"),
             ("personalities", "h2g2/Hactar.md"),
             ("roles", "engineering/lead-backend.md")],
        )

    def test_no_workflow(self):
        run = resolve_run(RunRequest(workspace="host", role="lead-backend"), ROOT, theme="h2g2")
        self.assertIsNone(run.workflow)

    def test_unknown_workflow_is_none(self):
        req = RunRequest(workspace="host", role="lead-backend", workflow="does-not-exist")
        self.assertIsNone(resolve_run(req, ROOT, theme="h2g2").workflow)

    def test_no_theme_no_personality(self):
        run = resolve_run(RunRequest(workspace="host", role="lead-backend"), ROOT, theme=None)
        self.assertIn("BASE-ROLE", run.system_prompt)
        self.assertNotIn("BASE-THEME", run.system_prompt)

    def test_autonomy_defaults_to_least_privilege(self):
        run = resolve_run(RunRequest(workspace="host", role="lead-backend"), ROOT)
        self.assertEqual(
            run.allowed_actions,
            ["code-read", "db-read", "git-read", "internal-comment", "issue-read"],
        )

    def test_autonomy_is_per_request(self):
        req = RunRequest(workspace="host", role="lead-backend",
                         autonomy=["code-read", "code-write", "git-push"])
        run = resolve_run(req, ROOT)
        self.assertEqual(run.allowed_actions, ["code-read", "code-write", "git-push"])

    def test_unknown_autonomy_action_raises(self):
        req = RunRequest(workspace="host", role="lead-backend", autonomy=["do-anything"])
        with self.assertRaises(ValueError):
            resolve_run(req, ROOT)


if __name__ == "__main__":
    unittest.main()
