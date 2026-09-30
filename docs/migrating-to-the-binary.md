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

`cortex init` refuses to run while `cortex/` is a submodule, and prints the commands that remove it. It does not run them: they rewrite your git state, so you run them yourself, once. In the project's root, they are:

```bash
git submodule deinit -f cortex
git rm cortex
git rm -f .gitmodules          # when cortex was the project's only submodule
rm -rf .git/modules/cortex
```

`git rm cortex` removes the submodule's section from `.gitmodules` and leaves the file, tracked: `cortex init` adds `git rm -f .gitmodules` when that section was the last one, so no empty `.gitmodules` is committed. On Windows, the last command is `Remove-Item -Recurse -Force .git\modules\cortex`. The commands `cortex init` prints name the project by its absolute path, so they run from any directory, and the path under `.git/modules/` is read from the submodule itself. A submodule whose repository is in its own `cortex/.git` directory, as older git made them, needs no removal under `.git/modules/`.

Then initialise the project with the options you gave `setup.sh` — they are the same:

```bash
cortex init --tool claude --force         # or copilot (the default), cursor, agents, custom
git add cortex.toml .gitignore CLAUDE.md  # CLAUDE.md, or your tool's file — see below
git commit -m "Move to the cortex binary"
```

`--force` replaces the instructions file `setup.sh` wrote: the new one reads `cortex.local.toml` first. **It keeps the old one beside it, as `FILE.bak`** — `CLAUDE.md.bak` here. Carry over what you added to it by hand — a table of services, sections of your own — then delete the `.bak`. Without `--force`, `cortex init` keeps an instructions file that is already there.

The instructions file is the tool's: `.github/copilot-instructions.md` for Copilot, `.cursor/rules/cortex.mdc` for Cursor, `CLAUDE.md` for Claude Code, `AGENTS.md` for `--tool agents`, the path you give with `--tool custom`. Keep your `project-overview.md`, `project-context.md` and `agents/` overlays as they are. Overlay headers keep their `Base: cortex/agents/…`: `cortex/` is now the directory `spec` names.

## 3. A workspace, from a standalone clone

The clone of Cortex next to your services goes; the workspace root gets a `cortex.toml`.

```bash
rm -rf cortex                             # Windows: Remove-Item -Recurse -Force cortex
cortex init --workspace --tool claude --force
```

Check first that the clone holds nothing of yours. `--service NAME` scaffolds a service's own `project-overview.md` and `project-context.md` — repeatable, `core/api` for a service in a subfolder. The services you already have keep their files. As in a single project, `--force` keeps the instructions file it replaces as `FILE.bak`: where the workspace root is no git repository, that `.bak` is the only copy of what you wrote in it.

**A workspace root that is no git repository** — a directory holding the services' repositories — has nowhere to commit `cortex.toml`, and `cortex init` says so. Each developer then runs `cortex init --workspace` in their own root: it pins the version of their own `cortex`, and their own theme and sync mode. A team-wide pin for that layout is left to a later decision (ADR-008 §9).

## 4. Every other developer, after a pull

```bash
cortex sync
```

That is the step after every clone, as `npm install` is. It writes `spec` in `cortex.local.toml`, which git ignores: where the spec is on *this* machine. A developer who chose a theme with `setup.sh` chooses it again. The team's theme is `theme` in `cortex.toml`; your own is `theme` in `cortex.local.toml`:

```toml
theme = "star-wars"
```

**A clone that had the submodule initialised.** The pull that removes the submodule leaves `cortex/` behind: git no longer tracks it, and keeps its files, the submodule's repository under `.git/modules/` and its settings in `.git/config` — the pull warns *unable to rmdir 'cortex'*. `cortex sync` then refuses, and prints what is left to remove. Check first that `cortex/` holds nothing of yours — what changed in it, ignored files included, and the commits nobody pushed — then run what it printed:

```bash
git -C cortex status --short --ignored       # these two print nothing? Then:
git -C cortex log --oneline HEAD --not --remotes
git config --remove-section submodule.cortex
rm -rf cortex .git/modules/cortex
cortex sync
```

