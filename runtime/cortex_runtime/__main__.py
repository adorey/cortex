"""Quick-start entrypoint:  python -m cortex_runtime

Serves a single-workspace runtime configured from environment variables — enough to smoke
-test the slice locally. Multi-workspace / production wiring builds a Runtime in code instead.

    CORTEX_WORKSPACE   workspace name           (default: "local")
    CORTEX_ROOT        path to the project root (default: ".")
    CORTEX_THEME       active theme             (default: none)
    CORTEX_BACKEND     demo | claude-cli | anthropic-api          (default: "demo")
    CORTEX_DATABASE_URL  postgres DSN (postgresql://…) — preferred for prod / local-iso-prod
    CORTEX_DB          sqlite path              (used only if no DATABASE_URL; default: in-memory)
    CORTEX_RUN_TIMEOUT per-run timeout seconds  (kills a hung agent run; default: 600)
    CORTEX_AUTH        on | off                 (ADR-004 Bearer security; default: off)
                       seed tenants/tokens with `python -m cortex_runtime.admin`
    CORTEX_ASYNC       on | off                 (ADR-005: enqueue runs, POST /run → 202; default: off)
    CORTEX_MAX_CONCURRENT_RUNS  worker-pool size / concurrency cap        (default: 4)
    CORTEX_MAX_PENDING_RUNS     bounded queue → 429 when full             (default: 100)
    CORTEX_MCP_CONFIG  path to a JSON file: {"mcp_servers": {...}, "mcp_bindings": {...}}
                       — MCP servers for the CLI (e.g. Jira) + ActionKind→MCP-tool bindings
    CORTEX_HOST/PORT   bind address             (default: 127.0.0.1:8000)

`demo` runs the whole wire with no key or CLI. Switch to `claude-cli` (Pro/Max via the Claude
Code CLI + `claude setup-token`) for local testing with a real model, or `anthropic-api` (a
Console key in .env.local) for a deployed service.
"""

from __future__ import annotations

import os
from pathlib import Path


def main():
    import uvicorn  # lazy: only needed to actually serve

    from .api import create_app
    from .app import WorkspaceConfig
    from .runtime import build_runtime
    from .state_store import store_from_env

    workspace = os.environ.get("CORTEX_WORKSPACE", "local")
    root = Path(os.environ.get("CORTEX_ROOT", "."))
    theme = os.environ.get("CORTEX_THEME") or None
    backend = os.environ.get("CORTEX_BACKEND", "demo")

    store = store_from_env()

    mcp_servers = mcp_bindings = None
    mcp_cfg = os.environ.get("CORTEX_MCP_CONFIG")
    if mcp_cfg:
        import json
        cfg = json.loads(Path(mcp_cfg).read_text(encoding="utf-8"))
        mcp_servers, mcp_bindings = cfg.get("mcp_servers"), cfg.get("mcp_bindings")

    runtime = build_runtime(
        {workspace: WorkspaceConfig(root=root, theme=theme,
                                    mcp_servers=mcp_servers, mcp_bindings=mcp_bindings)},
        store=store,
        model_backend=backend,
        run_timeout=int(os.environ.get("CORTEX_RUN_TIMEOUT", "600")),
        max_concurrent_runs=int(os.environ.get("CORTEX_MAX_CONCURRENT_RUNS", "4")),
        max_pending_runs=int(os.environ.get("CORTEX_MAX_PENDING_RUNS", "100")),
    )

    def _on(name: str) -> bool:
        return os.environ.get(name, "").lower() in ("1", "true", "on", "yes")

    # Security (ADR-004) is opt-in: CORTEX_AUTH=on protects the direct + monitoring routes with
    # Bearer tokens and runs the rate/budget/idempotency chain on /run. Register tenants and mint
    # tokens with `python -m cortex_runtime.admin` (see its --help).
    gate = None
    if _on("CORTEX_AUTH"):
        from .security_gate import build_gate
        gate = build_gate(store, runtime.cfg.secrets)

    # Async execution (ADR-005) is opt-in: CORTEX_ASYNC=on enqueues runs (POST /run → 202) and a
    # worker pool executes them; ?wait=true keeps the synchronous path. The queue's lifespan
    # (start + graceful drain on SIGTERM) is owned by the app.
    queue = runtime.build_queue() if _on("CORTEX_ASYNC") else None

    app = create_app(runtime, gate=gate, queue=queue)
    uvicorn.run(app, host=os.environ.get("CORTEX_HOST", "127.0.0.1"),
                port=int(os.environ.get("CORTEX_PORT", "8000")))


if __name__ == "__main__":
    main()
