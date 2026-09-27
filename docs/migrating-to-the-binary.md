# Moving to the `cortex` binary

From Cortex 1.0.0 a project no longer holds a copy of the spec. It holds a `cortex.toml` that pins its version, and `cortex sync` tells it where the spec is on the machine — see [ADR-008](adr/ADR-008-cortex-binary.md). `setup.sh` became `cortex init`, `bin/validate-overlays.sh` became `cortex validate`, and both scripts are gone. This guide covers the switch from a git submodule or a standalone clone, on Linux, macOS and Windows.

## 1. Install the binary — once per machine

```bash
curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh     # Linux, macOS
```

```powershell
irm https://raw.githubusercontent.com/adorey/cortex/main/install.ps1 | iex          # Windows
```

- **Where it goes.** The command lands in `~/.cortex/bin` (`%USERPROFILE%\.cortex\bin`). `install.ps1` adds that directory to your user `PATH`; `install.sh` prints the line to add to your shell profile.
- **Name.** It installs as `cortex-ai` when another `cortex` command comes first on your `PATH`.
- **Requirements.** It needs no Python, no Bash on Windows, and no git submodule.
- **Upgrade.** Running the script again upgrades the binary.

## 2. A single project, from a submodule

`cortex init` refuses to run while `cortex/` is a submodule, and prints the commands that remove it. It does not run them: they rewrite your git state, so you run them yourself, once, in the project's root.

```bash
git submodule deinit -f cortex
git rm cortex
rm -rf .git/modules/cortex
```

On Windows, the last one is `Remove-Item -Recurse -Force .git\modules\cortex`. The path under `.git/modules/` is the one `cortex init` prints: it reads it from the submodule itself.

Then initialise the project with the options you gave `setup.sh` — they are the same:

```bash
cortex init --tool claude --force         # or copilot (the default), cursor, agents, custom
git add cortex.toml .gitignore CLAUDE.md && git commit -m "Move to the cortex binary"
```

`--force` replaces the instructions file `setup.sh` wrote: the new one reads `cortex.local.toml` first. Without it, `cortex init` keeps an instructions file that is already there. Keep your `project-overview.md`, `project-context.md` and `agents/` overlays as they are. Overlay headers keep their `Base: cortex/agents/…`: `cortex/` is now the directory `spec` names.

## 3. A workspace, from a standalone clone

The clone of Cortex next to your services goes; the workspace root gets a `cortex.toml`.

```bash
rm -rf cortex                             # Windows: Remove-Item -Recurse -Force cortex
cortex init --workspace --tool claude --force
```

Check first that the clone holds nothing of yours. `--service NAME` scaffolds a service's own `project-overview.md` and `project-context.md` — repeatable, `core/api` for a service in a subfolder. The services you already have keep their files.

## 4. Every other developer, after a pull

```bash
cortex sync
```

That is the step after every clone, as `npm install` is. It writes `spec` in `cortex.local.toml`, which git ignores: where the spec is on *this* machine. A developer who chose a theme with `setup.sh` chooses it again. The team's theme is `theme` in `cortex.toml`; your own is `theme` in `cortex.local.toml`:

```toml
theme = "star-wars"
```

## 5. CI

Where CI ran `./cortex/bin/validate-overlays.sh --strict`, it installs the binary and syncs:

```bash
curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh
export PATH="$HOME/.cortex/bin:$PATH"
cortex sync && cortex validate --strict
```

`cortex validate` has the same checks, the same report and the same exit codes as the script. When it cannot run — no `cortex.toml`, a project not synced — it exits `2`.

## 6. The runtime

A project with a `cortex.toml` gives the runtime its base through the store. Set `CORTEX_STORE_PATH` in `deploy/.env` to your store (usually `~/.cortex`, written as an absolute path); compose mounts it read-only. A project without `cortex.toml` needs nothing. See the [deploy README](../deploy/README.md).

## 7. Which mode your tool needs

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
