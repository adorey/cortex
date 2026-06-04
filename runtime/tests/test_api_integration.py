"""Integration: security (ADR-004) AND async (ADR-005) on the same app — the combined /run
path (authenticate → enqueue), which neither feature's own tests exercise together."""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parent / "fixtures" / "host"

try:
    from fastapi.testclient import TestClient  # noqa: E402

    from cortex_runtime.api import create_app  # noqa: E402
    from cortex_runtime.app import WorkspaceConfig  # noqa: E402
    from cortex_runtime.auth import hash_token  # noqa: E402
    from cortex_runtime.auth_policy import AuthPolicy  # noqa: E402
    from cortex_runtime.ephemeral import InMemoryEphemeralStore  # noqa: E402
    from cortex_runtime.runtime import build_runtime  # noqa: E402
    from cortex_runtime.security_gate import SecurityGate  # noqa: E402
    from cortex_runtime.state_store import InMemoryStateStore  # noqa: E402
    HAVE_FASTAPI = True
except Exception:
    HAVE_FASTAPI = False

TOKEN = "rt_live_host_token"


@unittest.skipUnless(HAVE_FASTAPI, "fastapi (+ test client deps) not installed")
class SecuredAsyncApiTests(unittest.TestCase):
    """create_app(runtime, gate=…, queue=…): Bearer-protected AND accept-then-process."""

    def setUp(self):
        self.store = InMemoryStateStore()
        self.store.upsert_tenant("host", enabled=True)
        self.store.add_token("host", hash_token(TOKEN), scopes=["host"])
        self.runtime = build_runtime({"host": WorkspaceConfig(root=ROOT, theme="h2g2")},
                                     store=self.store, model_backend="demo")
        policy = AuthPolicy(self.store, hmac_secret_for=lambda t: None)
        self.gate = SecurityGate(self.store, policy, ephemeral=InMemoryEphemeralStore())
        self.queue = self.runtime.build_queue()
        self.app = create_app(self.runtime, gate=self.gate, queue=self.queue)

    def _auth(self):
        return {"Authorization": f"Bearer {TOKEN}"}

    def _poll(self, client, run_id, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = client.get(f"/runs/{run_id}", headers=self._auth())
            if r.status_code == 200 and r.json().get("lifecycle") in ("done", "failed", "skipped"):
                return r.json()
            time.sleep(0.02)
        raise AssertionError(f"run {run_id} did not finish in {timeout}s")

    def test_run_rejected_before_enqueue_without_token(self):
        with TestClient(self.app) as client:
            r = client.post("/run", json={"workspace": "host", "role": "support-engineer",
                                          "subject": "I1", "input": {}})
            self.assertEqual(r.status_code, 401)          # auth runs BEFORE enqueue → no 202
            # nothing was queued
            self.assertEqual(self.queue.stats()["pending"] + self.queue.stats()["active"], 0)

    def test_authenticated_run_is_accepted_and_executes(self):
        with TestClient(self.app) as client:
            r = client.post("/run", headers=self._auth(),
                            json={"workspace": "host", "role": "support-engineer",
                                  "subject": "I2", "input": {}})
            self.assertEqual(r.status_code, 202)          # secured AND async
            rec = self._poll(client, r.json()["run_id"])
            self.assertEqual((rec["lifecycle"], rec["state"]), ("done", "resolved"))

    def test_wait_true_is_secured_and_synchronous(self):
        with TestClient(self.app) as client:
            r = client.post("/run?wait=true", headers=self._auth(),
                            json={"workspace": "host", "role": "support-engineer", "subject": "I3"})
            self.assertEqual(r.status_code, 200)          # ?wait=true → sync even with a queue
            self.assertEqual(r.json()["state"], "resolved")

    def test_rate_limit_applies_on_the_async_path(self):
        self.store.upsert_tenant("host", enabled=True, rate_limit_per_min=1)
        body = {"workspace": "host", "role": "support-engineer", "subject": "I4", "input": {}}
        with TestClient(self.app) as client:
            self.assertEqual(client.post("/run", headers=self._auth(), json=body).status_code, 202)
            r = client.post("/run", headers=self._auth(), json=body)
            self.assertEqual(r.status_code, 429)          # rate-limit shed BEFORE enqueue
            self.assertIn("Retry-After", r.headers)

    def test_monitoring_still_requires_token(self):
        with TestClient(self.app) as client:
            self.assertEqual(client.get("/runs", params={"workspace": "host"}).status_code, 401)
            self.assertEqual(client.get("/ready").status_code, 200)   # /ready stays open


if __name__ == "__main__":
    unittest.main()
