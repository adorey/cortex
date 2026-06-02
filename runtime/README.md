# cortex-runtime

The **deployable engine** of Cortex. It compiles [ADR-001](../docs/adr/ADR-001-layered-overrides.md)
(the layered cascade) into an **executable resolver**, and wraps it in a thin agnostic API,
an agentic loop, and an optional model gateway — see [ADR-002](../docs/adr/ADR-002-cortex-runtime.md).

## The firewall (non-negotiable)

> **The runtime CONSUMES the spec. The spec NEVER depends on the runtime.**

The Markdown cascade (`agents/…`) stays a pure, portable, host-agnostic knowledge layer.
No `role.md` / `workflow.md` / overlay may contain an engine-specific field. This is enforced
mechanically by [`tests/test_firewall.py`](tests/test_firewall.py), not by repo boundaries.

```
cortex-spec     (agents/… markdown cascade, ADR-001)   ← declarative, host-agnostic
      ▲   consumed by (one direction only)
cortex-runtime  (this package: resolver + API + loop)  ← deployable engine
```

## Status — incremental MVP (feat/cortex-runtime)

| Phase | Scope (ADR-002) | State |
|---|---|---|
| 0 | Scaffolding + firewall guard | ✅ |
| 1 | **Resolver** (§3.1 cascade + §3.2 merge) — *the singularity* | ✅ |
| 2 | Agnostic API `POST /run` + `derive_capabilities` + manifest aliases (§3.2) | ✅ |
| 3 | Agentic loop + safety rails in code (§3.3) | ✅ |
| 3b | Agent SDK adapter (`ModelClient`) + secrets `SecretProvider` (§3.6) | ✅ |
| — | Persistence: `StateStore` (durable anti-recursion + audit), [ADR-003](../docs/adr/ADR-003-persistence-state-layer.md) | ✅ |
| 5 | Executable slice: `Runtime` wires resolve→tools→loop→state; `/run` executes; swappable model backend | ✅ |
| 4 | Project binding: warm mirrors + git worktree (§3.4) | ⏳ |
| 5 | Model gateway (§3.5) | deferred |
| 6 | Secrets: `SecretProvider` interface (§3.6) | ⏳ |

## The resolver

`cortex_runtime.resolver` is the Python port of ADR-001 §3.1, with the merge semantics of §3.2:

- `workflows/` → **replacement** (most specific wins entirely)
- `roles/`, `capabilities/`, `personalities/{theme}/theme.md`, `…/{character}.md` → **additive**
- `personalities/{theme}/characters.md` → **not overridable** (base only)

`tests/test_parity.py` asserts the Python resolver agrees with the shipped
[`bin/validate-overlays.sh`](../bin/validate-overlays.sh) on a fixture cascade, so the two
implementations cannot drift apart silently (ADR-002 §3.1).

## Run the slice (Phase 5) — no key, no SDK

The `demo` backend runs the whole wire (resolve → tools → loop → durable state) for free, so
you can smoke-test before connecting a real model:

```bash
cd runtime && pip install -e .            # fastapi for the API; demo backend needs nothing else
CORTEX_ROOT=/path/to/a/project CORTEX_BACKEND=demo python -m cortex_runtime   # serves on :8000
# then:
curl -X POST localhost:8000/run -H 'content-type: application/json' \
  -d '{"workspace":"local","role":"support-engineer","subject":"ACME-7","input":{"issue":"ACME-7"}}'
```

Swap the backend when ready: `CORTEX_BACKEND=claude-cli` (Pro/Max via the Claude Code CLI —
`npm i -g @anthropic-ai/claude-code && claude setup-token`, free at the margin, for local
testing) or `CORTEX_BACKEND=anthropic-api` (a Console key in `.env.local` — for the deployed
service). The Agent SDK *library* cannot use a subscription; only the CLI can. Same
`ModelClient` boundary, no code change. **Setup guide:** [docs/claude-cli-setup.md](docs/claude-cli-setup.md).

In code: `build_runtime({"acme": WorkspaceConfig(root=..., theme="h2g2")}, model_backend="demo")`
→ `runtime.run({...})` returns the outcome (state, actions, comments, audit persisted).

## The agnostic API (Phase 2)

`POST /run` resolves a request into the bundle the agentic loop will consume (the loop
itself is Phase 3). Projects **declare** domain endpoints via a manifest — they do not
write engine code (ADR-002 §3.2):

```python
from pathlib import Path
from cortex_runtime.api import create_app          # needs `pip install -e .[dev]` + fastapi
from cortex_runtime.app import WorkspaceConfig

app = create_app(
    registry={"acme": WorkspaceConfig(root=Path("/data/mirrors/acme"), theme="h2g2")},
    manifest={"/pr-review": {"role": "lead-backend", "workflow": "code-review"}},
)
# POST /run {"workspace":"acme","role":"lead-backend","service":"billing","workflow":"code-review"}
# POST /pr-review {"workspace":"acme","service":"billing"}   ← role/workflow from the manifest
```

