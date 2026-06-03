"""Operational state persistence — the StateStore boundary (ADR-003).

Holds ONLY operational state (what the agent produces/lives at runtime): conversation
state for anti-recursion across invocations, the audit log (ADR-002 §3.6), and run
history. It NEVER holds spec — that stays in git (the ADR-003 firewall).

Keyed by ``subject``: the host's agnostic correlation id (a support issue key, a dashboard
correlation id, a scheduled-run key). The engine never knows it is dealing with a "ticket".

Backends are swappable behind ``StateStore`` (the SecretProvider discipline):
  • ``InMemoryStateStore`` — tests / ephemeral
  • ``SqliteStateStore``   — local dev (file or ``:memory:``); Postgres is a later backend
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol

from .safety import ConversationState


@dataclass
class RunRecord:
    run_id: str
    workspace: str
    role: str
    subject: str
    model: Optional[str]
    state: Optional[str]        # final ConversationState value, or "failed"; None while running
    iterations: Optional[int]
    error: Optional[str] = None
    cost_usd: Optional[float] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    num_turns: Optional[int] = None
    duration_ms: Optional[int] = None
    ttft_ms: Optional[int] = None
    metrics_json: Optional[str] = None   # full usage blob (cache tokens, per-model breakdown…)
    started_at: Optional[int] = None     # unix seconds at start_run — windows the budget cap (ADR-004 §3.5)


@dataclass
class AuditEntry:
    run_id: str
    tool: str
    kind: str
    gated: bool
    at: str


# ── API security operational state (ADR-004 §3.7) ────────────────────────────────────────
# These three tables are the security perimeter's state. They hold ONLY operational config
# and the connection log — never raw secrets: HMAC secrets stay in the SecretProvider, and
# Bearer tokens are stored as a hash (``token_hash``), never the raw value. The *spec* a
# tenant points at remains in git (the ADR-003 firewall is untouched).

@dataclass
class TenantRecord:
    """Per-tenant operational config (keyed by the agnostic ``tenant`` = workspace name).
    Addable/tunable without a redeploy; the budget ceilings feed the cap (§3.5)."""
    tenant: str
    enabled: bool = True
    budget_daily_usd: Optional[float] = None
    budget_monthly_usd: Optional[float] = None
    rate_limit_per_min: Optional[int] = None


@dataclass
class TokenRecord:
    """A Bearer token at rest: its **hash**, owning tenant, and authorization scope.
    ``scopes`` = the workspaces the token may invoke (empty ⇒ its own tenant only)."""
    token_id: str
    tenant: str
    token_hash: str
    scopes: List[str]
    revoked: bool = False
    label: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class AuthLogEntry:
    """One inbound auth attempt — accepted or rejected — with the verdict and its reason.
    The perimeter log (who tried / verdict / why), distinct from the agent ``audit`` log."""
    at: str
    route: str
    method: str            # "hmac" | "bearer"
    result: str            # "accepted" | "rejected"
    reason: str            # an AuthReason value
    tenant: Optional[str] = None
    source_ip: Optional[str] = None
    request_id: Optional[str] = None


def _dump_scopes(scopes: Optional[Iterable[str]]) -> str:
    return json.dumps(list(scopes or []))


def _load_scopes(raw: Optional[str]) -> List[str]:
    return list(json.loads(raw)) if raw else []


def _token_from_row(row) -> TokenRecord:
    return TokenRecord(
        token_id=row["token_id"], tenant=row["tenant"], token_hash=row["token_hash"],
        scopes=_load_scopes(row["scopes"]), revoked=bool(row["revoked"]),
        label=row["label"], expires_at=row["expires_at"], created_at=row["created_at"],
    )


def _tenant_from_row(row) -> TenantRecord:
    return TenantRecord(
        tenant=row["tenant"], enabled=bool(row["enabled"]),
        budget_daily_usd=row["budget_daily_usd"], budget_monthly_usd=row["budget_monthly_usd"],
        rate_limit_per_min=row["rate_limit_per_min"],
    )


def _authlog_from_row(row) -> AuthLogEntry:
    return AuthLogEntry(
        at=row["at"], route=row["route"], method=row["method"], result=row["result"],
        reason=row["reason"], tenant=row["tenant"], source_ip=row["source_ip"],
        request_id=row["request_id"],
    )


_TOKEN_COLUMNS = "token_id, tenant, token_hash, scopes, revoked, label, expires_at, created_at"
_TENANT_COLUMNS = "tenant, enabled, budget_daily_usd, budget_monthly_usd, rate_limit_per_min"
_AUTHLOG_COLUMNS = "at, route, method, result, reason, tenant, source_ip, request_id"


def _usage_fields(usage: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Normalise a model client's ``last_usage`` dict to the run columns. The promoted columns
    are the commonly-queried ones; ``metrics_json`` keeps the FULL blob so nothing is lost."""
    usage = usage or {}
    return {
        "cost_usd": usage.get("total_cost_usd"),
        "tokens_in": usage.get("input_tokens"),
        "tokens_out": usage.get("output_tokens"),
        "num_turns": usage.get("num_turns"),
        "duration_ms": usage.get("duration_ms"),
        "ttft_ms": usage.get("ttft_ms"),
        "metrics_json": json.dumps(usage) if usage else None,
    }


