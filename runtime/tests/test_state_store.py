"""Tests for the StateStore backends — ADR-003. Run against both InMemory and SQLite."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cortex_runtime.safety import ConversationState  # noqa: E402
from cortex_runtime.state_store import InMemoryStateStore, SqliteStateStore  # noqa: E402


class _StateStoreContract:
    """Shared contract exercised against every backend."""

    def make_store(self):
        raise NotImplementedError

    def setUp(self):
        self.store = self.make_store()

    def test_conversation_state_roundtrip(self):
        self.assertIsNone(self.store.get_conversation_state("acme", "ACME-1"))
        self.store.set_conversation_state("acme", "ACME-1", ConversationState.AWAITING_HUMAN)
        self.assertEqual(self.store.get_conversation_state("acme", "ACME-1"),
                         ConversationState.AWAITING_HUMAN)

    def test_conversation_state_is_per_subject(self):
        self.store.set_conversation_state("acme", "ACME-1", ConversationState.RESOLVED)
        self.assertIsNone(self.store.get_conversation_state("acme", "ACME-2"))

    def test_run_lifecycle_and_history(self):
        rid = self.store.start_run("acme", "lead-backend", "ACME-1", model="claude-opus-4-8")
        self.assertTrue(rid)
        self.store.finish_run(rid, ConversationState.RESOLVED, iterations=4)
        runs = self.store.list_runs("acme")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].state, "resolved")
        self.assertEqual(runs[0].iterations, 4)
        self.assertEqual(runs[0].role, "lead-backend")

    def test_get_run_returns_record_or_none(self):
        rid = self.store.start_run("acme", "lead-backend", "ACME-1", model="m")
        self.assertEqual(self.store.get_run(rid).subject, "ACME-1")
        self.assertIsNone(self.store.get_run("does-not-exist"))

    def test_list_runs_is_scoped_and_recent_first(self):
        r1 = self.store.start_run("acme", "r", "S1")
        r2 = self.store.start_run("acme", "r", "S2")
        self.store.start_run("other", "r", "S3")
        runs = self.store.list_runs("acme")
        self.assertEqual([x.run_id for x in runs], [r2, r1])  # recent first, other workspace excluded

    def test_fail_run_records_error(self):
        rid = self.store.start_run("acme", "r", "ACME-1")
        self.store.fail_run(rid, "RuntimeError: bad path")
        rec = self.store.list_runs("acme")[0]
        self.assertEqual(rec.state, "failed")
        self.assertEqual(rec.error, "RuntimeError: bad path")

    def test_finish_run_stores_usage(self):
        import json
        rid = self.store.start_run("acme", "r", "ACME-1")
        self.store.finish_run(rid, ConversationState.RESOLVED, 2, usage={
            "total_cost_usd": 0.012, "input_tokens": 100, "output_tokens": 40, "num_turns": 3,
            "duration_ms": 36483, "ttft_ms": 4026, "cache_read_input_tokens": 999})
        rec = self.store.list_runs("acme")[0]
        self.assertEqual(rec.cost_usd, 0.012)
        self.assertEqual((rec.tokens_in, rec.tokens_out, rec.num_turns), (100, 40, 3))
        self.assertEqual((rec.duration_ms, rec.ttft_ms), (36483, 4026))
        # the full blob is preserved in metrics_json (nothing lost — e.g. cache tokens)
        self.assertEqual(json.loads(rec.metrics_json)["cache_read_input_tokens"], 999)

    def test_audit_append_and_filter(self):
        rid = self.store.start_run("acme", "r", "ACME-9")
        self.store.record_action(rid, "read_db", "db-read", gated=False, at="t1")
        self.store.record_action(rid, "open_ticket", "issue-create", gated=True, at="t2")
        trail = self.store.audit_trail(workspace="acme", subject="ACME-9")
        self.assertEqual([(e.tool, e.gated) for e in trail],
                         [("read_db", False), ("open_ticket", True)])
        self.assertEqual(self.store.audit_trail(subject="NOPE"), [])

    # — ADR-004 §3.7: tenants / api_tokens / auth_log —

    def test_tenant_upsert_and_get(self):
        self.assertIsNone(self.store.get_tenant("bluspark"))
        self.store.upsert_tenant("bluspark", budget_daily_usd=5.0, rate_limit_per_min=30)
        t = self.store.get_tenant("bluspark")
        self.assertEqual((t.tenant, t.enabled, t.budget_daily_usd, t.rate_limit_per_min),
                         ("bluspark", True, 5.0, 30))
        self.store.upsert_tenant("bluspark", enabled=False, budget_daily_usd=10.0)  # overwrite
        t = self.store.get_tenant("bluspark")
        self.assertEqual((t.enabled, t.budget_daily_usd), (False, 10.0))
        self.assertEqual([x.tenant for x in self.store.list_tenants()], ["bluspark"])

    def test_token_add_lookup_by_hash_and_scopes(self):
        tid = self.store.add_token("bluspark", "hash_abc", scopes=["bluspark", "wbtb"],
                                   label="wbtb-dashboard")
        self.assertTrue(tid)
        rec = self.store.get_token_by_hash("hash_abc")
        self.assertEqual((rec.tenant, rec.token_hash, rec.revoked), ("bluspark", "hash_abc", False))
        self.assertEqual(rec.scopes, ["bluspark", "wbtb"])
        self.assertEqual(rec.label, "wbtb-dashboard")
        self.assertIsNone(self.store.get_token_by_hash("nope"))

    def test_token_revocation(self):
        tid = self.store.add_token("bluspark", "hash_rev")
        self.store.revoke_token(tid)
        self.assertTrue(self.store.get_token_by_hash("hash_rev").revoked)
        self.assertEqual([t.token_id for t in self.store.list_tokens("bluspark")], [tid])

    def test_auth_log_records_and_filters_recent_first(self):
        self.store.record_auth(at="t1", route="/run", method="bearer", result="accepted",
                               reason="ok", tenant="bluspark", source_ip="10.0.0.1", request_id="r1")
        self.store.record_auth(at="t2", route="/run", method="bearer", result="rejected",
                               reason="rate_limited", tenant="bluspark", source_ip="10.0.0.2")
        self.store.record_auth(at="t3", route="/webhook", method="hmac", result="rejected",
                               reason="invalid_signature")  # unidentified caller → tenant None
        recent = self.store.auth_log(limit=10)
        self.assertEqual([e.reason for e in recent], ["invalid_signature", "rate_limited", "ok"])
        self.assertEqual([e.result for e in self.store.auth_log(result="rejected")],
                         ["rejected", "rejected"])
        self.assertEqual([e.reason for e in self.store.auth_log(tenant="bluspark")],
                         ["rate_limited", "ok"])


class InMemoryStateStoreTests(_StateStoreContract, unittest.TestCase):
    def make_store(self):
        return InMemoryStateStore()


@unittest.skipUnless(os.environ.get("CORTEX_TEST_DATABASE_URL"),
                     "set CORTEX_TEST_DATABASE_URL to run the Postgres contract")
class PostgresStateStoreTests(_StateStoreContract, unittest.TestCase):
    def make_store(self):
        try:
            from cortex_runtime.state_store import PostgresStateStore
            store = PostgresStateStore(os.environ["CORTEX_TEST_DATABASE_URL"])
        except ImportError as exc:
            self.skipTest(f"psycopg not installed: {exc}")
        with store._pool.connection() as conn:        # clean slate for contract isolation
            conn.execute("TRUNCATE conversation_state, runs, audit, tenants, api_tokens, auth_log")
        return store


class SqliteStateStoreTests(_StateStoreContract, unittest.TestCase):
    def make_store(self):
        return SqliteStateStore(":memory:")

    def test_persists_across_connections_on_disk(self):
        import tempfile
        db = Path(tempfile.mkdtemp()) / "state.db"
        s1 = SqliteStateStore(str(db))
        s1.set_conversation_state("acme", "ACME-1", ConversationState.AWAITING_HUMAN)
        s1.close()
        s2 = SqliteStateStore(str(db))  # fresh connection, same file
        self.assertEqual(s2.get_conversation_state("acme", "ACME-1"),
                         ConversationState.AWAITING_HUMAN)
        s2.close()


if __name__ == "__main__":
    unittest.main()
