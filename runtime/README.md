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
| 3 | Agentic loop, safety rails in code (§3.3) | ⏳ |
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
    registry={"wbtb": WorkspaceConfig(root=Path("/data/mirrors/wbtb"), theme="h2g2")},
    manifest={"/pr-review": {"role": "lead-backend", "workflow": "code-review"}},
)
# POST /run {"workspace":"wbtb","role":"lead-backend","service":"billing","workflow":"code-review"}
# POST /pr-review {"workspace":"wbtb","service":"billing"}   ← role/workflow from the manifest
```

The resolution core (`resolve_run`, `derive_capabilities`, alias merging) is
framework-agnostic and lives in `run.py` / `context.py` / `app.py` — tested without FastAPI.

## Run the tests (zero install)

```bash
cd runtime
python3 -m unittest discover -s tests -v
```
