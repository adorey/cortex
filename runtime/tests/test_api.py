"""Tests for the thin FastAPI shell. Skipped cleanly when FastAPI is not installed
(the rest of the suite must stay install-free)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parent / "fixtures" / "host"

try:
    from fastapi.testclient import TestClient  # noqa: E402

    from cortex_runtime.api import create_app  # noqa: E402
    from cortex_runtime.app import WorkspaceConfig  # noqa: E402
    HAVE_FASTAPI = True
except Exception:  # ImportError, or starlette/httpx missing
    HAVE_FASTAPI = False


@unittest.skipUnless(HAVE_FASTAPI, "fastapi (+ test client deps) not installed")
class ApiTests(unittest.TestCase):
    def setUp(self):
        registry = {"host": WorkspaceConfig(root=ROOT, theme="h2g2")}
        manifest = {"/pr-review": {"role": "lead-backend", "workflow": "code-review"}}
        self.client = TestClient(create_app(registry, manifest))

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertIn("host", r.json()["workspaces"])
        self.assertIn("/pr-review", r.json()["endpoints"])

    def test_run_resolves(self):
        r = self.client.post("/run", json={
            "workspace": "host", "role": "lead-backend", "service": "svc-a", "workflow": "code-review",
        })
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["capabilities"], ["languages/php.md"])
        self.assertIn("BASE-ROLE", body["system_prompt"])

    def test_run_requires_role(self):
        r = self.client.post("/run", json={"workspace": "host"})
        self.assertEqual(r.status_code, 422)

    def test_unknown_workspace_404(self):
        r = self.client.post("/run", json={"workspace": "ghost", "role": "lead-backend"})
        self.assertEqual(r.status_code, 404)

    def test_domain_alias_endpoint(self):
        r = self.client.post("/pr-review", json={"workspace": "host", "service": "svc-a"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.json()["workflow"])

    def test_autonomy_passes_through_payload(self):
        r = self.client.post("/run", json={
            "workspace": "host", "role": "lead-backend",
            "autonomy": ["code-read", "code-write", "git-push"],
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["allowed_actions"], ["code-read", "code-write", "git-push"])

    def test_unknown_autonomy_action_422(self):
        r = self.client.post("/run", json={
            "workspace": "host", "role": "lead-backend", "autonomy": ["nuke-everything"],
        })
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
