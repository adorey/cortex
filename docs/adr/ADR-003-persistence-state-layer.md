# ADR-003 — Persistence & operational state layer

- **Status:** Accepted
- **Date:** 2026-06-02 (proposed) · 2026-06-02 (accepted)
- **Authors:** Cortex maintainers (initiated by l'humanoïde, architecture by @Slartibartfast, dispatched by @Oolon)
- **Affects:** `cortex-runtime` (the agentic loop §3.3, the audit requirement §3.6), monitoring/observability routes, a future admin GUI
- **Relates to:** [ADR-002](ADR-002-cortex-runtime.md) — this ADR adds the *operational state* the runtime needs, **without** breaching ADR-002's firewall; [ADR-001](ADR-001-layered-overrides.md) — the spec stays git-versioned, untouched here

---

## 1. Context

`cortex-runtime` (ADR-002) is, today, **stateless**. Resolution is pure (spec in → prompt out) and the agentic loop holds its `StateMachine` **in memory for the duration of a single run**. Three needs break that assumption:

1. **Anti-recursion across invocations.** The loop's state machine (`awaiting-agent → awaiting-human → resolved`, ADR-002 §3.3) only works if it **survives between webhooks**. The real support flow is: webhook → agent posts an internal comment → state `awaiting-human` → *(hours later)* human replies → webhook → agent re-runs. With in-memory state, the second webhook has no memory of the first — the agent would react to its own comment. **The anti-recursion guarantee is currently non-functional end-to-end.**
2. **Audit log.** ADR-002 §3.6 **mandates** "an audit log of every action." That is, by definition, persistent operational state.
3. **Monitoring & history.** The future monitoring routes and steering dashboard (ADR-002 follow-up #6) need queryable run history and metrics.

### The tension (and the firewall)

ADR-002 is categorical: *"project specificity travels in the project's own git (overlays + manifest), never in the engine,"* and §5 explicitly **rejects** low-code platforms because *"the brain lives in their UI/DB, not in the project's git."* So introducing a database is dangerous **if it swallows the spec**. The whole value of this ADR is in drawing — and policing — a precise boundary.

## 2. Decision

We introduce a **persistence layer for *operational* state only**, behind a **swappable `StateStore` interface** (the same discipline as ADR-002's `SecretProvider`): **SQLite** for local development, **PostgreSQL** in production.

> **The firewall, restated for state:** **git holds what *defines* an agent (declarative, versioned). The DB holds what an agent *produces or lives* at runtime (operational).** The spec is never moved into the database.

### The boundary — what lives where

| Element | Lives in | Why |
|---|---|---|
| Cascade `cortex/agents/**` (+ overlays), `project-overview.md`, `project-context.md` | **git** | The spec — ADR-002 firewall. |
| Manifest (endpoint aliases → `/run`) | **git** | Project-declared spec, not engine config. |
| `.active-theme` | local file (gitignored) | Per-developer choice. |
| **Conversation/run state** per `subject` (the StateMachine) | **DB** | Must survive between invocations → anti-recursion. (`subject` = the host's correlation key, e.g. an issue key.) |
| **Audit log** (every action: tool, kind, run, actor, timestamp) | **DB** | Mandated by ADR-002 §3.6. |
| **Run history / metrics** | **DB** | Monitoring routes + dashboard. |
| Workspace registry (workspace → mirror path, theme, enabled) | **DB** *(later)* | Operational config — a *pointer*, not the spec. The content it points at stays git. |

The grey-zone rule: *"where does workspace X's cascade live?"* → **git** (its mirror). *"is X enabled, at which mirror, with which theme?"* → **DB** (operational config). The pointer may live in the database; the content pointed at never does.

## 3. Detailed contract

### 3.1 The `StateStore` boundary

A single swappable interface, consumed by the loop and the API; the backend is a deployment choice (§3.3).

```python
class StateStore(Protocol):
    # — conversation state (anti-recursion across invocations) —
    def get_conversation_state(self, workspace: str, subject: str) -> Optional[ConversationState]: ...
    def set_conversation_state(self, workspace: str, subject: str, state: ConversationState) -> None: ...

    # — run lifecycle + history —
    def start_run(self, workspace: str, role: str, subject: str, model: Optional[str]) -> str:  # → run_id
        ...
    def finish_run(self, run_id: str, state: ConversationState, iterations: int) -> None: ...
    def list_runs(self, workspace: str, *, limit: int = 50) -> list: ...

    # — audit log (append-only) —
    def record_action(self, run_id: str, tool: str, kind: str, gated: bool, at: str) -> None: ...
    def audit_trail(self, *, workspace: str = None, subject: str = None) -> list: ...
```

- **`subject` is the agnostic correlation key** for one conversation/flow — *not* a domain term. The host maps its own identifier onto it: a support issue key, a dashboard correlation id, a scheduled-run key. The engine stays generic (ADR-002 §4, "one engine, many consumers"); it never knows it is dealing with a "ticket".
- **Append-only audit.** `record_action` is never updated or deleted in place; corrections are new rows (mirrors the spec's archiving discipline).
- **Conversation state is keyed by `(workspace, subject)`** — the anti-recursion guard (`StateMachine.can_trigger_agent`) loads it at the start of every invocation and persists every transition.
- **`ConversationState` is reused verbatim** from `cortex_runtime.safety` — no duplication of the state vocabulary.

### 3.2 Backends — swappable, like secrets

| Backend | When | Notes |
|---|---|---|
| **SQLite** | local dev, single-node | zero-ops, file-based; the default in `local_*` factories |
| **PostgreSQL** | production, multi-tenant | concurrency, retention, the audit store of record |

The application always consumes `StateStore`; migrating SQLite → Postgres swaps only the backend (and a migration tool, e.g. Alembic), never the call sites. An in-memory backend serves the test suite (install-free).

### 3.3 Wiring into the loop (ADR-002 §3.3)

- At invocation receipt: load `(workspace, subject)` state; if not `awaiting-agent`, **refuse to trigger** (the existing `StateMachine` guard, now durable).
- Each executed or gated action → `record_action` (the §3.6 audit).
- On loop exit: `set_conversation_state` to the new state (`awaiting-human` / `resolved` / `escalated`) and `finish_run`.

### 3.4 What this ADR explicitly does NOT do

- It does **not** move spec, overlays, or manifests into the DB (firewall).
- It does **not** build the admin GUI or hot-config of workspaces — that is a later ADR; this layer only makes it *possible* without rework.
- It does **not** introduce a cache/queue (Redis) — out of scope; can come later for hot state.

## 4. Consequences

### Positive
- **Anti-recursion actually works** across webhooks — the support flow becomes end-to-end correct.
- **Audit & monitoring unlocked** — the §3.6 mandate is satisfied; monitoring routes have a store.
- **Firewall preserved** — operational state in DB, spec in git; the boundary is explicit and reviewable.
- **No rework later** — laying the `StateStore` interface now lets the GUI / hot-config / dashboard land without reverting the loop.

### Negative
- **A stateful service to operate** — migrations, backups, retention. This deepens ADR-002's "a platform to operate" cost.
- **Boundary-creep risk** — convenience will tempt config/spec into the DB; the boundary (§2) must be enforced in review, like the firewall.
- **GDPR surface** — audit logs and ticket state may hold personal data → retention + anonymisation policy required (links to ADR-002 §3.6 data-protection note).

### Neutral
- **Backend is swappable** — SQLite now, Postgres later, in-memory in tests.
- **Schema will evolve** — the interface is the stable contract; tables are an implementation detail behind it.

## 5. Alternatives considered

| Alternative | Rejected because |
|---|---|
| **Stay stateless / in-memory** | Anti-recursion breaks between webhooks; no audit. The need is real and present, not speculative. |
| **Everything in the DB (incl. spec + config)** | Violates the ADR-002 firewall; re-fragments the "brain" out of git — the exact low-code anti-pattern §5 rejects. |
| **Persist state in git** | git is for declarative, low-churn spec — not high-frequency operational state and audit; concurrency/locking would be miserable. |
| **External log/SIEM for audit only** | Covers audit, but conversation state needs a queryable, transactional store; one relational store covers both for the MVP. (A SIEM export remains a later option.) |
| **Redis/KV for state** | Good for hot state later, but audit + history want relational queries; a single relational store is simpler to start. |

## 6. Follow-ups (out of scope for this ADR)

1. **`StateStore` MVP** — interface + SQLite backend + in-memory test backend; wire conversation-state persistence and the audit log into the loop.
2. **PostgreSQL backend** + migration tooling (e.g. Alembic).
3. **Monitoring routes** — read the audit/run-history store (`GET /runs`, `GET /audit`).
4. **Admin GUI / hot-config** of the workspace registry — its own ADR (the pointer-in-DB grey zone).
5. **Retention & anonymisation** policy for audit/state (GDPR, ADR-002 §3.6).

## 7. References

- [ADR-002 — Cortex Runtime](ADR-002-cortex-runtime.md) — §3.3 (state machine, the loop) and §3.6 (audit mandate, secrets discipline this ADR mirrors)
- [ADR-001 — Layered overrides](ADR-001-layered-overrides.md) — the git-versioned spec, untouched
- [runtime/cortex_runtime/safety.py](../../runtime/cortex_runtime/safety.py) — `ConversationState` / `StateMachine` this layer persists
