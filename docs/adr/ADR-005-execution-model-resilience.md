# ADR-005 — Execution model & resilience

- **Status:** Accepted
- **Date:** 2026-06-03 (proposed) · 2026-06-03 (accepted)
- **Authors:** Cortex maintainers (initiated by l'humanoïde, dispatched by @Oolon)
- **Affects:** `cortex-runtime` API + execution path (`/run`, the agentic loop, the model clients), deployment (K8s probes, serving), the `StateStore` (run lifecycle)
- **Relates to:** [ADR-002](ADR-002-cortex-runtime.md) §3.7 (trigger/queue/worker — host-specific; this ADR pins the runtime's side) and §3.3 (iteration cap / `max_tokens` — per-run cost guards); [ADR-003](ADR-003-persistence-state-layer.md) (run records persist lifecycle → durable async results); [ADR-004](ADR-004-api-security.md) (security — its idempotency key dedups at the queue)

---

## 1. Context

The runtime works, but `POST /run` is **synchronous**: it blocks for the entire agent run (30 s+ for the `claude-cli` backend) and only then returns. This is fine for low-volume / manual use, but it is **not robust enough to open to autonomous, fanning-in triggers** (webhooks):

- **Threadpool saturation** — FastAPI runs our sync handlers in a threadpool (~40 threads). Each long run occupies a thread for its whole duration → throughput is capped at a few dozen concurrent runs, then requests queue behind blocked threads.
- **Hung runs** — without timeouts, a stuck model/CLI call blocks a thread forever. *(A per-run timeout was just added; this ADR generalises the resilience story.)*
- **Webhook expectations** — providers (Jira, GitHub) expect a **fast ack** (a few seconds) and will retry/disable a webhook that blocks for 30 s+.
- **No backpressure** — nothing bounds in-flight runs → a burst can exhaust resources (threads, DB connections, LLM rate).
- **K8s readiness** — only a liveness `/health`; no readiness (DB/worker reachable) for safe rollouts.

This is the **robustness** counterpart to ADR-004 (security). Both gate the full-autonomous opening; this one is about *holding up under load and faults*, not *who is allowed*.

## 2. Decision

Move from **synchronous request-blocking** to **async accept-then-process**, and add resilience guards. Six parts:

1. **Async trigger contract.** `POST /run` (and webhooks) **accept (`202`)** with a `run_id`, **enqueue** the work, and return immediately. The agent run executes on a **worker**. Results are read via the monitoring routes (`GET /runs/{run_id}`) and/or pushed to an optional `callback_url`. A **synchronous mode is preserved for dev/testing** (`?wait=true` or a config flag) — today's behaviour.
2. **Queue + worker, behind an interface.** A `JobQueue` abstraction (the SecretProvider/StateStore discipline): an **in-process async backend** for a single node, a **broker** for multi-node. The runtime defines the contract; the backend is swappable. Recommended split for a stack that already runs both: **RabbitMQ** for the job queue (durable work-queue, ack/nack + requeue on worker crash, dead-letter for poison jobs) and **Redis** for the ephemeral security state (rate-limit counters, idempotency keys, HMAC nonce cache — TTL-native).
3. **Timeouts everywhere.** Per-run timeout on the CLI subprocess and the model API call *(done)*; extend to MCP tool calls. A hung call is killed → the run is recorded `failed` (we already do this), never a zombie thread.
4. **Concurrency cap / backpressure.** Bound in-flight runs (a worker-pool size / semaphore). Beyond it, jobs wait in the queue (not in blocked HTTP threads); optionally shed with `429`.
5. **Health vs readiness.** Keep `/health` (liveness) and add `/ready` (readiness: DB reachable, worker alive) for K8s probes; **graceful shutdown** drains in-flight runs on `SIGTERM`.
6. **Production serving.** Run uvicorn with multiple workers (or `gunicorn` + uvicorn workers) behind the ingress.

The **run lifecycle** (`queued → running → {resolved | awaiting-human | escalated | failed}`) is distinct from the **conversation state** (ADR-003's StateMachine) and is tracked on the run record.

## 3. Detailed contract

### 3.1 Async `/run`
```
POST /run            → 202 { "run_id": "...", "status": "queued" }   (default)
POST /run?wait=true  → 200 { ...full outcome... }                     (dev / sync)
GET  /runs/{run_id}  → { status, state, final_text, metrics, ... }    (poll for the result)
optional: { "callback_url": "https://..." } in the payload → POST the outcome there when done
```

### 3.2 Worker
Pulls a job, runs `run_session` with the per-run timeout, records lifecycle transitions (`running` → terminal). A crash/timeout → `fail_run`. Idempotency (ADR-004) dedups duplicate deliveries at enqueue.

### 3.3 Knobs (env / config)
- `CORTEX_RUN_TIMEOUT` *(done)* — per-run timeout.
- `CORTEX_MAX_CONCURRENT_RUNS` — worker-pool size / semaphore.
- `CORTEX_QUEUE_BACKEND` — `inprocess` | `redis://…`.
- MCP/tool call timeouts.

### 3.4 Shape
- The queue/worker logic is **framework-agnostic and testable** (like the rest): a `JobQueue` interface + an in-process backend exercised with a fake clock/worker; the FastAPI layer stays a thin shell.

## 4. Consequences

### Positive
- **Scales** — throughput is bounded by *workers*, not by blocked request threads; webhooks get a fast `202`.
- **Resilient** — timeouts kill hung runs, the concurrency cap prevents resource exhaustion, graceful shutdown avoids losing in-flight work.
- **K8s-ready** — readiness probe + multi-replica + graceful drain.
- **Reuses what we built** — run records already persist state (durable async results); ADR-004's idempotency dedups at the queue.

### Negative
- **More moving parts** — a queue + worker to operate; a broker for multi-node. Async result delivery (poll/callback) is more complex than a blocking call.
- **Eventual results** — callers no longer get the outcome in the HTTP response by default; they poll or receive a callback.

### Neutral
- **Queue backend swappable** — in-process now, a broker later.
- **Sync mode kept** for local dev.

## 5. Alternatives considered

| Alternative | Rejected because |
|---|---|
| **Keep synchronous, just add more uvicorn workers/threads** | Still blocks per request; hung runs tie up resources; webhooks still time out. Scaling threads only delays saturation. |
| **`async def` handlers, await the run inline** | Frees the event loop from CPU waits, but the run is still long and a request still maps to a long-lived coroutine — accept is not decoupled from process, webhooks still wait. A queue/worker decouples properly. |
| **Fire-and-forget background task (no persistence)** | Runs are lost on restart. Our run records are persisted → a durable queue (or at least persisted lifecycle) is the right base. |
| **A full external workflow engine (Temporal, …)** | Powerful but heavy for the MVP. An interface + a simple broker covers the need; revisit if durable multi-step orchestration is required. |

## 6. Follow-ups

Implemented on `feat/async-execution`:

1. **Async `/run`** — ✅ `POST /run` → `202 {run_id, status:queued}`, a worker executes it, `GET /runs/{id}` polls the lifecycle; **sync via `?wait=true`** and fully sync when no queue is configured (`runtime.prepare`/`execute` split). *Optional `callback_url` push: not yet (poll only).*
2. **Timeouts** — ✅ CLI + model (`CORTEX_RUN_TIMEOUT`). *MCP tool-call timeout: still TODO.*
3. **Concurrency cap + backpressure** — ✅ worker-pool size (`max_concurrent_runs`) + bounded queue → `429 Retry-After` on `QueueFull` (`max_pending_runs`).
4. **Readiness + graceful shutdown** — ✅ `GET /ready` (store reachable + worker alive → `503` when not) + `/health` liveness; the queue drains in-flight runs on shutdown (lifespan). Container healthcheck hits `/ready`. *Multi-replica uvicorn workers: serving concern, deferred.*
5. **`JobQueue` interface + in-process backend** — ✅ `JobQueue` Protocol + `InProcessJobQueue` (thread pool, jobs are plain dicts → broker-ready). *RabbitMQ backend: TODO (multi-node).*
6. **Run lifecycle states** — ✅ `queued → running → {done | failed | skipped}` on the run record (distinct from the conversation `state`).

Still out of scope (later): the **broker (RabbitMQ) `JobQueue`** + **Redis** ephemeral backend (multi-node), the **`callback_url`** push, MCP tool-call timeouts, and multi-worker uvicorn serving.

## 7. References

- [ADR-002 — Cortex Runtime](ADR-002-cortex-runtime.md) — §3.7 (trigger/queue/worker), §3.3 (per-run cost guards complementary to timeouts)
- [ADR-003 — Persistence & operational state layer](ADR-003-persistence-state-layer.md) — run records persist lifecycle → durable async results
- [ADR-004 — API security & trust model](ADR-004-api-security.md) — idempotency dedups at the queue; both ADRs gate the autonomous opening
