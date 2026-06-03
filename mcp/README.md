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
