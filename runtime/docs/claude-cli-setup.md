# Configuring the `claude-cli` backend (Pro/Max subscription)

Use your **Claude Pro/Max subscription** to run the agent locally — no per-token API billing.
This drives the **Claude Code CLI** as a subprocess (the only supported subscription path; the
Agent SDK library cannot use a subscription).

> For local development/testing only. The subscription quota is interactive-oriented — a
> deployed 24/7 service should use the `anthropic-api` backend (a Console key) instead.

## Step 1 — Install the Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
claude --version        # verify it's on PATH
```

## Step 2 — Authenticate with your subscription (one-time)

```bash
claude setup-token
```

This opens a browser OAuth flow against your Pro/Max account and prints a **~1-year token**.
Copy it.

## Step 3 — Set the environment

```bash
export CLAUDE_CODE_OAUTH_TOKEN="<the token from step 2>"
unset ANTHROPIC_API_KEY          # IMPORTANT: if set, it overrides the subscription token
export DISABLE_TELEMETRY=1        # optional, for a service
```

> Put these in your shell profile or a local env file you source — **not** in git.

## Step 4 — Install the runtime

```bash
cd runtime
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[serve]"        # if venv fails: sudo apt install python3-venv
```

## Step 5 — Run the service against your project

```bash
CORTEX_WORKSPACE=acme \
CORTEX_ROOT=/path/to/your/project \
CORTEX_THEME=h2g2 \
CORTEX_BACKEND=claude-cli \
CORTEX_DB=cortex-runtime.db \
python -m cortex_runtime           # serves on http://127.0.0.1:8000
```

## Step 6 — Fire a run

```bash
curl -X POST localhost:8000/run -H 'content-type: application/json' -d '{
  "workspace": "acme",
  "role": "support-engineer",
  "subject": "ACME-7",
  "input": {"issue": "ACME-7", "summary": "describe the ticket here"}
}'
```

The response carries the run `state`, the agent's `final_text` (its diagnosis), and the
persisted run/audit. A second call on the same `subject` while `awaiting-human` is **skipped**
(durable anti-recursion).

## How autonomy maps to CLI tools

Per-request `autonomy` (action kinds) becomes the CLI's `--allowedTools` — this is how gating
is enforced in this backend (the CLI owns the loop + its own tools):

| Autonomy action | CLI tools allowed |
|---|---|
| `code-read` (default) | `Read,Grep,Glob` |
| `code-write` | `Edit,Write` |
| `db-*`, `git-*`, `issue-*` | *(no built-in CLI tool — MCP servers, later)* |

Default = read-only (`code-read`). Grant more per request:
`"autonomy": ["code-read", "code-write"]`.

## MCP tools (e.g. posting to the issue tracker)

To let the agent act on real tools (post an internal Jira comment, read a ticket…), declare an
MCP server for the CLI and bind your agnostic actions to its concrete tool names. Put this in a
JSON file and point `CORTEX_MCP_CONFIG` at it:

```jsonc
{
  "mcp_servers": {
    "jira": { "command": "<your-jira-mcp-server>", "args": ["..."], "env": { "JIRA_TOKEN": "..." } }
  },
  "mcp_bindings": {
    "internal-comment": ["mcp__jira__add_internal_comment"],
    "issue-read":       ["mcp__jira__get_issue"]
  }
}
```

```bash
CORTEX_MCP_CONFIG=./mcp.json  CORTEX_BACKEND=claude-cli  ...  python -m cortex_runtime
```

- `mcp_servers` is forwarded to the CLI via `--mcp-config` (Claude Code's native MCP support).
- `mcp_bindings` maps an **ActionKind** to the **real MCP tool name(s)** it unlocks, so granting
  `internal-comment` (on by default) lets the agent call your Jira comment tool — and it shows up,
  gated-aware, in the audit. Replace the server config and tool names with your actual Jira MCP server.

> A ready-made, headless-friendly Jira server (read + true `public:false` internal comment) lives
> in [`../../mcp/`](../../mcp/) — see its README for the exact `.mcp.json` + bindings.

## Troubleshooting

- **`'claude' CLI not found`** → Step 1 didn't put it on PATH (check `which claude`).
- **Auth/credit errors** → confirm `CLAUDE_CODE_OAUTH_TOKEN` is set and `ANTHROPIC_API_KEY` is
  unset in the same shell.
- **The run aborts when the model wants a tool** → that tool isn't in `--allowedTools`. Widen
  the request's `autonomy`, or (if your CLI version prompts in `-p` mode) pass a permission mode
  — set it on `ClaudeCodeCliClient(permission_mode=...)` (values vary by CLI version; check
  `claude --help`).
- **Want to see cost** → the client captures `last_usage` (tokens + `total_cost_usd`) from the
  CLI's JSON output; surfacing it per run into the StateStore is a planned follow-up.
