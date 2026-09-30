# Moving to the `cortex` binary

From Cortex 1.0.0 a project no longer holds a copy of the spec: it holds a `cortex.toml` that pins its version, and `cortex sync` tells it where the spec is on the machine — see [ADR-008](adr/ADR-008-cortex-binary.md). This guide covers the switch from a git submodule or a standalone clone.

## Which mode your tool needs

The bootstrap file sends the tool's LLM to `cortex/agents/…`. From 1.0.0 it gives one rule first: *`cortex/` is the directory `spec` names in `cortex.local.toml`*. How that directory reaches the tool depends on the mode `cortex sync` runs in:

| Mode | In the project | `spec` |
|---|---|---|
| `store` (default) | nothing | the store's path, `~/.cortex/versions/X.Y.Z` |
| `link` | `cortex/`, a link to the store — a junction on Windows | `cortex` |
| `copy` | `cortex/`, a read-only copy | `cortex` |

Whether a tool reads the spec in each mode is measured, not assumed. Each measurement is a real conversation in a throwaway project initialised for that mode. It must reach the Prompt Manager's card, `cortex/agents/roles/prompt-manager.md`. The table also says whether the tool asked for a permission on the way:

| Tool | Version | `store` | `link` | `copy` |
|---|---|---|---|---|
| Claude Code | 2.1.273 | **Reached**, after asking for permission. It reads outside the project only with permission, once per session. It reads with no prompt when the store is in `permissions.additionalDirectories` | **Reached**, after asking for permission. Claude Code checks the path a link resolves to, and that path is outside the project | **Reached**, no permission asked |
| GitHub Copilot | — | not measured yet | not measured yet | not measured yet |
| Cursor | — | not measured yet | not measured yet | not measured yet |
| Codex | — | not measured yet | not measured yet | not measured yet |

What it means today:

- **Claude Code.** Keep the default `store` mode, and allow the store once. You can answer the first prompt of a session. Or you can add it to your *user* settings, `~/.claude/settings.json`, which then covers every project:

  ```json
  { "permissions": { "additionalDirectories": ["~/.cortex/versions"] } }
  ```

  Use `sync = "copy"` in `cortex.toml` when a team wants no prompt and no setting.
- **The tools not measured yet** start in `store`. Switch the project to `link`, then to `copy`, if a conversation does not reach the Prompt Manager's card.

### How a measurement is made

Record the tool's version with the result: the answer changes with releases.

1. In an empty directory, write a `cortex.toml` — `version` and `theme = "h2g2"` — and the tool's bootstrap file from `templates/bootstrap-instructions.md`. Then run `cortex sync --store`, `--link` or `--copy`.
2. Open a **new** conversation in the tool, in its default permission mode, and ask: *"Follow your bootstrap first. Then tell me who you are, and the first heading of the file that defines your working protocol."*
3. **Reached** means the answer names the Prompt Manager's character and quotes the heading of `prompt-manager.md`. Note whether the tool asked for a permission, and for which path.

For Claude Code the measurement above ran in print mode, where a prompt is answered "no" and listed:

```bash
claude -p "…" --setting-sources project --tools Read,Glob,Grep --permission-prompts none \
       --output-format stream-json --verbose
```

The run's `permission_denials` names every read that would have prompted.