class StateStore(Protocol):
    # — conversation state (anti-recursion across invocations) —
    def get_conversation_state(self, workspace: str, subject: str) -> Optional[ConversationState]: ...
    def set_conversation_state(self, workspace: str, subject: str, state: ConversationState) -> None: ...

    # — run lifecycle + history —
    def start_run(self, workspace: str, role: str, subject: str, model: Optional[str] = None,
                  started_at: Optional[int] = None) -> str: ...
    def finish_run(self, run_id: str, state: ConversationState, iterations: int,
                   usage: Optional[Mapping[str, Any]] = None) -> None: ...
    def fail_run(self, run_id: str, error: str) -> None: ...
    def get_run(self, run_id: str) -> Optional[RunRecord]: ...
    def list_runs(self, workspace: str, *, limit: int = 50) -> List[RunRecord]: ...
    def spent_since(self, workspace: str, since_epoch: int) -> float: ...   # Σ cost_usd (ADR-004 §3.5)

    # — audit log (append-only) —
    def record_action(self, run_id: str, tool: str, kind: str, gated: bool, at: str) -> None: ...
    def audit_trail(self, *, workspace: Optional[str] = None, subject: Optional[str] = None) -> List[AuditEntry]: ...

    # — tenant registry (ADR-004 §3.7) —
    def upsert_tenant(self, tenant: str, *, enabled: bool = True,
                      budget_daily_usd: Optional[float] = None,
                      budget_monthly_usd: Optional[float] = None,
                      rate_limit_per_min: Optional[int] = None) -> None: ...
    def get_tenant(self, tenant: str) -> Optional[TenantRecord]: ...
    def list_tenants(self) -> List[TenantRecord]: ...

    # — Bearer tokens (stored hashed; ADR-004 §3.2/§3.7) —
    def add_token(self, tenant: str, token_hash: str, *, scopes: Iterable[str] = (),
                  label: Optional[str] = None, expires_at: Optional[str] = None,
                  created_at: Optional[str] = None) -> str: ...
    def get_token_by_hash(self, token_hash: str) -> Optional[TokenRecord]: ...
    def revoke_token(self, token_id: str) -> None: ...
    def list_tokens(self, tenant: str) -> List[TokenRecord]: ...

    # — connection log (perimeter; ADR-004 §3.7) —
    def record_auth(self, *, at: str, route: str, method: str, result: str, reason: str,
                    tenant: Optional[str] = None, source_ip: Optional[str] = None,
                    request_id: Optional[str] = None) -> None: ...
    def auth_log(self, *, tenant: Optional[str] = None, result: Optional[str] = None,
                 limit: int = 100) -> List[AuthLogEntry]: ...


