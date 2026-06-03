"""Quick-start entrypoint:  python -m cortex_runtime

Serves a single-workspace runtime configured from environment variables — enough to smoke
-test the slice locally. Multi-workspace / production wiring builds a Runtime in code instead.

    CORTEX_WORKSPACE   workspace name           (default: "local")
    CORTEX_ROOT        path to the project root (default: ".")
    CORTEX_THEME       active theme             (default: none)
    CORTEX_BACKEND     demo | claude-cli | anthropic-api          (default: "demo")
    CORTEX_DATABASE_URL  postgres DSN (postgresql://…) — preferred for prod / local-iso-prod
    CORTEX_DB          sqlite path              (used only if no DATABASE_URL; default: in-memory)
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
    from .state_store import InMemoryStateStore, SqliteStateStore

    workspace = os.environ.get("CORTEX_WORKSPACE", "local")
    root = Path(os.environ.get("CORTEX_ROOT", "."))
    theme = os.environ.get("CORTEX_THEME") or None
    backend = os.environ.get("CORTEX_BACKEND", "demo")

    db_url = os.environ.get("CORTEX_DATABASE_URL")
    db = os.environ.get("CORTEX_DB")
    if db_url:
        from .state_store import PostgresStateStore
        store = PostgresStateStore(db_url)
    elif db:
        store = SqliteStateStore(db)
    else:
        store = InMemoryStateStore()

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
    )
    app = create_app(runtime)
    uvicorn.run(app, host=os.environ.get("CORTEX_HOST", "127.0.0.1"),
                port=int(os.environ.get("CORTEX_PORT", "8000")))


if __name__ == "__main__":
    main()
