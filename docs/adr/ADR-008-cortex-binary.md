# ADR-008 — The `cortex` binary: one-line install, one store per machine, `cortex.toml` per project

- **Status:** Accepted
- **Date:** 2026-09-27 (proposed) · 2026-09-27 (accepted)
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
- **Targets:** Linux `x86_64` and `aarch64` (glibc 2.28 or later — built in a `manylinux_2_28` image; in AlmaLinux 8 since, §9, phase 1), macOS `arm64`, Windows `x86_64`. Intel macOS and Windows on ARM are not built.
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

1. **The configuration cascade and the IDE modes** — organisation policy ▸ project ▸ project-local ▸ machine, of which `cortex.toml` and `cortex.local.toml` are the first two files; rendering the resolved prompts for the IDE, which removes the cascade the LLM follows from the templates; a mode for a Cortex extension. Formerly in this ADR's epic; now [#98](https://github.com/adorey/cortex/issues/98).
2. **`cortex.lock` and upgrade tooling** — a resolved manifest, `cortex upgrade`, pruning unused versions from the store — [#99](https://github.com/adorey/cortex/issues/99).
3. **Other models, local ones included** — the provider abstraction, ADR-011 ([#40](https://github.com/adorey/cortex/issues/40)). It inherits the store and the runtime's binding as they are; its endpoints go in the machine tier, `~/.cortex/config.toml`.
4. **The CLI drives the runtime** — `cortex run`, `watch`, `runtime up` over the unified client protocol, ADR-016 ([#45](https://github.com/adorey/cortex/issues/45)).
5. **More channels and platforms** — Homebrew, winget, a signed Windows executable, Intel macOS, a PyPI wheel wrapping the binary if a Python consumer appears — under `cortex-ai`, the name the command falls back to, free on PyPI on 2026-09-26 (`cortex` is taken). [#86](https://github.com/adorey/cortex/issues/86) still reserves `cortex-core` meanwhile: `runtime/pyproject.toml` depends on it by name.

## 8. References

- [ADR-007](ADR-007-cortex-core.md) — `base_root`, the golden fixtures, the self-hosting case
- [ADR-002](ADR-002-cortex-runtime.md) §3.4 — the runtime binding this ADR extends
- [`setup.sh`](https://github.com/adorey/cortex/blob/0.10.1/setup.sh), [`bin/validate-overlays.sh`](https://github.com/adorey/cortex/blob/0.10.1/bin/validate-overlays.sh) — the behaviour to reach, as Cortex 0.10.1 ships it: phase 5 deletes both
- [`deploy/compose.yaml`](../../deploy/compose.yaml) — the runtime's mounts
- [`.github/workflows/repo-checks.yml`](../../.github/workflows/repo-checks.yml) — the scaffold job phase 5 moves to the binary
- [CONTRIBUTING.md — Versioning & releases](../../CONTRIBUTING.md#-versioning--releases)
- Roadmap epic [#37](https://github.com/adorey/cortex/issues/37)

## 9. Amendments

### Phase 1 — the build, the assets, the scripts

- **Linux is built in AlmaLinux 8, not in a `manylinux_2_28` image** (§3.1). The CPython of the manylinux images is linked statically — `Py_ENABLE_SHARED` is `0` in `manylinux_2_28_x86_64` — and PyInstaller needs the shared `libpython`. AlmaLinux 8 has the same glibc, 2.28, and a Python 3.12 built shared. The floor is unchanged: the binary built there runs on Debian 10, whose glibc is 2.28 and which has no Python.
- **The validator lists files in name order** (§3.1, §3.8). It listed them in the order the file system returns them, as `find` did: ext4's on the machine that captured the golden outputs, APFS's or NTFS's elsewhere — the same report could not hold on every target. Each directory's entries are now sorted by name; the captured outputs were already in that order, and none changed. The core's macOS job runs its whole suite since.
- **A build of no release is `0.0.0-dev.N`**, `N` the CI run, and a source checkout `0.0.0-dev` (§3.1): only a tag stamps a released version. A release's tag must be `X.Y.Z` and appear in `CHANGELOG.md`; a GitHub pre-release, `X.Y.Z-something`, may skip the changelog — it is how the release workflow is tested, on a throwaway pre-release.
- **Asset names carry no version** — `cortex-linux-x86_64.tar.gz`, `cortex-windows-x86_64.zip` — so that `releases/latest/download/{asset}` always names the latest release's (§3.2). The release is the version.
- **The binaries are attested, not only the archives** (§3.1): the attestation of an archive names the archive's digest, which nobody holds once it is unpacked. The binary inside each one is attested too, so that `gh attestation verify ~/.cortex/bin/cortex --repo adorey/cortex` checks the installed file itself.
- **The install scripts** (§3.2): both take `CORTEX_RELEASES_URL` for a mirror serving the releases' layout — how CI installs the binary it has just built, from a local server. `install.sh` runs from a function called on its last line — piped from `curl`, a download cut short runs nothing — and runs the binary once before moving it into place, from a directory inside `$CORTEX_HOME`: a binary that cannot run — an older glibc — is never installed, and `/tmp` may be mounted `noexec`. `install.ps1` takes PowerShell's `-Version` and `-Name` for `install.sh`'s `VERSION` and `--name`, writes the user's `PATH` in the registry as it is stored — `%VARIABLES%` unexpanded — and can leave it alone, with `-NoModifyPath` or `CORTEX_NO_MODIFY_PATH=1`. On Windows on ARM it installs the `x86_64` build, which Windows runs under emulation; no build of its own is made.
- **The project root is the directory as the shell names it** — `$PWD` when that is the current directory — not as `getcwd` resolves it. macOS keeps its temporary directories behind a link, `/var` to `/private/var`: resolved, the root was no longer a prefix of the paths the user typed, and `--service $PWD/api` printed whole.

### Phase 1 — found in review

- **A release is made on its tag's push, not by publishing it** (§3.1). The release is created as a draft, from `changelog/X.Y.Z.md`, gets its assets, and is published only once they are all on. Published first, `releases/latest/download/…` named a release without assets for the length of the build — about five minutes on the pre-release — and for good when one target failed. The maintainer pushes the tag; a release already published is never uploaded to again.
- **Integrity is not origin** (§3.2, §5). `SHA256SUMS` comes from where the archive does: it proves the download whole, not who built it. That origin is https: `CORTEX_RELEASES_URL` takes plain http only to this machine, for tests, and neither `file:` nor another scheme. *Traced to the workflow that built it* (§5) holds for whoever runs `gh attestation verify`, which neither script does.
- **The install scripts keep an installed name.** Run again without `--name`, a script upgrades the `cortex` or `cortex-ai` it installed before, instead of adding the other name beside a stale one. A command found first on `PATH` is another `cortex` only if it is another file: a link to the installed binary is the same one. Kept or forced as `cortex` while another comes first, the scripts say so.
- **Why a binary does not run.** `install.sh` shows the binary's own error. A onefile binary unpacks itself in `$TMPDIR` at every start, so a `noexec` `/tmp` stops it as surely as an older glibc. `install.ps1` runs `cortex.exe` before installing it, as `install.sh` does: one Windows will not start is neither installed nor put on `PATH`.
- **The build is pinned.** PyInstaller and its dependencies are pinned by hash for the four targets (`cli/requirements-build.txt`, written by `cli/pin_build.py`), the actions of the binary workflow by commit, and the archives are dated by the commit, their gzip header included: the same commit gives the same archive around the same binary. The binary itself is PyInstaller's, and not reproducible.
- **The glibc floor is measured in CI.** Each Linux binary runs on `debian:buster-slim`, pinned by digest, whose glibc is 2.28 and which has no Python.

### Phase 1 — found in the second review

- **https on every hop, in both scripts as in the command.** `install.sh` asks wget for each redirect itself, since wget follows one to any scheme; curl already took https only. `install.ps1` follows redirects one by one, with .NET, since `Invoke-WebRequest` follows them all. `CORTEX_RELEASES_URL` holds no user part — `http://127.0.0.1:1@example.com` names example.com — and a loopback URL has a port of digits, or none.
- **A binary that starts and fails is not installed either.** `install.ps1` checks the exit code of `cortex.exe --version`, not only that Windows started it: a missing DLL, a onefile binary that cannot unpack itself, exit with an error. `install.sh` names `CORTEX_HOME` beside `TMPDIR` as a directory the binary must be allowed to execute from.
- **A link or a junction on the way to a `cortex` on `PATH`** — a directory of `PATH` that is a junction to `~/.cortex/bin` — is followed by `install.ps1`, as `-ef` does for `install.sh`: that `cortex` is the installed one, not another.
- **The latest release is the highest version**, not the last published: a patch of an older line is published without becoming `releases/latest`. Releases are made one at a time, and no job keeps the checkout's token.

### Phase 1 — the maintainer's arbitration on CI time (2026-09-28)

- **The binaries are built where code integrates**, not on every pull request (§3.1). The binary workflow took about nine minutes a run, its Windows build most of it, on every pull request of a stack, where the tests from source run first anyway. It runs on a push to `main` or to a `release/**` branch, on a pull request into `main` — every one, whatever it changes — on a tag, and by hand. So a stack merges into its release branch, the binaries go green there, and only then does the release branch's pull request into `main` open: merged straight into `main`, a stack would skip the one build of what ships. A tag's push alone releases; a run started by hand on a tag builds and stops there.
- **A pull request's run is cancelled when its branch is pushed again**, in every workflow; the tests' workflows run on a push only to `main` and `release/**`, since a pull request's branch already runs as a pull request.

- **The glibc floor is measured in CI.** Each Linux binary runs on `debian:buster-slim`, whose glibc is 2.28 and which has no Python.

### Phase 2 — the store, sync, and what a tool reads

- **Measured: a link does not keep Claude Code inside the project** (§3.5). Claude Code 2.1.273, in its default permission mode:
  - in `store` mode it reads the spec after asking once for permission, or with no prompt when the store is in its `permissions.additionalDirectories`;
  - in `link` mode it asks too: it checks the path a link resolves to, and that path is outside the project;
  - in `copy` mode it reads with no prompt.

  The table of §3.5 said a link serves "a tool that reads only inside the workspace". For this tool it does not, and `copy` is the fallback. Copilot, Cursor and Codex are not measured yet. The table and how to measure are in [the migration guide](../migrating-to-the-binary.md).
- **On Windows the store's directories take new files** (§3.3). The read-only attribute protects files, not directories. Modifying or deleting a file of the spec fails on every target. Creating a new file beside one succeeds on Windows, and only there. An access-control list that denies it would also stand in the way of removing a version, which #99 will do. None is set.
- **`cortex validate` finds its roots itself** (§3.8):
  - In a project, the roots are the project root and the spec `spec` names. It refuses a spec synced for another version than the pinned one — a teammate bumped `version` and this machine has not synced — rather than validating against a spec the project no longer uses.
  - Without `cortex.toml`, it falls back to the `cortex/` of the current directory. That fallback lasts until phase 5 removes the submodule layout.
  - In a checkout of Cortex, the checkout is the base (ADR-007 §3.1).
  - When it cannot validate, it exits `2`, as the script did without a Python.
- **The spec archive is `git archive` of the tag** — `agents/`, `templates/`, `docs/` as committed, never the working copy — and the binary embeds that same archive for its own version. Other versions are downloaded from `CORTEX_RELEASES_URL` when it is set, as for the install scripts. When the binary's built-in OpenSSL finds no certificates where the build machine kept them — AlmaLinux's `/etc/pki/tls` on a Debian — it loads the system's certificate bundle from where Linux distributions and macOS keep it.
- **A source checkout stands for the version `CORTEX_SOURCE_VERSION` names**, for the tests that download. A build always carries its stamp and never reads it.
- **`sync` also says** when `cortex/` in `link` or `copy` mode is missing from `.gitignore`, and when the active theme is neither in the spec nor in the project. Both are notes: it still syncs.

### Phase 2 — found in review

- **A binary knows the spec archives released before it** (§3.3). The build reads the `SHA256SUMS` of every earlier release and embeds each spec archive's checksum. A download is checked against that checksum as well as the release's `SHA256SUMS`, and refused when the two differ: the release was changed after this binary was built. A binary serves no version newer than itself (§3.3), so it knows every version it serves — except a patch of an older line released after it, which only its `SHA256SUMS` checks. Downloads are https only — plain http only to this machine, for tests — and so is every redirect.
- **A version in the store is complete when its three trees are** (§3.3). A directory holding less is refused and named, not taken for a version. The rename that puts a version in place comes before the change of permissions; a sync interrupted between the two left a writable version, which the next sync makes read-only again. Stagings older than a day are removed.
- **One grammar for `cortex.toml` and `cortex.local.toml`**, in the core (`cortex_core.project`), for the command and the runtime (§3.4). A version is `X.Y.Z` with an optional pre-release, matched whole and in ASCII: `"1.0.0\n"`, which wrote `versions/1.0.0\n`, is refused, and so are digits outside ASCII. The same holds for a theme.
- **`.synced` is a manifest** (§3.5): the version copied — or the checkout, for `--from` — and the SHA-256 of every file written. A copy holding a file sync did not write, or a modified one, is refused, with those files listed: an LLM that writes `cortex/agents/…` instead of `agents/…` — possible on Windows, where the copy's directories take new files — no longer loses its file at the next sync. A `.synced` that is no manifest is refused. A directory with a `.git` is a submodule or a clone before anything else.
- **A link at `cortex/` is sync's** only when it points into the store, or at a checkout while `spec` is `cortex` — a link a developer made is refused like a directory.
- **Sync checks everything, then changes the project in one rename** (§3.5). The new `cortex.local.toml` is rendered, the new link or copy is written beside `cortex/`, then put in its place; only then is `cortex.local.toml` written and the old link or copy removed. A refusal on the way — a `--from` holding no `docs/`, a `spec` sync cannot write — leaves the project as it was. `--from` takes a checkout holding the three trees.
- **In `link` mode the `.gitignore` line is `/cortex`**, with no final slash (§3.5): a link is a file to git, and `cortex/` matches only a directory, so the link — and the absolute path of a developer's store in it — went into the commit. Whether git ignores `cortex` and `cortex.local.toml` is asked of git (`git check-ignore`), which reads every rule, and sync notes either one git does not ignore.
- **`cortex validate` takes a copy or a link from a checkout for that checkout** (§3.8) — the contributors' test loop, in the mode that asks Claude Code for no permission. It refuses a spec synced for another version than the pinned one whatever the store it is in, not only in this machine's `CORTEX_HOME`.
- **Sync and validate say what failed, on which path** — a `CORTEX_HOME` that is a file, a read-only project, a concurrent sync, a failed `mklink` — and exit `1` (`2` for validate), where they printed a traceback.
- **Sync names the project root** it found. The search still goes up through the directories: in a workspace, a service is a repository of its own inside the workspace root, and stopping at a repository's edge would miss the workspace's `cortex.toml`.
- **An empty certificate directory** where the build machine kept one counts as no certificates: the system's bundle is loaded.

### Phase 2 — found in the second review

- **A release from 1.0.0 without its spec archive fails the build** (§3.3). The build skipped it in silence, and the binary would have checked that version against its `SHA256SUMS` alone; a release before 1.0.0 still has none to give. `cortex --version --verbose` prints the table a binary carries, and CI checks, of each binary it builds, that it is the table the build was given — a module left out of the bundle would otherwise check nothing, as a build made without `--known-specs` does, which says so.
- **What an interrupted or a racing sync leaves beside `cortex/` is removed** (§3.5): a staged link or copy, an entry moved aside, once no sync can still be using it — ten minutes. A link among them named this machine's store, and `/cortex` did not keep it out of a commit. What is removed is decided by what it is, not by what it was when sync looked; a `cortex.local.toml` sync cannot write puts `cortex/` back as it was; and a sync that finds `cortex/` put back meanwhile says so.
- **A copy that lost a file is copied again** by sync, which says which files; `cortex validate` refuses a copy that no longer matches its manifest — a file added, changed or missing — rather than validate against another spec.
- **A value `cortex.toml` is refused for is shown escaped**, as JSON writes it: a committed file may hold a newline or a terminal's control sequence.
- **A stored version left writable is found by its files**, on every target: on Windows a directory never tells.
- **A copy's own directory is made read-only once in place**, and writable again before it is moved: macOS renames no directory its owner may not write in, where Linux does — a copy sealed before its rename never reached `cortex/` there. What the copy holds is read-only throughout.

### Phase 2 — found in the third review

- **One sync of a project at a time** (§3.5): the others wait for it, up to two minutes. Racing, most of them failed on a path of their own, and a residue could outlive them. The lock writes nothing: on POSIX it is the project's directory, on Windows a byte of `cortex.toml` far past its end. Under it, what an interrupted sync left beside `cortex/` is removed at once, whatever its age, and a copy kept as it was is sealed again.
- **A value of `spec` a message quotes is escaped**, as `cortex.toml`'s are.

