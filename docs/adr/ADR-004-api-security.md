# ADR-004 — API security & trust model

- **Status:** Accepted
- **Date:** 2026-06-03 (proposed) · 2026-06-03 (accepted)
- **Authors:** Cortex maintainers (initiated by l'humanoïde, dispatched by @Oolon)
- **Affects:** `cortex-runtime` API boundary (`/run`, `/resolve`, monitoring routes, future `/webhook`), the `SecretProvider` (ADR-002 §3.6), the cost metrics in the `StateStore` (ADR-003)
- **Relates to:** [ADR-002](ADR-002-cortex-runtime.md) §3.6 (secrets inventory: HMAC secret + Runtime API token) and §3.3 (per-run cost guards); [ADR-003](ADR-003-persistence-state-layer.md) (cost/usage persisted per run → budget enforcement)

---

## 1. Context

`cortex-runtime` exposes `POST /run`, which **triggers a model call** — i.e. it spends real money on every invocation. Before opening it to autonomous or external triggers (webhooks, dashboards, cron), it must not be callable by just anyone. The concrete fears:

- **Credit drain** — a bot (or a buggy loop) hammering `/run` and burning the LLM budget.
- **Forged triggers** — a fake "Jira webhook" that didn't come from Jira.
- **Replay** — re-sending a captured valid request.
- **Double-spend** — a webhook provider retrying a delivery → the same ticket processed (and paid for) twice.
- **Unauthorized access** — reading run history / audit, or invoking workspaces one shouldn't.

ADR-002 §3.6 already anticipated two controls — a **webhook HMAC secret** and a **Runtime API token**. This ADR turns that into an explicit, layered model and adds the controls that actually protect the wallet (rate-limiting + a budget cap), which authentication alone does not.

### The key insight

> **Authentication stops strangers. It does not stop an authenticated-but-compromised (or buggy) caller from draining credits.** The wallet is protected by **rate-limiting + a per-tenant budget cap**, not by auth alone.

## 2. Decision

**Defense in depth at the API boundary, with every check performed BEFORE any model call** — a rejected request costs **zero credit**. The order is fixed:

```
request → authenticate → replay/idempotency → rate-limit → budget cap → resolve → run (model call)
            ↑──────────────── all cheap, deterministic, pre-AI ────────────────↑
```

Six layers:

1. **Authentication — two paths, by entry point.**
   - **Webhook path** (`POST /webhook/...`): verify an **HMAC** signature over the raw body + a timestamp, using the provider's shared secret. Webhooks cannot send a Bearer token; HMAC is their standard (GitHub/Stripe/Jira all use it) and it proves **authenticity *and* payload integrity**.
   - **Direct path** (`/run`, `/resolve`, monitoring): a **Bearer token** (the Runtime API token) — the caller controls its request and can set `Authorization`.
2. **Replay protection** (HMAC path): the signed timestamp must be within a tolerance window (±300 s); a short-lived nonce/signature cache rejects exact replays inside the window.
3. **Idempotency**: an idempotency key (the webhook delivery id, or an `Idempotency-Key` header) is recorded; a duplicate returns the prior outcome **without re-running** — no double-spend. (Complementary to, not replaced by, the conversation StateMachine's anti-recursion.)
4. **Rate-limiting**: per-token / per-IP / global sliding window → `429` on exceed. The first line against floods.
5. **Per-tenant budget cap**: refuse a run if the workspace has exceeded its rolling budget. **We already persist `cost_usd` per run (ADR-003)** → sum over a window and compare to the workspace's ceiling. This is the direct credit protection; combined with the existing per-run guards (iteration cap, `max_tokens`), it bounds spend top-down and per-run.
6. **Authorization**: only registered workspaces/roles run (already: unknown workspace → 404); optionally a token is scoped to specific workspaces.

**All secrets** (per-tenant HMAC secrets, Bearer tokens, budget config) come from the **`SecretProvider`** (ADR-002 §3.6) — never hardcoded, never in git.

## 3. Detailed contract

### 3.1 HMAC (webhook authenticity + integrity + anti-replay)
```
Headers:  X-Cortex-Timestamp: <unix seconds>
          X-Cortex-Signature: sha256=<hex>
signature = HMAC_SHA256(secret, f"{timestamp}.{raw_body}")
```
- Reject if `abs(now - timestamp) > 300`.
- **Constant-time** comparison (`hmac.compare_digest`).
- `secret` is per webhook source (per tenant), from the `SecretProvider`.

### 3.2 Bearer (direct callers)
- `Authorization: Bearer <token>`; one token per caller, **revocable, scoped** (which workspaces it may invoke), constant-time compared, from the `SecretProvider`.

### 3.3 Idempotency
- Key = the provider delivery id (or `Idempotency-Key`). A `(key → outcome, expires_at)` store (a StateStore table) with a TTL. On a hit within TTL: return the stored outcome, **skip the run**.

### 3.4 Rate-limiting
- Sliding-window counter keyed by token / IP, plus a global ceiling. Backed by the StateStore now; a Redis backend is a later optimisation. `429` + `Retry-After` on exceed.

### 3.5 Budget cap
- Per-workspace ceiling (e.g. a daily and/or monthly `cost_usd` budget) from config/secret. Before a run: `spent_in_window(workspace) >= ceiling` → refuse (`402`/`429`). Because exact cost is only known *after* the run, enforcement is **accumulated-spend based** + the per-run guards prevent a single run from blowing the budget.

### 3.6 Shape
- An **`AuthPolicy`** / boundary middleware, framework-agnostic and **pure-testable** (sign/verify, window check, rate-limit counter, budget check) — the FastAPI layer stays a thin shell, exactly like the rest of the runtime.
- Failures return clean `401 / 403 / 429 / 402`, are **logged**, and are recorded in the connection log (§3.7).

### 3.7 Tenant model & connection logging

**Tenant registry (operational config → DB).** A `tenants` table holds per-tenant config: `workspace`, `enabled`, budget ceilings (daily/monthly `cost_usd`), rate-limit. A tenant can be added/configured **without a redeploy** (this subsumes ADR-003's workspace-registry grey zone). The *spec* it points at stays in git — the firewall is untouched.

**Bearer tokens (hashed → DB).** An `api_tokens` table stores a **hash** of each token (never the raw value) + `tenant_id`, `scopes` (allowed workspaces), `revoked`, `expires_at`. The raw token is shown to the caller once at issuance; verification hashes the incoming token and compares constant-time. Supports rotation, revocation and multiple tokens per tenant.

**HMAC secrets (raw → SecretProvider, NOT the DB).** Verifying an HMAC requires the *raw* shared secret to recompute the signature, so per-tenant/source HMAC secrets live in the `SecretProvider` (K8s Secret / vault) — never in the app database.

**Budget** is computed from `runs.cost_usd` (ADR-003) over the window versus the tenant's ceiling — no separate spend table.

**Connection log — every attempt, with a reason.** A dedicated `auth_log` table records **every** inbound auth attempt, accepted or rejected:
```
at · tenant (nullable when the caller isn't identified) · source_ip · route ·
method (hmac | bearer) · result (accepted | rejected) · reason · request_id
reason ∈ { ok, invalid_signature, stale_timestamp, replay, unknown_token,
           revoked_token, out_of_scope, tenant_disabled, rate_limited, budget_exceeded, … }
```
This is the **perimeter** log (who tried, the verdict, and why) — **distinct** from the agent `audit` table (what the agent *did* during a run). Exposed read-only for monitoring (`GET /auth-log`).

**New tables:** `tenants`, `api_tokens`, `auth_log` (+ idempotency keys, and rate-limit counters if not on Redis). Raw HMAC secrets and issued raw tokens **never touch the database**.

## 4. Consequences

### Positive
- **Credits protected** by the controls that actually matter (rate-limit + budget cap), reusing the cost data we already persist.
- **Only genuine triggers act** (HMAC), with **no replay** and **no double-spend** (idempotency).
- **Cheap & pre-AI** — every rejection happens before a single token is spent.
- **Reuses what we built** — `SecretProvider` for secrets, the `StateStore` for the new `tenants` / `api_tokens` / `auth_log` tables, rate-limit/idempotency state, and the budget computed from `runs.cost_usd`.
- **Full perimeter observability** — every connection attempt is logged with its verdict and reason (§3.7).

### Negative
- **More to configure** per tenant (HMAC secret, Bearer token, budget). Operational surface grows.
- **State for rate-limit/idempotency** — fine in the StateStore for one node; multi-replica wants Redis (a follow-up).
- **Budget enforcement is approximate** — cost is known post-run; the cap is on accumulated spend (the per-run guards cover the single-run blowout).

### Neutral
- **HMAC vs Bearer is per entry point**, not a global choice.
- **Limits/budgets/windows are configuration**, tunable per tenant.

## 5. Alternatives considered

| Alternative | Rejected because |
|---|---|
| **Auth only (Bearer), no rate-limit/budget** | An authenticated-but-compromised or buggy caller still drains credits — doesn't address the actual fear. |
| **HMAC only** *or* **Bearer only** | Each guards one door. Webhooks can't send a Bearer; direct callers shouldn't sign every payload with a shared webhook secret. Use both, by entry point. |
| **mTLS everywhere** | Strong, but webhook providers (Jira) can't easily do client certs. Keep mTLS as an option for internal service-to-service calls. |
| **IP allowlist** | Webhook source IPs change; brittle. HMAC is the right webhook control. |
| **Delegate all of it to an API gateway / WAF** | Good for edge rate-limiting/WAF, but the **budget cap is app-specific** (needs our per-run cost data) → it stays in-app; a gateway can layer on top. |
| **No idempotency, rely on the StateMachine anti-recursion** | Anti-recursion stops reacting to the agent's *own* output; it does not stop a duplicate *delivery* of the same event from double-running before the first finishes. Explicit idempotency is cleaner. |

## 6. Follow-ups (out of scope for this ADR)

0. **Data model** — `tenants` (config + budget), `api_tokens` (hashed), `auth_log` (connection log) tables; HMAC secrets in the `SecretProvider`.
1. **`AuthPolicy`** boundary middleware — HMAC verify + Bearer + replay window, pure helpers tested; writes every attempt to `auth_log`.
2. **Rate-limiter** (StateStore-backed counter; Redis backend later).
3. **Budget cap** — per-workspace ceiling + `GET /budget` (remaining), enforced from `cost_usd`.
4. **Idempotency store** (StateStore table, TTL).
5. **Secret inventory update** — per-tenant HMAC secret, Bearer tokens, budget config (extends ADR-002 §3.6).
6. **Webhook receiver** endpoint(s) + the trigger/queue/worker wiring (ADR-002 §3.7) — host-specific.

## 7. References

- [ADR-002 — Cortex Runtime](ADR-002-cortex-runtime.md) — §3.6 (secrets: HMAC secret + Runtime API token), §3.3 (iteration cap / `max_tokens` as per-run cost guards)
- [ADR-003 — Persistence & operational state layer](ADR-003-persistence-state-layer.md) — `cost_usd` per run, which the budget cap enforces; the StateStore that holds rate-limit / idempotency / auth-audit state
- [ADR-005 — Execution model & resilience](ADR-005-execution-model-resilience.md) — the robustness counterpart; both gate the autonomous opening (security vs holding up under load/faults)
