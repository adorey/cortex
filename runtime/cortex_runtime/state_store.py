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
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Protocol

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


@dataclass
class AuditEntry:
    run_id: str
    tool: str
    kind: str
    gated: bool
    at: str


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
    def start_run(self, workspace: str, role: str, subject: str, model: Optional[str] = None) -> str: ...
    def finish_run(self, run_id: str, state: ConversationState, iterations: int,
                   usage: Optional[Mapping[str, Any]] = None) -> None: ...
    def fail_run(self, run_id: str, error: str) -> None: ...
    def get_run(self, run_id: str) -> Optional[RunRecord]: ...
    def list_runs(self, workspace: str, *, limit: int = 50) -> List[RunRecord]: ...

    # — audit log (append-only) —
    def record_action(self, run_id: str, tool: str, kind: str, gated: bool, at: str) -> None: ...
    def audit_trail(self, *, workspace: Optional[str] = None, subject: Optional[str] = None) -> List[AuditEntry]: ...


def _new_run_id() -> str:
    return uuid.uuid4().hex


class InMemoryStateStore:
    """Non-persistent backend for tests and ephemeral runs."""

    def __init__(self):
        self._state: dict = {}
        self._runs: dict = {}
        self._audit: List[AuditEntry] = []
        self._run_subject: dict = {}

    def get_conversation_state(self, workspace, subject):
        return self._state.get((workspace, subject))

    def set_conversation_state(self, workspace, subject, state):
        self._state[(workspace, subject)] = state

    def start_run(self, workspace, role, subject, model=None):
        run_id = _new_run_id()
        self._runs[run_id] = RunRecord(run_id, workspace, role, subject, model, None, None)
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

    def record_action(self, run_id, tool, kind, gated, at):
        self._audit.append(AuditEntry(run_id, tool, kind, gated, at))

    def audit_trail(self, *, workspace=None, subject=None):
        def match(entry):
            ws, subj = self._run_subject.get(entry.run_id, (None, None))
            return (workspace is None or ws == workspace) and (subject is None or subj == subject)
        return [e for e in self._audit if match(e)]


_RUN_COLUMNS = "run_id, workspace, role, subject, model, state, iterations, error, " \
               "cost_usd, tokens_in, tokens_out, num_turns, duration_ms, ttft_ms, metrics_json"


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
                seq INTEGER
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                tool TEXT NOT NULL, kind TEXT NOT NULL, gated INTEGER NOT NULL, at TEXT NOT NULL
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
                          ("duration_ms", "INTEGER"), ("ttft_ms", "INTEGER"), ("metrics_json", "TEXT")):
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

    def start_run(self, workspace, role, subject, model=None):
        run_id = _new_run_id()
        seq = self._conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM runs").fetchone()[0]
        self._conn.execute(
            "INSERT INTO runs (run_id, workspace, role, subject, model, seq) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, workspace, role, subject, model, seq),
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


def local_state_store(path: str = "cortex-runtime.db") -> StateStore:
    """Dev convenience: a file-backed SQLite store."""
    return SqliteStateStore(path)