def _new_run_id() -> str:
    return uuid.uuid4().hex


def _now_epoch() -> int:
    return int(time.time())


class InMemoryStateStore:
    """Non-persistent backend for tests and ephemeral runs."""

    def __init__(self):
        self._state: dict = {}
        self._runs: dict = {}
        self._audit: List[AuditEntry] = []
        self._run_subject: dict = {}
        self._tenants: Dict[str, TenantRecord] = {}
        self._tokens: Dict[str, TokenRecord] = {}        # token_id → record
        self._auth_log: List[AuthLogEntry] = []

    def get_conversation_state(self, workspace, subject):
        return self._state.get((workspace, subject))

    def set_conversation_state(self, workspace, subject, state):
        self._state[(workspace, subject)] = state

    def start_run(self, workspace, role, subject, model=None, started_at=None):
        run_id = _new_run_id()
        rec = RunRecord(run_id, workspace, role, subject, model, None, None,
                        started_at=started_at if started_at is not None else _now_epoch())
        self._runs[run_id] = rec
        self._run_subject[run_id] = (workspace, subject)
        return run_id

    def finish_run(self, run_id, state, iterations, usage=None):
        rec = self._runs[run_id]
        rec.state = state.value
        rec.iterations = iterations
        for field, value in _usage_fields(usage).items():
            setattr(rec, field, value)

    def fail_run(self, run_id, error):
        rec = self._runs[run_id]
        rec.state = "failed"
        rec.error = error

    def get_run(self, run_id):
        return self._runs.get(run_id)

    def list_runs(self, workspace, *, limit=50):
        runs = [r for r in self._runs.values() if r.workspace == workspace]
        return list(reversed(runs))[:limit]

    def spent_since(self, workspace, since_epoch):
        return sum(r.cost_usd for r in self._runs.values()
                   if r.workspace == workspace and r.cost_usd
                   and (r.started_at or 0) >= since_epoch)

    def record_action(self, run_id, tool, kind, gated, at):
        self._audit.append(AuditEntry(run_id, tool, kind, gated, at))

    def audit_trail(self, *, workspace=None, subject=None):
        def match(entry):
            ws, subj = self._run_subject.get(entry.run_id, (None, None))
            return (workspace is None or ws == workspace) and (subject is None or subj == subject)
        return [e for e in self._audit if match(e)]

    def upsert_tenant(self, tenant, *, enabled=True, budget_daily_usd=None,
                      budget_monthly_usd=None, rate_limit_per_min=None):
        self._tenants[tenant] = TenantRecord(tenant, enabled, budget_daily_usd,
                                             budget_monthly_usd, rate_limit_per_min)

    def get_tenant(self, tenant):
        return self._tenants.get(tenant)

    def list_tenants(self):
        return list(self._tenants.values())

    def add_token(self, tenant, token_hash, *, scopes=(), label=None, expires_at=None,
                  created_at=None):
        token_id = uuid.uuid4().hex
        self._tokens[token_id] = TokenRecord(token_id, tenant, token_hash, list(scopes),
                                             False, label, expires_at, created_at)
        return token_id

    def get_token_by_hash(self, token_hash):
        for rec in self._tokens.values():
            if rec.token_hash == token_hash:
                return rec
        return None

    def revoke_token(self, token_id):
        rec = self._tokens.get(token_id)
        if rec:
            rec.revoked = True

    def list_tokens(self, tenant):
        return [r for r in self._tokens.values() if r.tenant == tenant]

    def record_auth(self, *, at, route, method, result, reason, tenant=None,
                    source_ip=None, request_id=None):
        self._auth_log.append(AuthLogEntry(at, route, method, result, reason,
                                           tenant, source_ip, request_id))

    def auth_log(self, *, tenant=None, result=None, limit=100):
        rows = [e for e in self._auth_log
                if (tenant is None or e.tenant == tenant)
                and (result is None or e.result == result)]
        return list(reversed(rows))[:limit]