The resolution core (`resolve_run`, `derive_capabilities`, alias merging) is
framework-agnostic and lives in `run.py` / `context.py` / `app.py` — tested without FastAPI.

## The agentic loop (Phase 3)

The loop *mechanism* is embedded from an Agent SDK (we don't reinvent `tool_use → result
→ loop`). What is uniquely ours lives in `safety.py` and is enforced in code, never in the
prompt (ADR-002 §3.3):

- **`ActionPolicy`** — autonomy is **per request**, not a hard-coded phase: the caller
  passes `autonomy: ["code-read", "code-write", …]` in the payload (the action kinds the
  agent may take without human validation). Omitted → least-privilege default (reads +
  internal comment). Any action outside the allowlist is **gated** → the loop halts at
  `AWAITING_HUMAN`.
- **`ActionKind`** — a granular taxonomy so autonomy can be sliced finely: `code-read /
  code-write`, `db-read / db-write`, `git-read / git-push`, `issue-read / issue-edit /
  issue-create`, `internal-comment`, `customer-reply`, `delete`.
- **`StateMachine`** — `awaiting-agent → awaiting-human → resolved`, with anti-recursion:
  the agent never runs off its own output.
- **iteration cap** → forced `ESCALATED`.

`loop.AgentLoop` drives a `ModelClient` (the SDK boundary — the real adapter implements
`propose`; tests use a scripted fake) and applies the rails around it.

## Secrets & the model adapter (Phase 3b)

Secrets sit behind one stable interface — `SecretProvider.get(name)` (ADR-002 §3.6) — so
only the *source* swaps:

```python
from cortex_runtime import local_secret_provider, AnthropicAgentClient

secrets = local_secret_provider(namespace="acme")   # .env.local first, then env (K8s in prod)
model = AnthropicAgentClient(registry, secrets)      # pulls llm_key; needs `anthropic` + a key
```

- **Local dev** → a gitignored `.env.local` (copy `.env.local.example`). Per-tenant keys
  are namespaced: `ACME_LLM_KEY`, `OTHER_LLM_KEY`.
- **Production** → environment variables fed by a K8s Secret / a vault — the app code is
  unchanged.

`AnthropicAgentClient` is the `ModelClient` boundary (the loop's plug for a real model). Its
import of `anthropic` is lazy, so the package and its test suite stay install-free; the pure
translation helpers (`interpret_response`, `tool_schemas`) are fully tested.

## Persistence — operational state (ADR-003)

Operational state lives behind one swappable interface, `StateStore` — the same discipline
as secrets. The spec stays in git; only what the agent *produces at runtime* is persisted:
conversation state (durable anti-recursion across invocations), the audit log (§3.6), and
run history. Keyed by an agnostic `subject` (the host's correlation id), never a "ticket".

```python
from cortex_runtime import local_state_store, run_session, mark_human_reply

store = local_state_store("cortex-runtime.db")   # SQLite (dev); InMemoryStateStore in tests
result = run_session(loop, model, store, workspace="acme", role="support-engineer",
                     subject="ACME-7", system_prompt=prompt, initial_input={"issue": "ACME-7"})
# A second trigger on ACME-7 while AWAITING_HUMAN is skipped (anti-recursion);
# mark_human_reply(store, "acme", "ACME-7") re-arms the agent.
```

- **Backends** (swappable): `InMemoryStateStore` (tests), `SqliteStateStore` (local), Postgres later.
- `run_session` is the reference wiring: load state → guard → run → record actions → persist.
- **Resilience**: a run that errors is recorded as `failed` (with the error) and logged — never
  left dangling.
- **Monitoring metrics** per run: `cost_usd`, tokens (in/out), `num_turns`, `duration_ms`,
  `ttft_ms` as queryable columns, plus a full `metrics_json` blob (cache tokens, per-model
  breakdown…) so nothing is lost. The `claude-cli` backend parses them from the CLI result;
  the `anthropic-api` backend reports tokens natively (cost computed from pricing).
- **Audit for the `claude-cli` backend**: the CLI's own tool use is parsed from `stream-json`
  and written to the audit log — including tools the CLI **refused** (not in `--allowedTools`),
  marked `gated` (so the audit shows what ran AND what was blocked). §3.6 holds even though the
  CLI owns the loop.

### Monitoring API (read-only)

The stored metrics are exposed for a host (e.g. a dashboard) to poll:

```
GET /runs?workspace=acme[&limit=50]   → run history (state, cost, tokens, duration, num_turns)
GET /runs/{run_id}                     → one run + its full metrics_json
GET /audit?workspace=&subject=         → the action trail (with the gated flag)
```

## Run the tests (zero install)

```bash
cd runtime
python3 -m unittest discover -s tests -v
```
