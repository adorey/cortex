"""The webhook trigger (ADR-004 §3.1) — POST /webhook/{source}: HMAC over the raw body, an
agnostic dotted-path subject extraction, then the same dispatch as /run. Demo backend."""

import json
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
    from cortex_runtime.auth import hmac_signature  # noqa: E402
    from cortex_runtime.auth_policy import AuthPolicy  # noqa: E402
    from cortex_runtime.ephemeral import InMemoryEphemeralStore  # noqa: E402
    from cortex_runtime.runtime import build_runtime  # noqa: E402
    from cortex_runtime.security_gate import SecurityGate  # noqa: E402
    from cortex_runtime.state_store import InMemoryStateStore  # noqa: E402
    HAVE_FASTAPI = True
except Exception:
    HAVE_FASTAPI = False

SECRET = "whsec_host"
WEBHOOKS = {"jira": {"tenant": "host", "role": "support-engineer", "subject_path": "issue.key"}}


@unittest.skipUnless(HAVE_FASTAPI, "fastapi (+ test client deps) not installed")
class WebhookApiTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStateStore()
        self.store.upsert_tenant("host", enabled=True)
        self.runtime = build_runtime({"host": WorkspaceConfig(root=ROOT, theme="h2g2")},
                                     store=self.store, webhooks=WEBHOOKS, model_backend="demo")
        policy = AuthPolicy(self.store, hmac_secret_for={"host": SECRET}.get,
                            ephemeral=InMemoryEphemeralStore())
        self.gate = SecurityGate(self.store, policy, ephemeral=policy._ephemeral)
        self.queue = self.runtime.build_queue()
        self.app = create_app(self.runtime, gate=self.gate, queue=self.queue)

    def _signed(self, body: str, *, secret=SECRET, ts=None, delivery="d1"):
        ts = ts if ts is not None else str(int(time.time()))
        return {"X-Cortex-Timestamp": ts, "X-Cortex-Signature": hmac_signature(secret, ts, body),
                "X-Delivery-Id": delivery}

    def _poll(self, run_id, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            rec = self.store.get_run(run_id)
            if rec is not None and rec.lifecycle in ("done", "failed", "skipped"):
                return rec
            time.sleep(0.02)
        raise AssertionError(f"run {run_id} did not finish")

    def test_signed_webhook_runs_with_extracted_subject(self):
        body = json.dumps({"webhookEvent": "jira:issue_updated", "issue": {"key": "ACME-1"}})
        with TestClient(self.app) as client:
            r = client.post("/webhook/jira", content=body, headers=self._signed(body))
            self.assertEqual(r.status_code, 202)
            run_id = r.json()["run_id"]
            rec = self._poll(run_id)
            self.assertEqual(rec.lifecycle, "done")
            self.assertEqual(rec.subject, "ACME-1")           # subject_path "issue.key" → "ACME-1"
            self.assertEqual(rec.role, "support-engineer")

    def test_bad_signature_401(self):
        body = json.dumps({"issue": {"key": "ACME-2"}})
        with TestClient(self.app) as client:
            r = client.post("/webhook/jira", content=body,
                            headers=self._signed(body, secret="wrong-secret"))
            self.assertEqual(r.status_code, 401)
            self.assertEqual(len(self.store.list_runs("host")), 0)   # nothing ran

    def test_stale_timestamp_401(self):
        body = json.dumps({"issue": {"key": "ACME-3"}})
        old = str(int(time.time()) - 9999)
        with TestClient(self.app) as client:
            r = client.post("/webhook/jira", content=body, headers=self._signed(body, ts=old))
            self.assertEqual(r.status_code, 401)

    def test_unknown_source_404(self):
        body = json.dumps({"issue": {"key": "X"}})
        with TestClient(self.app) as client:
            r = client.post("/webhook/ghosthook", content=body, headers=self._signed(body))
            self.assertEqual(r.status_code, 404)

    def test_subject_path_unresolved_422(self):
        body = json.dumps({"no_issue_here": True})   # "issue.key" won't resolve
        with TestClient(self.app) as client:
            r = client.post("/webhook/jira", content=body, headers=self._signed(body))
            self.assertEqual(r.status_code, 422)

    def test_resigned_retry_is_deduped_by_delivery_id(self):
        # A provider retry re-signs (fresh timestamp → new signature) but keeps the SAME delivery
        # id → passes the anti-replay nonce, then idempotency dedups it → no second run.
        body = json.dumps({"issue": {"key": "ACME-DUP"}})
        ts1 = str(int(time.time()))
        ts2 = str(int(ts1) + 1)
        with TestClient(self.app) as client:
            first = client.post("/webhook/jira", content=body, headers=self._signed(body, ts=ts1, delivery="retry-1"))
            self.assertEqual(first.json()["status"], "queued")
            second = client.post("/webhook/jira", content=body, headers=self._signed(body, ts=ts2, delivery="retry-1"))
            self.assertEqual(second.json()["status"], "duplicate")
            self.assertEqual(first.json()["run_id"], second.json()["run_id"])
            self._poll(first.json()["run_id"])
            self.assertEqual(len(self.store.list_runs("host")), 1)        # exactly one run

    def test_exact_replay_is_rejected_by_nonce(self):
        # The SAME signed bytes re-sent (identical signature) is a replay → 401, before any run.
        body = json.dumps({"issue": {"key": "ACME-RP"}})
        h = self._signed(body, delivery="retry-1")
        with TestClient(self.app) as client:
            self.assertEqual(client.post("/webhook/jira", content=body, headers=h).json()["status"], "queued")
            replay = client.post("/webhook/jira", content=body, headers=h)
            self.assertEqual(replay.status_code, 401)
            self.assertEqual(replay.json()["detail"], "replay")

    def test_open_mode_without_gate(self):
        app = create_app(self.runtime)   # no gate, no queue → open + sync
        body = json.dumps({"issue": {"key": "ACME-OPEN"}})
        with TestClient(app) as client:
            r = client.post("/webhook/jira", content=body)   # no signature needed when open
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["state"], "resolved")
            self.assertEqual(r.json()["subject"], "ACME-OPEN")


if __name__ == "__main__":
    unittest.main()
