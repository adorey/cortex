"""Async execution wiring (ADR-005 §3.1) — POST /run → 202 + run_id, a worker executes it,
GET /runs/{id} polls the lifecycle; ?wait=true and no-queue stay synchronous. Demo backend."""

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
    from cortex_runtime.runtime import build_runtime  # noqa: E402
    from cortex_runtime.state_store import InMemoryStateStore  # noqa: E402
    HAVE_FASTAPI = True
except Exception:
    HAVE_FASTAPI = False

MANIFEST = {"/pr-review": {"role": "lead-backend", "workflow": "code-review"}}


@unittest.skipUnless(HAVE_FASTAPI, "fastapi (+ test client deps) not installed")
class AsyncApiTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStateStore()
        self.runtime = build_runtime({"host": WorkspaceConfig(root=ROOT, theme="h2g2")},
                                     store=self.store, manifest=MANIFEST, model_backend="demo")
        self.queue = self.runtime.build_queue()
        self.app = create_app(self.runtime, queue=self.queue)

    def _poll(self, client, run_id, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = client.get(f"/runs/{run_id}")
            if r.status_code == 200 and r.json().get("lifecycle") in ("done", "failed", "skipped"):
                return r.json()
            time.sleep(0.02)
        raise AssertionError(f"run {run_id} did not finish in {timeout}s")

    def test_run_returns_202_then_completes(self):
        with TestClient(self.app) as client:
            r = client.post("/run", json={"workspace": "host", "role": "support-engineer",
                                          "subject": "A1", "input": {}})
            self.assertEqual(r.status_code, 202)
            body = r.json()
            self.assertEqual(body["status"], "queued")
            self.assertEqual(body["subject"], "A1")
            rec = self._poll(client, body["run_id"])
            self.assertEqual(rec["lifecycle"], "done")
            self.assertEqual(rec["state"], "resolved")

    def test_queued_record_is_visible_before_completion(self):
        with TestClient(self.app) as client:
            run_id = client.post("/run", json={"workspace": "host", "role": "support-engineer",
                                               "subject": "A2"}).json()["run_id"]
            # the record exists immediately (queued/running/done — never 404)
            self.assertEqual(client.get(f"/runs/{run_id}").status_code, 200)
            self.assertEqual(self._poll(client, run_id)["lifecycle"], "done")

    def test_wait_true_is_synchronous(self):
        with TestClient(self.app) as client:
            r = client.post("/run?wait=true", json={"workspace": "host", "role": "support-engineer",
                                                    "subject": "A3", "input": {}})
            self.assertEqual(r.status_code, 200)          # full outcome inline, not 202
            self.assertEqual(r.json()["state"], "resolved")

    def test_no_queue_is_synchronous(self):
        app = create_app(self.runtime)                    # no queue at all
        with TestClient(app) as client:
            r = client.post("/run", json={"workspace": "host", "role": "support-engineer",
                                          "subject": "A4"})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["state"], "resolved")

    def test_validation_fails_fast_even_async(self):
        with TestClient(self.app) as client:
            # unknown workspace → 404 synchronously, before enqueueing (no run record created)
            self.assertEqual(client.post("/run", json={"workspace": "ghost", "role": "x"}).status_code, 404)
            # missing role → 422 synchronously
            self.assertEqual(client.post("/run", json={"workspace": "host"}).status_code, 422)

    def test_alias_endpoint_is_async(self):
        with TestClient(self.app) as client:
            r = client.post("/pr-review", json={"workspace": "host", "service": "svc-a", "subject": "A5"})
            self.assertEqual(r.status_code, 202)
            self.assertEqual(self._poll(client, r.json()["run_id"])["lifecycle"], "done")

    def test_ready_probe_ok(self):
        with TestClient(self.app) as client:
            r = client.get("/ready")
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertTrue(body["ready"] and body["db"] and body["worker"])
            self.assertEqual(body["queue"]["workers"], 4)   # the worker pool is up

    def test_ready_503_when_worker_down(self):
        # before the lifespan starts the queue, the worker pool is not alive → not ready
        client = TestClient(self.app)   # NOT entered as a context manager → no startup
        r = client.get("/ready")
        self.assertEqual(r.status_code, 503)
        self.assertFalse(r.json()["ready"])
        self.assertFalse(r.json()["worker"])

    def test_health_is_liveness_only(self):
        client = TestClient(self.app)   # health needs no started worker
        self.assertEqual(client.get("/health").status_code, 200)

    def test_async_anti_recursion_records_skip(self):
        with TestClient(self.app) as client:
            first = client.post("/run", json={"workspace": "host", "role": "support-engineer",
                                              "subject": "RT", "input": {}, "handoff": True})
            done = self._poll(client, first.json()["run_id"])
            self.assertEqual((done["lifecycle"], done["state"]), ("done", "awaiting-human"))
            # a second trigger on the same subject is anti-recursion-skipped by the worker
            second = client.post("/run", json={"workspace": "host", "role": "support-engineer",
                                               "subject": "RT", "input": {}, "handoff": True})
            skipped = self._poll(client, second.json()["run_id"])
            self.assertEqual(skipped["lifecycle"], "skipped")
            self.assertIn("anti-recursion", skipped["error"])


if __name__ == "__main__":
    unittest.main()
