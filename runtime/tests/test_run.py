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



class ProjectContextInPromptTests(unittest.TestCase):
    """#87 — the project context is the agent's context: it reaches the system prompt."""

    def test_the_project_context_closes_the_system_prompt(self):
        run = resolve_run(RunRequest(workspace="host", role="lead-backend"), ROOT, theme="h2g2")
        context = (ROOT / "project-context.md").read_text(encoding="utf-8")
        self.assertTrue(run.system_prompt.endswith("# Project context\n\n" + context), run.system_prompt[-200:])


class WorkspaceViewInPromptTests(unittest.TestCase):
    """#88 — the agent sees what the Prompt Manager reads in the editor: the overviews, the
    workspace's services, then the contexts."""

    def test_a_run_on_a_service_sees_the_whole_workspace(self):
        import shutil
        import tempfile
        root = Path(tempfile.mkdtemp(prefix="cortex-run-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        shutil.copytree(ROOT / "cortex", root / "cortex")
        files = {
            "agents/project-overview.md": "TEAM-VISION", "project-overview.md": "DEV-VISION",
            "svc-a/project-overview.md": "<!-- @alias: api -->\n# Main API\nSVC-VISION",
            "svc-b/project-overview.md": "<!-- @alias: web -->\n# Web application",
            "project-context.md": "DEV-RULES",
        }
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        prompt = resolve_run(RunRequest(workspace="host", role="lead-backend", service="svc-a"), root, theme=None).system_prompt
        marks = ["# Project overview", "## Team overview", "TEAM-VISION", "## Developer overview", "DEV-VISION",
                 "## Service overview — svc-a", "SVC-VISION", "# Workspace services", "`@api` — `svc-a/` — Main API (active)",
                 "`@web` — `svc-b/` — Web application", "# Project context", "DEV-RULES"]
        at = [prompt.index(m) for m in marks]
        self.assertEqual(at, sorted(at))


if __name__ == "__main__":
    unittest.main()
