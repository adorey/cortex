# Changelog

All notable changes to Cortex are recorded here — **this file is the single source of truth for versions**.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Each entry links to its detailed, narrated
release note under [`changelog/`](changelog/).

## [Unreleased]

## [1.1.1] - 2026-09-30 — Unpleasantly Like Being Drunk _(Released)_
[Full notes](changelog/1.1.1.md)

### Fixed
- **A teammate who pulled the submodule's removal is no longer sent to commands that cannot run** ([#147](https://github.com/adorey/cortex/issues/147)). After such a pull, git has dropped `cortex` from the index and kept the directory, the submodule's repository and its settings: `git submodule deinit` and `git rm` had nothing left to act on, and `cortex sync` refused again. It now tells the two states apart — asking git whether the index still holds the submodule — and prints, for the teammate, the commands that remove what the pull left. Before them come two checks: what changed in `cortex/`, ignored files included — but the theme marker `setup.sh` wrote — and the commits no remote branch holds. If a command 1.0.0 or 1.1.0 printed already removed the submodule's repository, it says instead that git can no longer show what changed.
- **The last submodule leaves no empty `.gitmodules`:** `git rm cortex` empties the file and keeps it tracked, so the commands `cortex init` prints include `git rm -f .gitmodules` when `cortex` was the only submodule.
- The refusal of a `cortex/` that is a submodule, a clone or another directory Cortex did not write names Cortex, not *cortex sync*: `cortex init` prints it too.
- **A binary no longer carries the checksums of pre-releases** ([#151](https://github.com/adorey/cortex/issues/151)): 1.0.0 and 1.1.0 knew `0.0.0-alpha.1`'s, which no binary serves. A pre-release is thrown away or built again under its tag, and a checksum kept for it would have the binaries built meanwhile refuse the new build. A pre-release is checked against its release's `SHA256SUMS` alone, like a release newer than the binary.
- The CLI suite no longer breaks when a theme is added ([#148](https://github.com/adorey/cortex/issues/148)): a test listed the shipped themes by hand, and reads them from its spec now.

## [1.1.0] - 2026-09-30 — Vogon Poetry _(Released)_
[Full notes](changelog/1.1.0.md)

### Added
- **The `code-review` workflow** (`agents/workflows/engineering/code-review.md`) — reviewing someone's pull request (mode A), and handling the review of ours (mode B), with one grid for both sides: a shared legend (🔴 blocking, 🟠 major, ⚪ minor, ❓ doubt, 🎫 out of scope), rules that make a review converge — a 🔴 or a 🟠 is proven in the code, a defect older than the pull request becomes an issue, no new mechanism in answer to a review, a new point from round 2 only on the previous round's delta — the GitHub event each verdict takes, and the template of the published review. Mode A also checks that the base is current, runs the CI again when it ran older workflows, and replays what the description says was verified.

## [1.0.0] - 2026-09-30 — So Long, and Thanks for All the Fish _(Released)_
[Full notes](changelog/1.0.0.md)

### Added
- **The `cortex` command** ([ADR-008](docs/adr/ADR-008-cortex-binary.md)): a native binary for Linux (`x86_64`, `aarch64`, glibc 2.28 or later), macOS (Apple silicon) and Windows (`x86_64`) that needs no Python. `cortex validate` runs the overlay checks of `bin/validate-overlays.sh` — same options, same report, same exit codes.
- **A one-line install**: `curl -fsSL …/install.sh | sh` on Linux and macOS, `irm …/install.ps1 | iex` on Windows. Both check the download against the release's `SHA256SUMS` and install into `~/.cortex/bin`, as `cortex-ai` when another `cortex` comes first on `PATH`. Each release carries the binaries, their `SHA256SUMS` and a build-provenance attestation for each. They download over https only — every redirect too — and install no binary that does not run here.
- **One spec per machine**: `~/.cortex/versions/X.Y.Z`, read-only, filled on demand — the binary's own version from itself, others downloaded from their release's spec archive and checked against its `SHA256SUMS`. A project pins its version in a committed `cortex.toml`; `cortex sync` writes where the spec is in `cortex.local.toml`, which git ignores. The spec is read in place, or brought into the project as `cortex/` with `--link` or `--copy`; `--from PATH` uses a checkout. `cortex validate` validates against that spec. A binary embeds the checksum of every spec archive released before it, and refuses a download its release no longer matches. One sync of a project runs at a time.
- **`cortex init`** — `setup.sh`, at parity: the same options and the same files, byte for byte, plus `cortex.toml`, `cortex.local.toml` and its `.gitignore` line. Services are named by a repeatable `--service`, so `--workspace` runs unattended; an existing instructions file is kept unless `--force`, which keeps it as `FILE.bak` — `FILE.bak.N` when a backup is there: none is overwritten. In a project that has one, `cortex.toml` keeps its version and changes only for the options given. A project whose `cortex/` is a submodule, a worktree or a clone is refused, with the commands that remove it. Beyond parity, `--from PATH` writes the bootstrap from a checkout's templates and syncs from it — the contributors' test loop — and `--theme` also takes a theme of the project's own, in `agents/personalities/`. A project that has a `cortex.toml` keeps the tool whose instructions file is there; a new one takes Copilot's, as before. Outside a git repository no `.gitignore` is written.
- **`claude_access`** — on request, `cortex sync` lets Claude Code read the spec in the store without asking for permission. It keeps the store's path in `.claude/settings.local.json` — that entry only, recorded as `claude_entry` in `cortex.local.toml`, and never the developer's own; `cortex init --tool claude` offers it, and `cortex sync --claude-access` and `--no-claude-access` set it for one developer.

### Changed
- 💥 **A project uses Cortex through `cortex.toml`, not a submodule.** The bootstrap templates read the spec from the directory `spec` names in `cortex.local.toml`, and the theme from `cortex.local.toml`, then `cortex.toml`: the active-theme marker is gone. Moving a project over is covered by [the migration guide](docs/migrating-to-the-binary.md).
- The validator lists files in name order — not in the file system's — so that its report is the same on every platform.
- 💥 **`cortex validate` needs a `cortex.toml`.** Where `bin/validate-overlays.sh` read the `cortex/` of the current directory, a project without `cortex.toml` exits `2`; one whose `cortex/` is a submodule or a clone is sent to `cortex init`, which says how to leave it; one whose spec was synced for another version than `cortex.toml` pins is sent to `cortex sync`.
- **The runtime takes a project's base from its `cortex.toml`** ([ADR-002 §9](docs/adr/ADR-002-cortex-runtime.md#9-amendments)): the store's copy of the version it pins, read when a run is accepted and named in the answer, `cortex_version`. `deploy/compose.yaml` mounts the store's `versions/`, and nothing else of it, read-only from `CORTEX_STORE_PATH`. A project without `cortex.toml` resolves as before; a version the store lacks is refused, `422`. Without `CORTEX_THEME` — which `deploy/.env.example` no longer sets — the theme is the one `cortex.toml` names.

### Removed
- 💥 `setup.sh` and `bin/validate-overlays.sh` — `cortex init` and `cortex validate` replace them, with the same options and the same output.
- 💥 `python3 -m cortex_core.validate` and `cortex_core.validate.cli()`, the script's way into the core ([ADR-007 §9](docs/adr/ADR-007-cortex-core.md#9-amendments)): `cortex validate` runs the core's validator.

## [0.10.1] - 2026-09-27 — Mostly Harmless _(Released)_
[Full notes](changelog/0.10.1.md)

### Fixed
- The delivery process showed several issues behind one closing keyword (`Closes #42, #43`), which closes the first one only; it now says one `Closes #NN` per issue — in the process, the `adr-implementation` workflow and the pull request template.

## [0.10.0] - 2026-09-27 — Quite Definitely the Answer _(Released)_
[Full notes](changelog/0.10.0.md)

### Added
- `cortex-core` (`core/`) — the one implementation of the cascade in code: resolution, merge semantics, the capability catalog, prompt assembly and overlay validation, parameterised by a `base_root` ([ADR-007](docs/adr/ADR-007-cortex-core.md)). Standard library only, Python 3.9 or later.

### Changed
- `bin/validate-overlays.sh` is a shim over `cortex-core`: it needs **Python 3.9 or later**, runs Python isolated, and is about 77× faster — same options, same exit codes.
- The validator reports a headerless file at the path of a base (`MISSING_HEADER`) and checks the overlays behind a symbolic link; `--strict` may start failing on them. A headerless `characters.md` stays `NON_OVERRIDABLE`; a `README.md` is documentation.
- The runtime reads ADR-006's team tier, `agents/project-context.md`, and selects capabilities from it, for every role alike — prompts grow accordingly.
- **The agent sees the project** ([ADR-002 §9](docs/adr/ADR-002-cortex-runtime.md#9-amendments)): its system prompt closes on `# Project overview`, `# Workspace services` and `# Project context`. That is 44 to 66 KB of prompt on every model call, and the developer's untracked notes sent to the model provider; the API backend marks the system prompt cacheable. A run's `service` must be a folder of the workspace, or it is refused (`422`).
- The runtime depends on `cortex-core`: install both, `pip install -e ../core -e .` from `runtime/`.

### Fixed
- A header missing its `Base:`, `Scope:` or `Semantic:` key stopped the validator at once; it is reported as `MISSING_FIELD`.
- The validator's verdicts no longer depend on where the project sits — under a directory named `agents` or `cortex` — and a service overlay with no category level that declares `Scope: workspace` gets `SCOPE_MISMATCH`.
- Header values and file names are printed as read, control characters escaped: an overlay can no longer rewrite the report on a terminal.
- The `claude-cli` backend could not start past 128 KiB of prompt: the system prompt now goes in a file, the task on stdin.
- `setup.sh` named every scaffolded service `@my-project`, and stopped on a service in a subfolder.

## [0.9.0] - 2026-09-23 — Beware of the Leopard _(Released)_
[Full notes](changelog/0.9.0.md)

### Added
- `adr-implementation` workflow — a generic, stack-agnostic eight-step pipeline for delivering one phase of an accepted multi-phase ADR.
- `docs/process/adr-implementation.md` — one integration branch per ADR, one stacked pull request per phase, the four-level issue model (epic → milestone → phase → task), labels and gates.
- Maintainer tooling: `bin/setup-labels.sh`, ADR epic / phase / task issue templates and a pull request template.

### Changed
- ADRs delivered in several steps end with a numbered **Phases** section; new `Implemented` status.
- A pull request inside a stack is merged with a merge commit — never squashed or rebased; ADR work puts `#<issue>` before the commit subject.
- The release naming convention — a name per release, an epigraph per note — is written into `CONTRIBUTING.md`.

### Fixed
- The workflows index listed two of the four generic workflows; `frontend-testing` and `support-triage` were missing.
- `CONTRIBUTING.md` described a release process nobody followed: its release steps now match practice — an integration branch, artefacts stacked last with their heading already marked `_(Released)_`, a GitHub Release, tags without a `v` prefix — and its changelog instruction points at `## [Unreleased]` instead of a `## Changes` section that does not exist.
- `CONTRIBUTING.md` and `CLAUDE.md` no longer point at a `validate-cortex.sh` planned for 0.3 and never written; both name `bin/check-english.sh`, the gate CI actually runs.
- 0.8.0 was released without its `_(Released)_` marker.

## [0.8.0] - 2026-08-26 — Marginalia _(Released)_
[Full notes](changelog/0.8.0.md)

### Added
- `practices/` capability category, opening with `code-comments` — comment the *why*, descriptive not narrative, density under the project's rule. Declared `always load` by `lead-backend`, `lead-frontend`, `architect` and `qa-automation`.

### Changed
- `languages/php`, `languages/typescript` and `frameworks/vue` gain a doc-block section covering their own mechanics only, pointing at the shared card; the orphan comment bullet in `lead-backend` now references it.
- `templates/project-context.md.template` prompts for the project's own comment conventions (language, reference format).
- The capability tree is refreshed in all three places that carry it — `README.md`, `agents/capabilities/README.md` and `docs/getting-started.md`; `agents/capabilities/README.md` also names the distinction between stack-resolved and unconditional categories.

### Fixed
- `lead-backend` declared no capability category at all, so the role loaded none — restored to `languages/`, `frameworks/`, `databases/`, `security/` and `practices/`.
- `lead-frontend`'s capability list rendered as a single run-on line (lost newline after `**Categories to load:**`).

## [0.7.0] - 2026-08-18 — End to End _(Released)_
[Full notes](changelog/0.7.0.md)

### Added
- `testing/` capabilities: framework-agnostic `e2e-testing` and `component-testing`; a `frameworks/vue` card; a `frontend-testing` workflow.
- `regulatory-compliance-writer` role + **@Pag** character.

### Changed
- Symfony reference gains an "End-to-end & functional testing" section **and three more traps that pass every gate**; `lead-frontend` and `qa-automation` now load the `testing/` category.

## [0.6.0] - 2026-08-13 — Trapdoor
[Full notes](changelog/0.6.0.md)

### Added
- Five Symfony "security traps that pass every gate"; a `qa-automation` role card.

### Changed
- Translated API error responses (translatable HTTP exceptions, never a raw throw) documented in the Symfony card.

## [0.5.0] - 2026-08-10 — Publishable
[Full notes](changelog/0.5.0.md)

### Added
- A licence and community documentation; CI for the framework layer.

### Changed
- English throughout (including the archive template); line endings pinned to LF.

## [0.4.1] - 2026-07-28 — Reuse before create
[Full notes](changelog/0.4.1.md)

### Added
- A dispatch-protocol step that checks whether an existing script/playbook/job already covers the case before writing a new one.

## [0.4.0] - 2026-07-20 — Team & developer context tiers (ADR-006)
[Full notes](changelog/0.4.0.md)

### Added
- Two aggregated context tiers: team context in `agents/`, developer context at the root — no change to existing root files.

## [0.3.2] - 2026-07-20 — Cortex reads its own instructions
[Full notes](changelog/0.3.2.md)

### Changed
- Self-hosted `CLAUDE.md` so Cortex bootstraps itself.

## [0.3.1] - 2026-07-09 — Docs catch up with the engine
[Full notes](changelog/0.3.1.md)

### Changed
- README and docs now cover both halves of Cortex (framework + runtime).

## [0.3.0] - 2026-07-09 — The runtime comes alive
[Full notes](changelog/0.3.0.md)

### Added
- The Cortex Runtime executable engine (ADR-002/003), persistence & state, API security & trust model (ADR-004), async execution & resilience (ADR-005), webhooks, and deploy/DevEx tooling.

## [0.2.2] - 2026-06-02 — Cortex Runtime direction (ADR-002)
[Full notes](changelog/0.2.2.md)

### Added
- ADR-002 (Cortex Runtime) accepted, with supporting documentation.

## [0.2.0] - 2026-04-28 — Layered overrides
[Full notes](changelog/0.2.0.md)

### Added
- The cascade/overlay convention for all agent layers, the overlay file convention, and `validate-overlays.sh`.

## [0.1.2] — Minimal Dependencies Principle
[Full notes](changelog/0.1.2.md)

### Added
- A "Minimal Dependencies" universal principle; role-card updates.

## [0.1.1] — Starlight Capability & Archiving Revamp
[Full notes](changelog/0.1.1.md)

### Added
- A Starlight capability; Archiving Protocol v2.

## [0.1.0] — First Release
[Full notes](changelog/0.1.0.md)

### Added
- The 3-layer architecture, 15 agent roles, the H2G2 personality theme, the Prompt Manager & dispatch protocol, the workflows layer, and setup & tooling.
