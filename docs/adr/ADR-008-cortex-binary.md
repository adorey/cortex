# ADR-008 — The `cortex` binary: one-line install, one store per machine, `cortex.toml` per project

- **Status:** Proposed
- **Date:** 2026-09-27 (proposed)
- **Authors:** Cortex maintainers (initiated by the maintainer, drafted by @Oolon)
- **Affects:** a new `cli/` package (`cortex_cli`), the release pipeline, new `install.sh` and `install.ps1`, the runtime's base binding (`runtime/cortex_runtime`, `deploy/compose.yaml`), `setup.sh` and `bin/validate-overlays.sh` (removed in phase 5), `templates/bootstrap-instructions*.md`, `docs/`, `README.md`, `CONTRIBUTING.md`, CI
- **Relates to:** [ADR-007](ADR-007-cortex-core.md) — the core this binary embeds, `base_root`, and the promises of its §7 · [ADR-001](ADR-001-layered-overrides.md) — the cascade, untouched · [ADR-002](ADR-002-cortex-runtime.md) §3.4 — the runtime's `root` binding, extended with the base's location · [ADR-006](ADR-006-workspace-shareable-repo.md) — the tiers `cortex init` scaffolds · roadmap epic [#37](https://github.com/adorey/cortex/issues/37)

---

## 1. Context

A host project gets Cortex today in two steps, and keeps it with a third:

1. **The spec arrives by git** — `git submodule add https://github.com/adorey/cortex cortex`, or a standalone clone in a workspace. The project pins a version by the submodule's commit.
2. **`./cortex/setup.sh`** writes the bootstrap instructions for the AI tool (`--tool copilot|cursor|claude|agents|custom`), the active-theme marker, the `project-overview.md` and `project-context.md` templates and, with `--workspace`, one pair per service and the team tier of ADR-006.
3. **`./cortex/bin/validate-overlays.sh`** checks the overlays — since ADR-007, a shim that needs **Python 3.9 or later** on the host.

Nothing in that sequence is an installation: the tooling is whatever the checked-out copy of the spec happens to contain, run from inside it. Every project carries its own copy of the spec; a developer needs git submodules to work, Bash for the setup — so no native Windows — and a Python for the validator. The maintainer's goal is the opposite: **one command installs Cortex on a machine — Linux, macOS or Windows — the spec lives once on that machine, and any number of projects activate it, each at its own version.**

Four constraints shape how:

- **The LLM of the IDE reads the spec as files, at `cortex/agents/…`.** The bootstrap templates send it there, and on to `cortex/docs/extending-layers.md`; the Prompt Manager's card points at `cortex/templates/workflow.md.template`. Most tools can read a file outside the workspace when told where it is; **not all of them will**, by policy or by configuration, and some models follow an indirection less reliably than a literal path. Reading the spec where it lives must be the default, and bringing it into the project a fallback.
- **The runtime resolves the base at `{project}/cortex`** (ADR-007's default `base_root`), and in its container sees only the mounted project. It will soon run other models than Claude — local ones among them, behind a provider abstraction (ADR-011, [#40](https://github.com/adorey/cortex/issues/40)) — and assembles their prompts itself: whatever this ADR decides must not depend on what an IDE tool agrees to read.
- **A shared spec must not be edited through one project.** Today a developer, or an agent, who edits `cortex/agents/…` edits that project's submodule only. With one store per machine, the same edit would change every project using that version.
- **Nobody outside the maintainer's team consumes Cortex yet.** The switch can be clean — no dual mode, no deprecation window.

ADR-007 left this ADR three promises: point `base_root` at an installed copy, ship a native binary that removes the Python prerequisite, and introduce the `cortex` command its internal module entry point is not.

## 2. Decision

**Cortex is distributed as a native `cortex` binary, installed by one command on Linux, macOS and Windows. The spec lives once per machine, in a store under `~/.cortex`, one read-only directory per version. A project activates Cortex with a committed `cortex.toml` that pins its version; `cortex sync` puts that version in the store and tells the project where it is. The spec is read in place: nothing of it enters the project, unless a tool needs it there — then `cortex sync --link` or `--copy` brings it in as `cortex/`.** The binary reaches **feature parity with what exists** — `setup.sh` becomes `cortex init`, `validate-overlays.sh` becomes `cortex validate` — and both scripts are then removed.

The store belongs here and not in a later ADR: it decides what a host project contains of Cortex. Deferring it would mean migrating every project twice.

It is otherwise **no more than parity**. The organisation-wide configuration cascade, the rendering of resolved prompts for the IDE, a lock file, upgrade tooling, and the CLI driving the runtime are later decisions (§7). There is **no PyPI distribution**: nothing consumes Cortex as a Python library.

## 3. Detailed contract

### 3.1 The binary

- Built with **PyInstaller** from `cortex_core` and a new `cortex_cli` package, both standard library only. It embeds the interpreter: the host needs **no Python**.
- **Targets:** Linux `x86_64` and `aarch64` (glibc 2.28 or later — built in a `manylinux_2_28` image), macOS `arm64`, Windows `x86_64`. Intel macOS and Windows on ARM are not built.
- **Named `cortex`** (`cortex.exe` on Windows), with **`cortex-ai`** as its fallback name. Other projects already ship a `cortex` command — the Cortex Labs CLI, the Prometheus-compatible Cortex server — so a machine may have one. The binary behaves the same under either name; nothing reads the name it was called by.
- **Its version is the release's**, stamped at build time from the tag — `cortex --version` prints it. `CHANGELOG.md` stays the single source of truth for versions.
- **The same output on every platform.** Paths are printed with `/`, the output is UTF-8 whatever the console's code page, and a file with CRLF line endings — what git produces on Windows with `core.autocrlf` — reads the same as with LF.
- Built and published by CI **from the tag**, as assets of the GitHub Release: one archive per target, the spec archive of §3.3, and a `SHA256SUMS` file. Each asset carries a GitHub **build-provenance attestation**, so `gh attestation verify` can tie it to the workflow run that built it.
- The Windows executable is **not code-signed** in this ADR. SmartScreen and antivirus heuristics may warn on an unsigned PyInstaller executable; signing is a follow-up (§7), taken when that friction is measured.

### 3.2 The one-line install

```bash
curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh                    # Linux, macOS
curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh -s -- 1.0.0       # a given version
```

```powershell
irm https://raw.githubusercontent.com/adorey/cortex/main/install.ps1 | iex                          # Windows
```

Both scripts detect the platform, download the matching asset of the release (the latest, or the version given), **verify it against `SHA256SUMS` and stop on a mismatch**, and install `cortex` into `~/.cortex/bin` (`%USERPROFILE%\.cortex\bin`). Neither asks for administrator rights. When another `cortex` command comes first on `PATH`, both scripts say which one, and install as `cortex-ai` instead — `--name cortex` forces the first name anyway. `install.ps1` adds the directory to the user's `PATH`; `install.sh` prints the line to add to the shell profile, and edits no file on its own. Running a script again replaces the binary: that is the upgrade.

### 3.3 The store — `~/.cortex`

```text
~/.cortex/                 $CORTEX_HOME overrides the location
├── bin/cortex             the binary (§3.2)
└── versions/
    ├── 1.0.0/             one release's spec: agents/, templates/, docs/ — read-only
    └── 1.1.0/
```

- A version directory holds the three trees the IDE's LLM and the runtime read — `agents/`, `templates/`, `docs/` — and nothing else.
- **Filled on demand.** The binary embeds the spec of its own version and writes it without a network. Any other version is downloaded once, from that release's spec archive, **verified against its `SHA256SUMS`**, then kept.
- **Read-only once written** — the write permission removed on POSIX, the read-only attribute set on Windows. An edit of the spec — by a developer or an agent, in place or through a project's link — fails loudly instead of silently changing every project on that version. A developer who wants to change the spec writes an overlay, as today.
- **Which versions a binary serves:** any released version from **1.0.0** — the release that ships this ADR, the first published as a spec archive — up to its own. A project pinned to a newer version than the binary is refused, with the command that upgrades the binary. The tool is newer than the data it reads, never older.
- **Nothing in the store is per project, and nothing lists the projects.** A project is a directory with a `cortex.toml`; adding one is `cortex init` in it, or `cortex sync` in a clone of one. Any number of projects share the store, each at its own version. A machine-wide list of projects is the project registry's decision, not this one. Pruning versions no project uses is a follow-up (§7) — a version is under a megabyte.
- **Works offline** for the binary's own version, embedded; a machine with no network — a local model's usual setting — installs one binary and uses that version.
- **`~/.cortex/config.toml` is reserved** for the machine tier of the configuration cascade (§7) — where a local model's endpoint will be configured. This ADR writes nothing there.

### 3.4 `cortex.toml` and `cortex.local.toml`

`cortex.toml` is committed at the project root — where the bootstrap file's paths start from, the workspace root in workspace mode:

```toml
# Written by `cortex init`. Committed.
version = "1.0.0"    # the Cortex release this project uses
theme = "h2g2"       # the team's default theme — "none" for no personality
sync = "store"       # optional — "link" or "copy" when the team's tool needs the spec in the project (§3.5)
```

`cortex.local.toml`, next to it, is **ignored by git** — this developer, on this machine:

```toml
theme = "star-wars"                               # optional — overrides cortex.toml's theme
spec = "/home/dev/.cortex/versions/1.0.0"         # written by `cortex sync` — where the spec is
```

`version` and `theme` are required in `cortex.toml`; `cortex.local.toml` accepts only `theme` and `spec`. **An unknown key is an error**, not a warning: these files are the ones a later ADR extends, and a typo that silently does nothing is the failure they must not start with.

The active-theme marker **leaves the spec**: it lived inside `cortex/agents/personalities/`, which is now a shared, read-only store. The bootstrap templates read the theme from `cortex.local.toml`, then `cortex.toml` — the same per-developer choice as today, with a team default a fresh clone did not have.

### 3.5 `cortex sync` — where the project finds the spec

`cortex sync`:

1. finds `cortex.toml` in the current directory or the nearest ancestor, and validates both files;
2. makes sure the pinned version is in the store (§3.3);
3. writes `spec` in `cortex.local.toml`, creating the file if needed and keeping its `theme`.

**`cortex/` becomes a name, not a directory.** The spec's own text says `cortex/agents/…`, `cortex/templates/…`, `cortex/docs/…`, and every overlay's `Base:` header says `cortex/agents/…` — already a logical identifier since ADR-007 §3.4. The bootstrap templates give the rule once: *`cortex/` is the directory `spec` names*. Nothing else in the spec or in the overlays is edited.

Three modes, chosen by `--store`, `--link` or `--copy`, or by `cortex.toml`'s `sync`, `store` by default:

| Mode | In the project | `spec` | For |
|---|---|---|---|
| `store` | nothing | the store's absolute path | every tool that reads a file outside the workspace when told where it is |
| `link` | `cortex/` → the store: a **symbolic link** on Linux and macOS, a **directory junction** on Windows, which needs no administrator right and no developer mode | `cortex` | a tool that reads only inside the workspace, or a model that follows a literal path better than an indirection |
| `copy` | `cortex/`, a read-only copy with a `.synced` marker naming the version | `cortex` | a file system without links, or a tool that does not read through one |

`sync` is a team setting because the tool is: the bootstrap file `cortex init` writes is committed. A flag overrides it for one run on one machine. In `link` and `copy` modes, `cortex init` adds `cortex/` to `.gitignore`. In every mode, sync **refuses when `cortex/` exists and is neither a link nor a copy it made** — a submodule, a clone, any other directory: it would contradict the rule the templates give, and sync never deletes something it did not write. Switching back to `store` removes the link or copy it made, and nothing else.

`cortex sync --from PATH` points `spec` at a checkout of this repository instead of the store, with no version check and a warning saying so. It is how a contributor tests an unreleased spec in a throwaway host project — CONTRIBUTING's test loop.

After a clone, a developer runs `cortex sync` — as they would `npm install`. The bootstrap templates say so: when `cortex.local.toml` or its `spec` is missing, the LLM tells the user to run it rather than working without its instructions.

### 3.6 The runtime finds the base through `cortex.toml`

`spec` is a path of the host, and a project's link points at one: the runtime's container sees neither. So the runtime takes the base from `cortex.toml` when the project has one — `base_root = {CORTEX_HOME}/versions/{version}`, ADR-007's parameter — and falls back to `{root}/cortex` otherwise. `deploy/compose.yaml` mounts the store read-only next to the project and sets `CORTEX_HOME` inside the container. A run against a version missing from the store is refused (`422`) with the version named. Which model the runtime then calls — Claude, or a local one once ADR-011 lands — changes nothing here: the runtime reads the store itself, whatever an IDE tool may read. This amends ADR-002 §3.4: the binding still names one project root, and now also where that project's base is.

### 3.7 `cortex init` — `setup.sh`, at parity

```text
cortex init [DIR] [--theme THEME | --no-personality] [--workspace] [--service NAME ...]
            [--tool copilot|cursor|claude|agents|custom] [--instructions-file PATH]
            [--link | --copy] [--force]
```

Same options, same defaults (`--theme h2g2`, `--tool copilot`), same files at the same paths as `setup.sh`: the instructions file of the tool, the root `project-overview.md` and `project-context.md` when missing, and in workspace mode a pair per service with its `@alias` — the basename of the service's folder — plus the team tier when `agents/` is its own git working tree. It writes `cortex.toml` at the binary's own version, adds `cortex.local.toml` to `.gitignore`, then runs `cortex sync`. `--link` and `--copy` are accepted and written as `cortex.toml`'s `sync`.

Two deliberate differences:

- **Services are named by `--service`**, repeatable. The interactive prompt remains, only when stdin is a terminal and no `--service` was given.
- **An existing instructions file is kept unless `--force`**, instead of a `y/N` prompt that blocks every unattended run.

### 3.8 `cortex validate` — `validate-overlays.sh`, at parity

`cortex validate [--service PATH] [--strict]` runs ADR-007's validator against the spec `spec` names — the pinned version, or a checkout given by `--from`: same checks, same report, same exit codes (`0` clean, `1` errors or warnings under `--strict`, `2` bad arguments). The frozen golden outputs of ADR-007 are replayed against the binary on every target.

### 3.9 Packages

```text
core/  cortex_core   the cascade — a library, imported by the CLI and the runtime
cli/   cortex_cli    the `cortex` command — argument parsing, the store, sync, init
```

`cortex_core` imports neither `cortex_cli` nor `cortex_runtime`, and a test enforces it, as ADR-007 already does for the runtime. The CLI is a package of its own because it will grow away from the core: driving the runtime over HTTP (§7) is client code, not cascade code.

### 3.10 Leaving the submodule

`cortex init` or `cortex sync` in a project whose `cortex/` is a submodule or a clone **refuses** (§3.5) — in every mode, since the old directory would shadow the rule the templates give — and prints the git commands that remove it — `git submodule deinit -f cortex`, `git rm cortex`, `rm -rf .git/modules/cortex` — without running them: they rewrite the project's git state, and the developer should see them first. A migration guide in `docs/` covers the single-project and workspace layouts, on each platform.

## 4. Phases

Execution order: **1 → 2 → 3 → 4 → 5**. All five gate the ADR's release: parity is the point, and the scripts are removed only once it is reached.

### Phase 1 — The binary, installable, that validates

Create `cli/` with `cortex --version` and `cortex validate`, the latter reading the base from an explicit path for now. Build the binary for the four targets in CI, attach it to a release with `SHA256SUMS` and attestations, and ship `install.sh` and `install.ps1`.

Acceptance criteria:

- on each target, the ADR-007 golden fixtures replayed through the **built binary** match byte for byte, on a runner with no Python on `PATH` — Windows included, paths printed with `/`
- the same overlays checked out with CRLF line endings produce the same report
- each install script installs a release asset into an empty `$CORTEX_HOME`, and stops with a non-zero exit when one byte of the asset is altered
- with another `cortex` first on `PATH`, each install script names it and installs `cortex-ai`; `--name cortex` installs `cortex`
- `cortex --version` prints the version of the tag it was built from
- a test fails when a `cortex_core` module imports `cortex_cli`

### Phase 2 — The store and `cortex sync`

The spec archive in the release, the store, `cortex.toml` and `cortex.local.toml`, the three modes and `--from`; the bootstrap templates' rule for `cortex/`.

Acceptance criteria:

- two projects pinned to two different versions sync on one machine and each `spec` names its own version; a third project on one of those versions downloads nothing
- in `store` mode, sync writes nothing in the project but `cortex.local.toml`
- a downloaded spec whose checksum differs is refused and leaves nothing in the store
- writing a file of the store fails, in place and through a link, on every target
- sync refuses, and deletes nothing, when `cortex/` is a submodule, a clone or any directory it did not write; switching a project from `link` or `copy` back to `store` removes only what sync made
- a project pinned to a version newer than the binary is refused with the upgrade command
- on Windows, the junction is created by a user without administrator rights or developer mode
- `cortex.toml` with an unknown key, or without `version` or `theme`, is refused and the key named; so is any key but `theme` and `spec` in `cortex.local.toml`
- for Copilot, Cursor, Claude Code and Codex, which mode works — the spec read in place, through the link, or only copied — is measured on a real conversation that must reach a role card, and written in the migration guide, with whether the tool asked for permission

### Phase 3 — The runtime finds the base through `cortex.toml`

Acceptance criteria:

- the runtime, in its container, resolves a synced project with the store mounted as `deploy/compose.yaml` describes, and a project without `cortex.toml` exactly as before
- a run on a project pinned to a version missing from the store is refused with `422`, the version named
- ADR-002 carries the amendment of §3.6

### Phase 4 — `cortex init`, at parity with `setup.sh`

Acceptance criteria:

- across a parity matrix — single and workspace mode, each of the five `--tool` values, `--no-personality` and a non-default `--theme`, a service in a subfolder, a git-backed `agents/` — `cortex init` produces the same files, byte for byte, as `setup.sh`, plus `cortex.toml`, `cortex.local.toml` and its `.gitignore` line. The repo-checks scaffold job exercises only `--tool claude` today: the matrix is written for this phase, and runs against `setup.sh` until phase 5 deletes it
- `cortex init --workspace --service api --service core/web` runs unattended with stdin closed, on every target
- an existing instructions file is untouched without `--force`, replaced with it
- `cortex init` in a project whose `cortex/` is a submodule refuses and prints the three git commands

### Phase 5 — The switch

Point the templates — the rule for `cortex/`, the theme read from `cortex.local.toml` then `cortex.toml` — `docs/`, `README.md` and `CONTRIBUTING.md` at the binary; write the migration guide; delete `setup.sh` and `bin/validate-overlays.sh`; move this repository's CI to the binary.

Acceptance criteria:

- `git grep -n 'setup.sh\|validate-overlays.sh\|\.active-theme'` finds only the changelog, the ADRs and the migration guide
- the bootstrap templates tell the LLM what to do when `cortex.local.toml` or its `spec` is missing
- the repo-checks scaffold job builds a host project with the install script, `cortex init` and `cortex validate --strict` only, on Linux and on Windows
- this repository still validates itself — the base as its own project, ADR-007 §3.1

## 5. Consequences

### Positive

- **One command installs Cortex**, on Linux, macOS and Windows, with no git submodule, no Bash, no Python on the host.
- **The spec lives once per machine**, and any number of projects use it, each at its own version — what submodules allowed, without a copy per project. By default a project holds **nothing** of Cortex but `cortex.toml`, its bootstrap file and its own overlays.
- **The shared spec cannot be edited by accident**, through any project.
- **ADR-007's Python prerequisite is gone** for host projects.
- The spec's paths and every overlay header are untouched: `cortex/` keeps its meaning, as a name.
- **The runtime's side does not depend on the IDE's**: it reads the store itself, for whichever model it calls — local ones included, once ADR-011 lands.
- Everything downloaded — binary and spec — is checked before use, and can be traced to the workflow that built it.

### Negative

- **A step after every clone**: `cortex sync`, which writes the machine's `spec`. CI needs the binary too — it already needed the validator.
- **One indirection for the LLM**: it reads `cortex.local.toml` before the spec. A tool or a model that does not follow it needs `--link`; one that does not read through a link needs `--copy`. Phase 2 measures which tools those are — none of this is known yet.
- **The runtime changes**, a little: it reads `cortex.toml`, and its container mounts the store.
- **A build matrix to maintain** — four targets, a glibc floor, a Windows runner — and a binary of roughly 10 to 15 MB where a script was a few kilobytes. An unsigned Windows executable may be flagged until it is signed.
- **The active-theme marker moves**, from inside the spec to `cortex.local.toml`: a developer who chose a theme chooses it again once.
- **Breaking, by CONTRIBUTING's own versioning table**, which makes a change to the `setup.sh` CLI a major: the release that ships this ADR is **1.0.0**. It is also the first binary, and the first spec archive.

### Neutral

- `cortex_core` stays runnable from source with Python 3.9: the runtime and the tests still use it that way.
- A pinned version is still a commit-level pin in spirit — a released version — but no longer an arbitrary commit: a project can no longer track an unreleased branch of Cortex. Contributors testing an unreleased spec use `cortex sync --from` (§3.5), or work in this repository.

## 6. Alternatives considered

| Alternative | Why not |
|---|---|
| **A PyPI distribution first, the binary later** (`pipx` / `uv tool install`) | A one-line install only for machines that already have `pipx` or `uv`; a channel the team adopts and then has to leave; and no Python library consumer to justify it. |
| **Rewrite the CLI in Go or Rust** | A second implementation of the cascade — the one ADR-007 just removed. |
| **One version per machine, the spec copied into each project** | The first draft of this ADR. It breaks two projects on two versions, which submodules handle, and a later store would have migrated every project a second time. |
| **The store's path written in the committed bootstrap file** | The version duplicated from `cortex.toml`, and a path that is wrong on another platform or with `$CORTEX_HOME` moved. `spec` in the ignored local file is right on every machine. |
| **A link in every project, by default** | The second draft of this ADR. It keeps the spec's paths literal, but makes links — junctions on Windows, file systems without them, the runtime's container — a dependency of every project, for tools that mostly do not need it. Kept as the fallback. |
| **Commit the copied `cortex/`** | No step after a clone, but around nine thousand lines of someone else's files in every host repository, and a diff that size on every upgrade. |
| **Keep the submodule; replace only the scripts** | The install stays two steps, still needs git submodules, and still copies the spec per project. |
| **An XDG layout** (`~/.local/share/cortex`, `%LOCALAPPDATA%`) | Three locations to document, where `~/.cortex` is one on every platform, like `~/.cargo` or `~/.rustup`. `$CORTEX_HOME` covers whoever needs another. |
| **Nuitka** | Compiles to C: faster at start-up, much slower and more fragile to build. PyInstaller is enough for a command that runs for a second; revisit if start-up time is measured to matter. |
| **PyApp or a bootstrapping launcher** | Downloads a Python on first run: not self-contained, and a network dependency at the worst moment. |

## 7. Follow-ups (out of scope for this ADR)

1. **The configuration cascade and the IDE modes** — organisation policy ▸ project ▸ project-local ▸ machine, of which `cortex.toml` and `cortex.local.toml` are the first two files; rendering the resolved prompts for the IDE, which removes the cascade the LLM follows from the templates; a mode for a Cortex extension. Formerly in this ADR's epic; needs an epic of its own.
2. **`cortex.lock` and upgrade tooling** — a resolved manifest, `cortex upgrade`, pruning unused versions from the store.
3. **Other models, local ones included** — the provider abstraction, ADR-011 ([#40](https://github.com/adorey/cortex/issues/40)). It inherits the store and the runtime's binding as they are; its endpoints go in the machine tier, `~/.cortex/config.toml`.
4. **The CLI drives the runtime** — `cortex run`, `watch`, `runtime up` over the unified client protocol, ADR-016 ([#45](https://github.com/adorey/cortex/issues/45)).
5. **More channels and platforms** — Homebrew, winget, a signed Windows executable, Intel macOS, a PyPI wheel wrapping the binary if a Python consumer appears — under `cortex-ai`, the name the command falls back to, free on PyPI on 2026-09-26 (`cortex` is taken). [#86](https://github.com/adorey/cortex/issues/86) still reserves `cortex-core` meanwhile: `runtime/pyproject.toml` depends on it by name.

## 8. References

- [ADR-007](ADR-007-cortex-core.md) — `base_root`, the golden fixtures, the self-hosting case
- [ADR-002](ADR-002-cortex-runtime.md) §3.4 — the runtime binding this ADR extends
- [`setup.sh`](../../setup.sh), [`bin/validate-overlays.sh`](../../bin/validate-overlays.sh) — the behaviour to reach
- [`deploy/compose.yaml`](../../deploy/compose.yaml) — the runtime's mounts
- [`.github/workflows/repo-checks.yml`](../../.github/workflows/repo-checks.yml) — the scaffold job phase 5 moves to the binary
- [CONTRIBUTING.md — Versioning & releases](../../CONTRIBUTING.md#-versioning--releases)
- Roadmap epic [#37](https://github.com/adorey/cortex/issues/37)

## 9. Amendments

None yet.
