"""Tests for the thin FastAPI shell. Skipped cleanly when FastAPI is not installed
(the rest of the suite stays install-free). Uses the no-dep `demo` backend."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parent / "fixtures" / "host"

try:
    from fastapi.testclient import TestClient  # noqa: E402

    from cortex_runtime.api import create_app  # noqa: E402
    from cortex_runtime.app import WorkspaceConfig  # noqa: E402
    from cortex_runtime.runtime import build_runtime  # noqa: E402
    from cortex_runtime.state_store import InMemoryStateStore  # noqa: E402
    HAVE_FASTAPI = True
except Exception:
    HAVE_FASTAPI = False


@unittest.skipUnless(HAVE_FASTAPI, "fastapi (+ test client deps) not installed")
class ApiTests(unittest.TestCase):
    def setUp(self):
        runtime = build_runtime(
            {"host": WorkspaceConfig(root=ROOT, theme="h2g2")},
            store=InMemoryStateStore(),
            manifest={"/pr-review": {"role": "lead-backend", "workflow": "code-review"}},
            model_backend="demo",
        )
        self.client = TestClient(create_app(runtime))

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("host", body["workspaces"])
        self.assertIn("/pr-review", body["endpoints"])
        self.assertEqual(body["backend"], "demo")

    def test_resolve_returns_bundle(self):
        r = self.client.post("/resolve", json={"workspace": "host", "role": "lead-backend",
                                               "service": "svc-a", "workflow": "code-review"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("BASE-ROLE", r.json()["system_prompt"])
        self.assertEqual(r.json()["capabilities"], ["languages/php.md"])

    def test_run_executes(self):
        r = self.client.post("/run", json={"workspace": "host", "role": "support-engineer",
                                           "subject": "ACME-7", "input": {"issue": "ACME-7"}})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["skipped"])
        self.assertEqual(body["state"], "resolved")
        self.assertEqual(len(body["comments"]), 1)

    def test_run_requires_role(self):
        r = self.client.post("/run", json={"workspace": "host"})
        self.assertEqual(r.status_code, 422)

    def test_unknown_workspace_404(self):
        r = self.client.post("/run", json={"workspace": "ghost", "role": "lead-backend"})
        self.assertEqual(r.status_code, 404)

    def test_unknown_autonomy_action_422(self):
        r = self.client.post("/run", json={"workspace": "host", "role": "lead-backend",
                                           "autonomy": ["nuke-everything"]})
        self.assertEqual(r.status_code, 422)

    def test_domain_alias_executes(self):
        r = self.client.post("/pr-review", json={"workspace": "host", "service": "svc-a",
                                                 "subject": "ACME-2"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["skipped"])


if __name__ == "__main__":
    unittest.main()