_RUN_COLUMNS = "run_id, workspace, role, subject, model, state, iterations, error, " \
               "cost_usd, tokens_in, tokens_out, num_turns, duration_ms, ttft_ms, metrics_json, " \
               "started_at"


class SqliteStateStore:
    """SQLite backend — local dev (a file path, or ``:memory:``). Postgres is a later backend
    behind this same interface; call sites do not change."""

    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversation_state (
                workspace TEXT NOT NULL, subject TEXT NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY (workspace, subject)
            );
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, workspace TEXT NOT NULL, role TEXT NOT NULL,
                subject TEXT NOT NULL, model TEXT, state TEXT, iterations INTEGER,
                error TEXT, cost_usd REAL, tokens_in INTEGER, tokens_out INTEGER,
                num_turns INTEGER, duration_ms INTEGER, ttft_ms INTEGER, metrics_json TEXT,
                started_at INTEGER, seq INTEGER
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                tool TEXT NOT NULL, kind TEXT NOT NULL, gated INTEGER NOT NULL, at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tenants (
                tenant TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1,
                budget_daily_usd REAL, budget_monthly_usd REAL, rate_limit_per_min INTEGER
            );
            CREATE TABLE IF NOT EXISTS api_tokens (
                token_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
                scopes TEXT, revoked INTEGER NOT NULL DEFAULT 0,
                label TEXT, expires_at TEXT, created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);
            CREATE TABLE IF NOT EXISTS auth_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, route TEXT NOT NULL,
                method TEXT NOT NULL, result TEXT NOT NULL, reason TEXT NOT NULL,
                tenant TEXT, source_ip TEXT, request_id TEXT
            );
            """
        )
        self._migrate()
        self._conn.commit()

    def _migrate(self):
        """Add columns introduced after the first schema (forward-compatible with older dev DBs)."""
        existing = {r["name"] for r in self._conn.execute("PRAGMA table_info(runs)")}
        for col, decl in (("error", "TEXT"), ("cost_usd", "REAL"), ("tokens_in", "INTEGER"),
                          ("tokens_out", "INTEGER"), ("num_turns", "INTEGER"),
                          ("duration_ms", "INTEGER"), ("ttft_ms", "INTEGER"),
                          ("metrics_json", "TEXT"), ("started_at", "INTEGER")):
            if col not in existing:
                self._conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {decl}")

    def close(self):
        self._conn.close()

    def get_conversation_state(self, workspace, subject):
        row = self._conn.execute(
            "SELECT state FROM conversation_state WHERE workspace=? AND subject=?",
            (workspace, subject),
        ).fetchone()
        return ConversationState(row["state"]) if row else None

    def set_conversation_state(self, workspace, subject, state):
        self._conn.execute(
            "INSERT INTO conversation_state (workspace, subject, state) VALUES (?, ?, ?) "
            "ON CONFLICT(workspace, subject) DO UPDATE SET state=excluded.state",
            (workspace, subject, state.value),
        )
        self._conn.commit()

    def start_run(self, workspace, role, subject, model=None, started_at=None):
        run_id = _new_run_id()
        seq = self._conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM runs").fetchone()[0]
        self._conn.execute(
            "INSERT INTO runs (run_id, workspace, role, subject, model, started_at, seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, workspace, role, subject, model,
             started_at if started_at is not None else _now_epoch(), seq),
        )
        self._conn.commit()
        return run_id

    def finish_run(self, run_id, state, iterations, usage=None):
        u = _usage_fields(usage)
        self._conn.execute(
            "UPDATE runs SET state=?, iterations=?, cost_usd=?, tokens_in=?, tokens_out=?, "
            "num_turns=?, duration_ms=?, ttft_ms=?, metrics_json=? WHERE run_id=?",
            (state.value, iterations, u["cost_usd"], u["tokens_in"], u["tokens_out"],
             u["num_turns"], u["duration_ms"], u["ttft_ms"], u["metrics_json"], run_id),
        )
        self._conn.commit()

    def fail_run(self, run_id, error):
        self._conn.execute("UPDATE runs SET state='failed', error=? WHERE run_id=?", (error, run_id))
        self._conn.commit()

    def get_run(self, run_id):
        row = self._conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return RunRecord(**dict(row)) if row else None

    def list_runs(self, workspace, *, limit=50):
        rows = self._conn.execute(
            f"SELECT {_RUN_COLUMNS} FROM runs WHERE workspace=? ORDER BY seq DESC LIMIT ?",
            (workspace, limit),
        ).fetchall()
        return [RunRecord(**dict(r)) for r in rows]

    def spent_since(self, workspace, since_epoch):
        row = self._conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM runs WHERE workspace=? AND started_at>=?",
            (workspace, since_epoch),
        ).fetchone()
        return float(row[0])

    def record_action(self, run_id, tool, kind, gated, at):
        self._conn.execute(
            "INSERT INTO audit (run_id, tool, kind, gated, at) VALUES (?, ?, ?, ?, ?)",
            (run_id, tool, kind, 1 if gated else 0, at),
        )
        self._conn.commit()

    def audit_trail(self, *, workspace=None, subject=None):
        sql = ("SELECT a.run_id, a.tool, a.kind, a.gated, a.at FROM audit a "
               "JOIN runs r ON r.run_id = a.run_id")
        clauses, params = [], []
        if workspace is not None:
            clauses.append("r.workspace=?"); params.append(workspace)
        if subject is not None:
            clauses.append("r.subject=?"); params.append(subject)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY a.id"
        rows = self._conn.execute(sql, params).fetchall()
        return [AuditEntry(r["run_id"], r["tool"], r["kind"], bool(r["gated"]), r["at"]) for r in rows]

    def upsert_tenant(self, tenant, *, enabled=True, budget_daily_usd=None,
                      budget_monthly_usd=None, rate_limit_per_min=None):
        self._conn.execute(
            "INSERT INTO tenants (tenant, enabled, budget_daily_usd, budget_monthly_usd, "
            "rate_limit_per_min) VALUES (?, ?, ?, ?, ?) ON CONFLICT(tenant) DO UPDATE SET "
            "enabled=excluded.enabled, budget_daily_usd=excluded.budget_daily_usd, "
            "budget_monthly_usd=excluded.budget_monthly_usd, rate_limit_per_min=excluded.rate_limit_per_min",
            (tenant, 1 if enabled else 0, budget_daily_usd, budget_monthly_usd, rate_limit_per_min),
        )
        self._conn.commit()

    def get_tenant(self, tenant):
        row = self._conn.execute(
            f"SELECT {_TENANT_COLUMNS} FROM tenants WHERE tenant=?", (tenant,)).fetchone()
        return _tenant_from_row(row) if row else None

    def list_tenants(self):
        rows = self._conn.execute(f"SELECT {_TENANT_COLUMNS} FROM tenants ORDER BY tenant").fetchall()
        return [_tenant_from_row(r) for r in rows]

    def add_token(self, tenant, token_hash, *, scopes=(), label=None, expires_at=None,
                  created_at=None):
        token_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO api_tokens (token_id, tenant, token_hash, scopes, revoked, label, "
            "expires_at, created_at) VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
            (token_id, tenant, token_hash, _dump_scopes(scopes), label, expires_at, created_at),
        )
        self._conn.commit()
        return token_id

    def get_token_by_hash(self, token_hash):
        row = self._conn.execute(
            f"SELECT {_TOKEN_COLUMNS} FROM api_tokens WHERE token_hash=?", (token_hash,)).fetchone()
        return _token_from_row(row) if row else None

    def revoke_token(self, token_id):
        self._conn.execute("UPDATE api_tokens SET revoked=1 WHERE token_id=?", (token_id,))
        self._conn.commit()

    def list_tokens(self, tenant):
        rows = self._conn.execute(
            f"SELECT {_TOKEN_COLUMNS} FROM api_tokens WHERE tenant=? ORDER BY created_at",
            (tenant,)).fetchall()
        return [_token_from_row(r) for r in rows]

    def record_auth(self, *, at, route, method, result, reason, tenant=None,
                    source_ip=None, request_id=None):
        self._conn.execute(
            f"INSERT INTO auth_log ({_AUTHLOG_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (at, route, method, result, reason, tenant, source_ip, request_id),
        )
        self._conn.commit()

    def auth_log(self, *, tenant=None, result=None, limit=100):
        sql = f"SELECT {_AUTHLOG_COLUMNS} FROM auth_log"
        clauses, params = [], []
        if tenant is not None:
            clauses.append("tenant=?"); params.append(tenant)
        if result is not None:
            clauses.append("result=?"); params.append(result)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [_authlog_from_row(r) for r in rows]


class PostgresStateStore:
    """PostgreSQL backend — production (and local-iso-prod). Same interface as the others;
    ``psycopg`` is imported lazily so the package stays install-free until Postgres is used.

    ``dsn`` e.g. ``postgresql://user:pass@host:5432/db``. A small connection pool makes it safe
    under FastAPI's threadpool (sync handlers run concurrently)."""

    def __init__(self, dsn: str):
        from psycopg_pool import ConnectionPool
        self._pool = ConnectionPool(dsn, min_size=1, open=True)
        self._init_schema()

    def _init_schema(self):
        with self._pool.connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS conversation_state ("
                         "workspace TEXT NOT NULL, subject TEXT NOT NULL, state TEXT NOT NULL,"
                         "PRIMARY KEY (workspace, subject))")
            conn.execute("CREATE TABLE IF NOT EXISTS runs ("
                         "run_id TEXT PRIMARY KEY, workspace TEXT NOT NULL, role TEXT NOT NULL,"
                         "subject TEXT NOT NULL, model TEXT, state TEXT, iterations INTEGER,"
                         "error TEXT, cost_usd DOUBLE PRECISION, tokens_in INTEGER, tokens_out INTEGER,"
                         "num_turns INTEGER, duration_ms INTEGER, ttft_ms INTEGER, metrics_json TEXT,"
                         "started_at BIGINT, seq BIGSERIAL)")
            conn.execute("CREATE TABLE IF NOT EXISTS audit ("
                         "id BIGSERIAL PRIMARY KEY, run_id TEXT NOT NULL, tool TEXT NOT NULL,"
                         "kind TEXT NOT NULL, gated BOOLEAN NOT NULL, at TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS tenants ("
                         "tenant TEXT PRIMARY KEY, enabled BOOLEAN NOT NULL DEFAULT TRUE,"
                         "budget_daily_usd DOUBLE PRECISION, budget_monthly_usd DOUBLE PRECISION,"
                         "rate_limit_per_min INTEGER)")
            conn.execute("CREATE TABLE IF NOT EXISTS api_tokens ("
                         "token_id TEXT PRIMARY KEY, tenant TEXT NOT NULL,"
                         "token_hash TEXT NOT NULL UNIQUE, scopes TEXT,"
                         "revoked BOOLEAN NOT NULL DEFAULT FALSE, label TEXT,"
                         "expires_at TEXT, created_at TEXT)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash)")
            conn.execute("CREATE TABLE IF NOT EXISTS auth_log ("
                         "id BIGSERIAL PRIMARY KEY, at TEXT NOT NULL, route TEXT NOT NULL,"
                         "method TEXT NOT NULL, result TEXT NOT NULL, reason TEXT NOT NULL,"
                         "tenant TEXT, source_ip TEXT, request_id TEXT)")
            for col, decl in (("error", "TEXT"), ("cost_usd", "DOUBLE PRECISION"),
                              ("tokens_in", "INTEGER"), ("tokens_out", "INTEGER"),
                              ("num_turns", "INTEGER"), ("duration_ms", "INTEGER"),
                              ("ttft_ms", "INTEGER"), ("metrics_json", "TEXT"),
                              ("started_at", "BIGINT")):
                conn.execute(f"ALTER TABLE runs ADD COLUMN IF NOT EXISTS {col} {decl}")

    def _dict_rows(self, conn):
        from psycopg.rows import dict_row
        return conn.cursor(row_factory=dict_row)

    def get_conversation_state(self, workspace, subject):
        with self._pool.connection() as conn:
            row = conn.execute("SELECT state FROM conversation_state WHERE workspace=%s AND subject=%s",
                               (workspace, subject)).fetchone()
        return ConversationState(row[0]) if row else None

    def set_conversation_state(self, workspace, subject, state):
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO conversation_state (workspace, subject, state) VALUES (%s, %s, %s) "
                         "ON CONFLICT (workspace, subject) DO UPDATE SET state=EXCLUDED.state",
                         (workspace, subject, state.value))

    def start_run(self, workspace, role, subject, model=None, started_at=None):
        run_id = _new_run_id()
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO runs (run_id, workspace, role, subject, model, started_at) "
                         "VALUES (%s,%s,%s,%s,%s,%s)",
                         (run_id, workspace, role, subject, model,
                          started_at if started_at is not None else _now_epoch()))
        return run_id

    def finish_run(self, run_id, state, iterations, usage=None):
        u = _usage_fields(usage)
        with self._pool.connection() as conn:
            conn.execute("UPDATE runs SET state=%s, iterations=%s, cost_usd=%s, tokens_in=%s, tokens_out=%s, "
                         "num_turns=%s, duration_ms=%s, ttft_ms=%s, metrics_json=%s WHERE run_id=%s",
                         (state.value, iterations, u["cost_usd"], u["tokens_in"], u["tokens_out"],
                          u["num_turns"], u["duration_ms"], u["ttft_ms"], u["metrics_json"], run_id))

    def fail_run(self, run_id, error):
        with self._pool.connection() as conn:
            conn.execute("UPDATE runs SET state='failed', error=%s WHERE run_id=%s", (error, run_id))

    def get_run(self, run_id):
        with self._pool.connection() as conn:
            row = self._dict_rows(conn).execute(
                f"SELECT {_RUN_COLUMNS} FROM runs WHERE run_id=%s", (run_id,)).fetchone()
        return RunRecord(**row) if row else None

    def list_runs(self, workspace, *, limit=50):
        with self._pool.connection() as conn:
            rows = self._dict_rows(conn).execute(
                f"SELECT {_RUN_COLUMNS} FROM runs WHERE workspace=%s ORDER BY seq DESC LIMIT %s",
                (workspace, limit)).fetchall()
        return [RunRecord(**r) for r in rows]

    def spent_since(self, workspace, since_epoch):
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM runs WHERE workspace=%s AND started_at>=%s",
                (workspace, since_epoch)).fetchone()
        return float(row[0])

    def record_action(self, run_id, tool, kind, gated, at):
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO audit (run_id, tool, kind, gated, at) VALUES (%s,%s,%s,%s,%s)",
                         (run_id, tool, kind, bool(gated), at))

    def audit_trail(self, *, workspace=None, subject=None):
        sql = "SELECT a.run_id, a.tool, a.kind, a.gated, a.at FROM audit a JOIN runs r ON r.run_id = a.run_id"
        clauses, params = [], []
        if workspace is not None:
            clauses.append("r.workspace=%s"); params.append(workspace)
        if subject is not None:
            clauses.append("r.subject=%s"); params.append(subject)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY a.id"
        with self._pool.connection() as conn:
            rows = self._dict_rows(conn).execute(sql, params).fetchall()
        return [AuditEntry(r["run_id"], r["tool"], r["kind"], bool(r["gated"]), r["at"]) for r in rows]

    def upsert_tenant(self, tenant, *, enabled=True, budget_daily_usd=None,
                      budget_monthly_usd=None, rate_limit_per_min=None):
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO tenants (tenant, enabled, budget_daily_usd, budget_monthly_usd, "
                "rate_limit_per_min) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (tenant) DO UPDATE SET "
                "enabled=EXCLUDED.enabled, budget_daily_usd=EXCLUDED.budget_daily_usd, "
                "budget_monthly_usd=EXCLUDED.budget_monthly_usd, rate_limit_per_min=EXCLUDED.rate_limit_per_min",
                (tenant, enabled, budget_daily_usd, budget_monthly_usd, rate_limit_per_min))

    def get_tenant(self, tenant):
        with self._pool.connection() as conn:
            row = self._dict_rows(conn).execute(
                f"SELECT {_TENANT_COLUMNS} FROM tenants WHERE tenant=%s", (tenant,)).fetchone()
        return _tenant_from_row(row) if row else None

    def list_tenants(self):
        with self._pool.connection() as conn:
            rows = self._dict_rows(conn).execute(
                f"SELECT {_TENANT_COLUMNS} FROM tenants ORDER BY tenant").fetchall()
        return [_tenant_from_row(r) for r in rows]

    def add_token(self, tenant, token_hash, *, scopes=(), label=None, expires_at=None,
                  created_at=None):
        token_id = uuid.uuid4().hex
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO api_tokens (token_id, tenant, token_hash, scopes, revoked, label, "
                "expires_at, created_at) VALUES (%s, %s, %s, %s, FALSE, %s, %s, %s)",
                (token_id, tenant, token_hash, _dump_scopes(scopes), label, expires_at, created_at))
        return token_id

    def get_token_by_hash(self, token_hash):
        with self._pool.connection() as conn:
            row = self._dict_rows(conn).execute(
                f"SELECT {_TOKEN_COLUMNS} FROM api_tokens WHERE token_hash=%s", (token_hash,)).fetchone()
        return _token_from_row(row) if row else None

    def revoke_token(self, token_id):
        with self._pool.connection() as conn:
            conn.execute("UPDATE api_tokens SET revoked=TRUE WHERE token_id=%s", (token_id,))

    def list_tokens(self, tenant):
        with self._pool.connection() as conn:
            rows = self._dict_rows(conn).execute(
                f"SELECT {_TOKEN_COLUMNS} FROM api_tokens WHERE tenant=%s ORDER BY created_at",
                (tenant,)).fetchall()
        return [_token_from_row(r) for r in rows]

    def record_auth(self, *, at, route, method, result, reason, tenant=None,
                    source_ip=None, request_id=None):
        with self._pool.connection() as conn:
            conn.execute(
                f"INSERT INTO auth_log ({_AUTHLOG_COLUMNS}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (at, route, method, result, reason, tenant, source_ip, request_id))

    def auth_log(self, *, tenant=None, result=None, limit=100):
        sql = f"SELECT {_AUTHLOG_COLUMNS} FROM auth_log"
        clauses, params = [], []
        if tenant is not None:
            clauses.append("tenant=%s"); params.append(tenant)
        if result is not None:
            clauses.append("result=%s"); params.append(result)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT %s"
        params.append(limit)
        with self._pool.connection() as conn:
            rows = self._dict_rows(conn).execute(sql, params).fetchall()
        return [_authlog_from_row(r) for r in rows]

    def close(self):
        self._pool.close()


def local_state_store(path: str = "cortex-runtime.db") -> StateStore:
    """Dev convenience: a file-backed SQLite store."""
    return SqliteStateStore(path)


def store_from_env() -> StateStore:
    """Select a backend from the environment (shared by the server and the admin CLI):
    ``CORTEX_DATABASE_URL`` → Postgres, else ``CORTEX_DB`` → SQLite file, else in-memory."""
    import os
    db_url = os.environ.get("CORTEX_DATABASE_URL")
    if db_url:
        return PostgresStateStore(db_url)
    db = os.environ.get("CORTEX_DB")
    return SqliteStateStore(db) if db else InMemoryStateStore()
