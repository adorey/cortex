"""Tests for the framework-agnostic app logic (alias merge + workspace registry)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.app import WorkspaceConfig, build_run_request, resolve_endpoint  # noqa: E402

ROOT = Path(__file__).resolve().parent / "fixtures" / "host"
REGISTRY = {"host": WorkspaceConfig(root=ROOT, theme="h2g2")}


class BuildRunRequestTests(unittest.TestCase):
    def test_alias_supplies_defaults(self):
        req = build_run_request(
            {"workspace": "host", "service": "svc-a"},
            alias={"role": "lead-backend", "workflow": "code-review"},
        )
        self.assertEqual((req.role, req.workflow, req.service), ("lead-backend", "code-review", "svc-a"))

    def test_body_overrides_alias(self):
        req = build_run_request(
            {"workspace": "host", "role": "architect"},
            alias={"role": "lead-backend"},
        )
        self.assertEqual(req.role, "architect")

    def test_none_values_do_not_clobber_alias(self):
        req = build_run_request(
            {"workspace": "host", "role": "lead-backend", "workflow": None},
            alias={"workflow": "code-review"},
        )
        self.assertEqual(req.workflow, "code-review")


class ResolveEndpointTests(unittest.TestCase):
    def test_generic_run(self):
        resolved = resolve_endpoint(
            REGISTRY,
            {"workspace": "host", "role": "lead-backend", "service": "svc-a", "workflow": "code-review"},
        )
        self.assertEqual(resolved.capabilities, ["languages/php.md"])
        self.assertIn("BASE-ROLE", resolved.system_prompt)
        self.assertIn("WORKSPACE-WORKFLOW", resolved.workflow)

    def test_domain_alias(self):
        resolved = resolve_endpoint(
            REGISTRY,
            {"workspace": "host", "service": "svc-a", "input": {"issue": "ACME-1"}},
            alias={"role": "lead-backend", "workflow": "code-review"},
        )
        self.assertIn("SERVICE-RULE", resolved.system_prompt)
        self.assertIsNotNone(resolved.workflow)

    def test_unknown_workspace_raises(self):
        with self.assertRaises(KeyError):
            resolve_endpoint(REGISTRY, {"workspace": "ghost", "role": "lead-backend"})


if __name__ == "__main__":
    unittest.main()
