"""The FastAPI security wiring (ADR-004 #6) — a gate-protected app: Bearer on direct +
monitoring routes, the full chain on /run, GET /auth-log + /budget. Mirrors test_api.py's
demo runtime; skipped cleanly without FastAPI."""

import sys
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
class SecuredApiTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStateStore()
        self.store.upsert_tenant("host", enabled=True)
        self.store.add_token("host", hash_token(TOKEN), scopes=["host"])
        runtime = build_runtime(
            {"host": WorkspaceConfig(root=ROOT, theme="h2g2")},
            store=self.store,
            manifest={"/pr-review": {"role": "lead-backend", "workflow": "code-review"}},
            model_backend="demo",
        )
        policy = AuthPolicy(self.store, hmac_secret_for=lambda t: None)
        self.gate = SecurityGate(self.store, policy, ephemeral=InMemoryEphemeralStore())
        self.client = TestClient(create_app(runtime, gate=self.gate))

    def _auth(self, token=TOKEN):
        return {"Authorization": f"Bearer {token}"}

    # — health stays open (liveness probe, no secret) —
    def test_health_is_open(self):
        self.assertEqual(self.client.get("/health").status_code, 200)

    # — direct path: /run —
    def test_run_without_token_401(self):
        r = self.client.post("/run", json={"workspace": "host", "role": "support-engineer",
                                           "subject": "S1", "input": {}})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["detail"], "unknown_token")

    def test_run_with_token_ok(self):
        r = self.client.post("/run", headers=self._auth(),
                             json={"workspace": "host", "role": "support-engineer",
                                   "subject": "S2", "input": {}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["state"], "resolved")

    def test_run_bad_token_401(self):
        r = self.client.post("/run", headers=self._auth("wrong"),
                             json={"workspace": "host", "role": "support-engineer", "subject": "S3"})
        self.assertEqual(r.status_code, 401)

    def test_run_out_of_scope_403(self):
        # token scoped to "host"; a run targeting an unregistered/other workspace → 403 (or 404)
        self.store.upsert_tenant("other", enabled=True)
        r = self.client.post("/run", headers=self._auth(),
                             json={"workspace": "other", "role": "support-engineer", "subject": "S4"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["detail"], "out_of_scope")

    # — monitoring routes require the token (for wbtb) —
    def test_monitoring_requires_token(self):
        self.assertEqual(self.client.get("/runs", params={"workspace": "host"}).status_code, 401)
        r = self.client.get("/runs", params={"workspace": "host"}, headers=self._auth())
        self.assertEqual(r.status_code, 200)

    def test_auth_log_route(self):
        self.client.post("/run", json={"workspace": "host", "role": "support-engineer", "subject": "S5"})  # 401
        self.client.post("/run", headers=self._auth(),
                         json={"workspace": "host", "role": "support-engineer", "subject": "S6"})  # ok
        r = self.client.get("/auth-log", params={"tenant": "host"}, headers=self._auth())
        self.assertEqual(r.status_code, 200)
        reasons = {e["reason"] for e in r.json()["auth_log"]}
        self.assertIn("ok", reasons)            # the successful /run and this /auth-log read

    def test_auth_log_rejected_filter_shows_the_401(self):
        self.client.post("/run", json={"workspace": "host", "role": "support-engineer", "subject": "S7"})
        r = self.client.get("/auth-log", params={"result": "rejected"}, headers=self._auth())
        reasons = [e["reason"] for e in r.json()["auth_log"]]
        self.assertIn("unknown_token", reasons)

    def test_budget_route(self):
        self.store.upsert_tenant("host", enabled=True, budget_daily_usd=10.0)
        r = self.client.get("/budget", params={"workspace": "host"}, headers=self._auth())
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["allowed"])
        self.assertEqual(body["daily"]["ceiling_usd"], 10.0)
        self.assertEqual(body["daily"]["remaining_usd"], 10.0)

    # — rate-limit surfaces as 429 with Retry-After —
    def test_rate_limit_429(self):
        self.store.upsert_tenant("host", enabled=True, rate_limit_per_min=1)
        body = {"workspace": "host", "role": "support-engineer", "subject": "RL", "input": {}}
        self.assertEqual(self.client.post("/run", headers=self._auth(), json=body).status_code, 200)
        r = self.client.post("/run", headers=self._auth(), json=body)
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)

    # — idempotency: a repeated delivery returns the cached outcome —
    def test_idempotency_replays_outcome(self):
        body = {"workspace": "host", "role": "support-engineer", "subject": "IDEM", "input": {}}
        h = {**self._auth(), "Idempotency-Key": "delivery-42"}
        first = self.client.post("/run", headers=h, json=body)
        self.assertEqual(first.status_code, 200)
        second = self.client.post("/run", headers=h, json=body)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["run_id"], second.json()["run_id"])   # same run, not re-executed


if __name__ == "__main__":
    unittest.main()
