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

## Run the tests (zero install)

```bash
cd runtime
python3 -m unittest discover -s tests -v
```