If you already ran the commands 1.0.0 or 1.1.0 printed, their last one removed `.git/modules/cortex`: git can no longer show what changed in `cortex/`, and `cortex sync` says so. Look through it yourself before you remove it.

Before the pull, `git submodule deinit -f cortex` and `rm -rf .git/modules/cortex` are enough: the pull then removes the empty `cortex/`, and `cortex sync` passes the first time.

## 5. CI

Where CI ran `./cortex/bin/validate-overlays.sh --strict`, it installs the binary of the version `cortex.toml` pins, and syncs:

```bash
version="$(LC_ALL=C tr -d '\357\273\277' < cortex.toml | sed -n "s/^[[:space:]]*version[[:space:]]*=[[:space:]]*[\"']\([^\"']*\)[\"'].*/\\1/p" | head -n 1)"
[ -n "$version" ] || { echo "cortex.toml pins no version" >&2; exit 1; }
curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh -s -- "$version"
export PATH="$HOME/.cortex/bin:$PATH"
cortex sync && cortex validate --strict
```

On a Windows runner, in PowerShell:

```powershell
$pinned = Select-String -Path cortex.toml -Pattern '^\s*version\s*=\s*["'']([^"'']+)["'']' | Select-Object -First 1
if (-not $pinned) { throw "cortex.toml pins no version" }
$version = $pinned.Matches[0].Groups[1].Value
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/adorey/cortex/main/install.ps1))) -Version $version
$env:Path = "$env:USERPROFILE\.cortex\bin;$env:Path"
cortex sync; if ($LASTEXITCODE) { exit $LASTEXITCODE }
cortex validate --strict; if ($LASTEXITCODE) { exit $LASTEXITCODE }
```

`cortex validate` has the same checks, the same report and the same exit codes as the script. When it cannot run — no `cortex.toml`, a project not synced — it exits `2`. The binary checks with its own rules: a later release may warn where the pinned one did not, and `--strict` fails on a warning. Pinned, CI checks the project with the rules of the version it uses, and a bump of `version` is the change that brings the new ones (ADR-008 §9).

## 6. The runtime

A project with a `cortex.toml` gives the runtime its base through the store. Run `cortex sync` in the project, then set `CORTEX_STORE_PATH` in `deploy/.env` to your store (usually `~/.cortex`, written as an absolute path); compose mounts its `versions/`, read-only, and nothing else of it. A project without `cortex.toml` needs nothing. See the [deploy README](../deploy/README.md).

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

- **Claude Code.** Keep the default `store` mode, and let `cortex sync` allow the store. It needs one of these:
  - `claude_access = true` in `cortex.toml`, for the whole team. `cortex init --tool claude` asks for it on a terminal, and `--claude-access` sets it unattended.
  - `cortex sync --claude-access`, for you alone: it writes `claude_access = true` in `cortex.local.toml`.

  `cortex sync` then keeps the store's path of the pinned version in `.claude/settings.local.json`, under `permissions.additionalDirectories`. That file holds Claude Code's settings for you on this machine, which git ignores. Sync replaces the path when the version changes, and removes it when access is turned off — the path it wrote, which `cortex.local.toml` records as `claude_entry`, and no other: an entry you added yourself, by hand or through Claude Code's own prompt, stays yours. While neither file sets `claude_access`, sync does not touch the file. `claude_entry` is how sync knows its own entry: if `cortex.local.toml` goes — a `git clean -X` removes it — the entry stays in `.claude/settings.local.json` as if you had written it, and is yours to remove; edit `claude_entry`, and the next sync takes the path you wrote for its own: it removes that entry at once, and the store's entry, already there, then passes for yours. Leave `claude_entry` to sync. Measured with Claude Code 2.1.273: the Prompt Manager's card is reached with no prompt at all.

  Without it, you answer the permission prompt once per session. `sync = "copy"` needs no setting either.
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

The run's `permission_denials` names every read that would have prompted. `--setting-sources project` leaves out your own settings, so that nothing you allowed before counts. To measure `claude_access`, add the settings `cortex sync` writes: `--setting-sources project,local`, since `.claude/settings.local.json` is Claude Code's *local* source.
