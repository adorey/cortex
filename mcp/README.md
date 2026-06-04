# Cortex MCP servers

Host-side **MCP tool servers** that a Cortex agent can use at runtime (e.g. posting to an issue
tracker). They are deliberately **decoupled from `cortex-runtime`** — they import nothing from it;
the runtime simply consumes them like any MCP server (declare them in the project's `.mcp.json`
and bind an `ActionKind` to their tools via `CORTEX_MCP_CONFIG`).

| Server | Purpose |
|---|---|
| [`cortex_jsm_mcp.py`](cortex_jsm_mcp.py) | Read a JSM issue + post a **true `public:false` internal comment** (the one thing the official Atlassian Rovo MCP does not expose) |

---

## `cortex_jsm` — read + internal comment (headless-friendly)

The official Atlassian Rovo MCP is fine interactively, but in a headless `claude -p` subprocess
it's painful: OAuth isn't completed (read-only fallback) and its `addCommentToJiraIssue` only
offers group/role visibility — **not** the JSM `public:false` internal note.

This server uses **Basic auth** (email + API token), which works headless with no OAuth, and
exposes two tools:

- `get_jira_issue(issue_key)` — read an issue (summary, status, description, recent comments)
- `add_internal_comment(issue_key, body)` — post a **true `public:false`** internal note

So an agent can run the whole support cycle through this one server — no Rovo needed.

## Install it as a named command (no raw path in `.mcp.json`)

```bash
pipx install /abs/path/to/cortex/mcp      # → the `cortex-jsm-mcp` command, on PATH
# (or, in a venv:  pip install /abs/path/to/cortex/mcp )
```

This builds the entry point declared in `pyproject.toml`, so you reference it by name — exactly
like any other server.

## Wire it to the project (`.mcp.json`)

```jsonc
{
  "mcpServers": {
    "cortex_jsm": {
      "command": "cortex-jsm-mcp",
      "env": {
        "JIRA_URL": "https://your-site.atlassian.net",
        "JIRA_EMAIL": "you@example.com",
        "JIRA_API_TOKEN": "${JIRA_BEARER_TOKEN}"
      }
    }
  }
}
```

> No `args`, no path. The server key `cortex_jsm` becomes the tool prefix `mcp__cortex_jsm__…`.
> `cortex-jsm-mcp` must be on the PATH of the process that launches the CLI (pipx puts it in
> `~/.local/bin` — run `pipx ensurepath` once if needed).

## Bind it in `CORTEX_MCP_CONFIG` (autonomy → tools)

```jsonc
{
  "mcp_bindings": {
    "issue-read":       ["mcp__cortex_jsm__get_jira_issue"],
    "internal-comment": ["mcp__cortex_jsm__add_internal_comment"]
  }
}
```

`issue-read` + `internal-comment` are granted by default (least-privilege), so the agent reads the
ticket and posts its analysis as a real internal note — fully headless. Posting internal comments
requires the account to be an **agent** on the service desk.

---

## Remote MCP servers (HTTP/SSE) — e.g. a database MCP

An MCP server doesn't have to be spawned by the runtime. If you already run one **as a local
service** (a long-lived process exposing an MCP endpoint over HTTP/SSE), declare it by **URL**
instead of a `command` — the runtime never starts it, it just connects. This suits a shared
**database MCP** (e.g. [DBHub](https://github.com/bytebase/dbhub)) that you keep running with its
own connection config.

```jsonc
{
  "mcp_servers": {
    "dbhub": {
      "type": "http",                                 // or "sse", per the server
      "url": "http://host.docker.internal:8080/mcp"   // your local service, seen from the container
      // "headers": { "Authorization": "Bearer ${DBHUB_TOKEN}" }   // if it's protected
    }
  },
  "mcp_bindings": {
    "db-read": ["mcp__dbhub__run_query", "mcp__dbhub__list_tables", "mcp__dbhub__describe_table"]
  }
}
```

- **Agnostic by construction**: the engine only knows the abstract `db-read` capability (in
  `SAFE_DEFAULT_ACTIONS`, so a support role gets read-only DB investigation by default). It never
  learns *which* server or *which* database — that's this host-declared binding.
- **Docker → host**: from inside the container, `localhost` is the container. Reach a host service
  via `host.docker.internal` (on Linux add `extra_hosts: ["host.docker.internal:host-gateway"]`
  to the compose service). If the server is also containerised, share a network and use its name.
- **Read-only is the server's job here**: when the runtime *spawns* a DB MCP it can force a
  `--readonly` flag; when it only *connects* to your already-running one, the read-only guarantee
  lives in **your** server config / a read-only DB user (ideally an anonymised replica). Cortex's
  second belt remains: bind **only read tools** to `db-read`; any write tool would go to `db-write`
  (gated, never granted by default).
- **Secrets** (DSN / tokens) stay in the `SecretProvider` / env (`${...}`), **never** in git or the
  spec — exactly like the Jira creds above.
