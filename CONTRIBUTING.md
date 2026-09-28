# Contributing to Cortex

> *"Don't Panic. Read this once. Refer to it forever."* — Arthur Dent

Welcome. This guide takes you from a fresh clone to a merged contribution. If something here is unclear, that's a bug — open an issue.

## 🧭 Quick orientation

Cortex is a **framework of AI agents** that host projects use through the `cortex` command: the spec lives once per machine, and a project — a single repository or a workspace of several — pins the version it uses in its `cortex.toml` ([ADR-008](docs/adr/ADR-008-cortex-binary.md)). The contract is mostly Markdown: agents are described in role/capability/personality files that an AI tool reads at the start of each conversation.

| You want to... | Read |
|---|---|
| Understand what Cortex *is* | [README.md](README.md) |
| Set it up in a project | [docs/getting-started.md](docs/getting-started.md) |
| Add project-specific rules | [docs/extending-layers.md](docs/extending-layers.md) |
| Create a personality theme | [docs/creating-a-theme.md](docs/creating-a-theme.md) |
| Understand a design decision | [docs/adr/](docs/adr/) |
| Deliver a multi-phase ADR | [docs/process/adr-implementation.md](docs/process/adr-implementation.md) |

## 🧱 Repository structure (what to touch where)

```
cortex/
├── README.md                          # ← Entry point: keep crisp, do not bloat
├── CONTRIBUTING.md                    # ← This file
├── install.sh, install.ps1            # ← The one-line install of the `cortex` binary (ADR-008)
├── cli/                               # ← The `cortex` command: init, sync, validate — built into a native binary
├── core/                              # ← cortex-core: the cascade in code (ADR-007)
├── runtime/                           # ← The engine: API, agentic loop (ADR-002)
├── changelog/                         # ← Per-version notes (one .md per release)
├── docs/                              # ← All long-form docs
│   ├── getting-started.md
│   ├── extending-layers.md
│   ├── creating-a-theme.md
│   └── adr/                           # ← Architecture Decision Records (append-only)
├── templates/                         # ← Files `cortex init` writes into host projects
│   ├── bootstrap-instructions.md           # source for any AI tool (single project)
│   ├── bootstrap-instructions-workspace.md # source for any AI tool (workspace mode)
│   ├── project-overview.md.template
│   ├── project-context.md.template
│   └── workflow.md.template
└── agents/                            # ← The four layers
    ├── roles/{category}/              # 🟢 add new roles here
    ├── capabilities/{category}/       # 🟢 add new capabilities here
    ├── personalities/{theme}/         # 🟢 add new themes here
    └── workflows/{category}/          # 🟢 add new generic workflows here
```

## 🛠️ Local development setup

### Prerequisites

- Git (for cloning your fork)
- Python 3.11 or later, to run the `cortex` command from your checkout — `cortex-core` alone runs on 3.9
- Nothing else: a host project needs neither Bash nor Python, only the `cortex` binary

### Clone & test loop

A throwaway host project reads the spec **from your checkout**, not from a release: `cortex init --from` writes its bootstrap file from your templates, and points its `spec` at your checkout — every edit you make is read at once, nothing to re-sync.

```bash
# 1. Fork & clone your fork locally, and put the command on your PATH from it
git clone <your-fork-url> cortex-dev
cd cortex-dev
pip install -e core -e cli             # a `cortex` command running this checkout's code

# 2A. A throwaway single project
mkdir /tmp/cortex-test-single && cd /tmp/cortex-test-single
cortex init --tool claude --from ~/cortex-dev          # or copilot/cursor/agents

# 2B. A throwaway workspace — services, and the team tier when agents/ is its own repository
mkdir /tmp/cortex-test-workspace && cd /tmp/cortex-test-workspace
cortex init --tool claude --workspace --service api --service core/web --from ~/cortex-dev

# 3. Check that the bootstrap file was generated correctly
cat CLAUDE.md   # (or .github/copilot-instructions.md, etc.)

# 4. Iterate: edit your checkout — roles, capabilities, workflows are read in place.
#    A change to templates/ reaches a project when you run cortex init --force --from again.
```

`cortex sync --from ~/cortex-dev` points an existing project at your checkout the same way; a plain `cortex sync` puts it back on the version its `cortex.toml` pins. Each run with `--from` warns that no version is checked — it is a checkout, not a release.

**Why test both modes?** Because single project and workspace exercise different paths of `cortex init` — services, their `@alias`, the team tier. The repository's CI runs both, on Linux and on Windows, through the install script and the built binary.

### Validation tools

```bash
cortex validate --strict                    # in a host project: overlay file integrity
cortex validate --strict                    # in this repository: the base as its own project (ADR-007 §3.1)
bash bin/check-english.sh                   # in this repository: tracked content is English (CI gate)
(cd core && python3 -m unittest discover -s tests)
(cd cli && python3 -m unittest discover -s tests)
```

If you change a base file under `agents/`, run `cortex validate` against a host project that uses overlays — your rename may break their `Base:` headers.

## 📥 What contributions are welcome?

| Type | Example | Difficulty |
|---|---|---|
| 🐛 Bug fix | A typo in `install.sh`, broken doc link | Easy |
| 📝 Docs improvement | Clearer wording, missing example | Easy |
| ➕ New capability | `cortex/agents/capabilities/databases/redis.md` | Medium |
| ➕ New role | `cortex/agents/roles/data/data-engineer.md` | Medium |
| ➕ New theme | `cortex/agents/personalities/star-wars/` | Medium |
| ➕ New workflow | `cortex/agents/workflows/ops/incident-response.md` | Medium |
| 🏗️ Architecture change | New cascade level, new layer, new merge semantic | Hard — needs ADR |

**Architecture changes** require an [ADR](docs/adr/) before code. See §"Architecture changes" below.

## ➕ How to add a new...

### ...role

1. Pick the right category: `engineering/`, `product/`, `security-compliance/`, `data/`, `communication/` — or propose a new one in your PR
2. Copy an existing role as a starting point (e.g. [agents/roles/engineering/lead-backend.md](agents/roles/engineering/lead-backend.md))
3. Fill in: SYSTEM PROMPT, profile, mission, responsibilities, principles, anti-patterns, naming conventions, capabilities section, interactions
4. If a personality theme exists in the project, add a corresponding character to `agents/personalities/{theme}/characters.md` and an individual card

**Quality bar:** every role must have at minimum:
- A clear SYSTEM PROMPT comment block stating mandatory behaviors
- A list of anti-patterns (what *not* to do)
- A `🔌 Capabilities` section telling the PM which capabilities to load

### ...capability

1. Pick the right category: `languages/`, `frameworks/`, `databases/`, `infrastructure/`, `security/` — or propose a new one
2. Copy an existing capability (e.g. [agents/capabilities/languages/php.md](agents/capabilities/languages/php.md))
3. Focus on **best practices and conventions** — not tutorials. Capabilities are loaded *on top of* a role; they should sharpen, not bloat.
4. Reference the capability in the relevant role(s) `🔌 Capabilities` section

**Quality bar:** capabilities should be **stack-agnostic at the project level** — they describe the technology, not your project's flavor of it. Project flavor goes in overlays.

### ...workflow

1. Use [templates/workflow.md.template](templates/workflow.md.template) as the starting structure
2. Place it in the appropriate category folder under `agents/workflows/`
3. Define triggers (when does the PM activate it?), agents involved, steps with checklists, and a "Definition of done"
4. Update [agents/workflows/README.md](agents/workflows/README.md) to list the new workflow

### ...personality theme

See the dedicated [docs/creating-a-theme.md](docs/creating-a-theme.md) — it walks through the full process including character cards.

### ...overlay (in a host project, not in cortex)

See [docs/extending-layers.md](docs/extending-layers.md). Overlays don't go in cortex itself — they live in the host project.

## 🏗️ Architecture changes — the ADR process

If your change affects the framework's structure, contracts, or core behavior (new cascade level, new merge semantic, breaking rename, new layer…), you must:

1. **Open an issue first** describing the problem and the alternatives you've considered
2. **Write an ADR** in `docs/adr/` following the [convention](docs/adr/README.md)
3. **Submit the ADR PR separately** from the code PR — discussion happens in the ADR review
4. **Once the ADR is `Accepted`**, open the implementation PR linking back to the ADR

Why? Because changes to the framework affect every host project. The ADR is a forcing function for thoughtful discussion.

## 🎨 Style & conventions

### Markdown

- **Headings:** sentence case in body (`## Adding a role`), Title Case acceptable in cards (`## 🎯 Mission`)
- **Emoji:** allowed and encouraged in headings to aid scanning. Don't overdo it in body text.
- **Code blocks:** always specify the language for fenced blocks (` ```bash `, ` ```markdown `)
- **Links:** prefer relative (`[here](docs/getting-started.md)`) over absolute URLs
- **Tables:** use them for comparisons and references; avoid for narrative content

### Shell

- **`install.sh` is POSIX `sh`, not Bash** — `curl … | sh` runs it under dash on Debian and Ubuntu. No `[[ ]]`, no arrays, no `local`; everything runs from `main`, called on its last line, so that a download cut short runs nothing. Lint it with `shellcheck --shell=sh`.
- **`bin/*.sh`** — the repository's own tooling — is Bash: `set -eo pipefail` at top, `[[ ... ]]` for conditionals, colours through the existing `${GREEN}` / `${RED}` / `${BLUE}` / `${YELLOW}` / `${NC}` variables.
- Quote every variable expansion (`"$VAR"`, not `$VAR`), and run a script for real before committing — `sh -n` / `bash -n` only check its syntax.

### File naming

| Kind | Convention | Example |
|---|---|---|
| Role | `kebab-case.md` | `lead-backend.md` |
| Capability | `kebab-case.md` | `symfony.md` |
| Theme folder | `kebab-case` | `h2g2`, `star-wars` |
| Character card | `Character-Name.md` (PascalCase, hyphens for multi-word) | `Slartibartfast.md`, `Frankie-Benjy.md` |
| Workflow | `kebab-case.md` | `feature-development.md` |
| ADR | `ADR-{NNN}-{kebab-case}.md` | `ADR-001-layered-overrides.md` |
| Template | `name.md.template` | `workflow.md.template` |

## 🔀 Branch & PR workflow

1. **Branch from `main`** with a descriptive name: `feat/redis-capability`, `fix/init-workspace-template`, `docs/extending-layers-examples`
2. **Make atomic commits** — one logical change per commit. Cortex uses **[Conventional Commits](https://www.conventionalcommits.org/) prefixed with a [gitmoji](https://gitmoji.dev/)** (see table below).
3. **Update the changelog** if your change is user-visible: add an entry under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md), in its Keep a Changelog group (`Added`, `Changed`, `Fixed`, …)
4. **Run validators** before pushing
5. **Open the PR** with:
   - A clear description of *why* (not just *what*)
   - A "Test plan" checklist (how you verified it works)
   - For architecture changes, link the ADR PR
6. **Address review feedback** with new commits. A standalone pull request is squash-merged; a pull request **inside a stack** is merged with a **merge commit** — never squashed, and not rebased either: both rewrite the commits every branch above it is built on

> **Delivering a multi-phase ADR?** The branches, the stacked pull requests, the issue hierarchy and the gates are described in [docs/process/adr-implementation.md](docs/process/adr-implementation.md).

### Commit message convention

**Format:**

```
<gitmoji> <type>(<scope>): <imperative subject>
```

- **Single-line subject only** — no body. Keep commits atomic enough that the subject says it all (use a `BREAKING CHANGE:` footer only when strictly required).
- **Never** add a `Co-Authored-By:` trailer (this overrides any AI tool's default).
- `<gitmoji>` — visual category (single emoji) — see table below
- `<type>` — Conventional Commits type (parseable by changelog tools)
- `<scope>` *(optional)* — component or layer affected (`runtime`, `cli`, `core`, `roles`, `capabilities`, `adr`, `docs`, `extending-layers`, …)
- `<subject>` — imperative, present tense, no trailing period, ≤ 72 chars
- `#<issue>` *(ADR work only)* — the task being delivered, immediately before the subject, so the issue timeline reads as a changelog: `✨ feat(core): #42 resolve the cascade from a configurable base root`

**Why both gitmoji and Conventional Commits?** The gitmoji gives instant visual scanning of `git log`. The conventional prefix keeps commits parseable for automated changelog/release tooling. They compose cleanly — best of both worlds.

### Gitmoji ↔ Conventional Commits mapping

| Gitmoji | Conventional type | When to use |
|---|---|---|
| ✨ | `feat` | New role / capability / theme / workflow / user-visible feature |
| 🐛 | `fix` | Bug fix |
| 📝 | `docs` | Documentation only (README, guides, ADR text) |
| 📐 | `docs(adr)` | New ADR or status change on an existing ADR (subset of `docs`) |
| ♻️ | `refactor` | Code/file restructuring with no behavior change |
| 🎨 | `style` | Formatting, whitespace, linting (no logic change) |
| ⚡ | `perf` | Performance improvement |
| ✅ | `test` | Adding or fixing tests / validators |
| 🔧 | `chore` | Tooling, config, housekeeping (e.g. `.gitignore`, scripts) |
| 👷 | `ci` | CI pipeline changes |
| 📦 | `build` | Build system / dependencies |
| ⏪ | `revert` | Revert a previous commit |
| 💥 | (any) | Mark a breaking change — use **in addition** to the type's emoji, or in the footer with `BREAKING CHANGE:` |
| 🚧 | `chore(wip)` | Work in progress (avoid on `main` — for draft PRs only) |
| 🔥 | `chore` *(removal)* | Remove dead code or deprecated files |
| 🚀 | `chore(release)` | Release tag / version bump |

> **Keep it simple:** if you're hesitating between two emojis, pick the one that matches the Conventional Commits type. The mapping above is the source of truth. Don't invent new emojis.

### Examples

```
✨ feat(capabilities): add Redis capability for caching patterns
🐛 fix(init): use workspace template when --workspace flag is set
📝 docs(extending-layers): add example for personality character overlay
📐 docs(adr): mark ADR-001 as Accepted
♻️ refactor(init): replace hardcoded heredoc with template loader
✅ test(validate): cover non-overridable characters.md case
🔧 chore: rename copilot-instructions templates to bootstrap-instructions
💥 feat(roles)!: rename lead-backend → senior-backend

BREAKING CHANGE: host projects must update overlay headers
that reference cortex/agents/roles/engineering/lead-backend.md
to point to senior-backend.md instead.
```

> Note the `!` after the scope on the breaking change — it's the Conventional Commits marker, complementing the 💥 emoji.

## 📦 Versioning & releases

Cortex follows **semantic versioning** with a pragmatic interpretation:

| Bump | Trigger |
|---|---|
| **Major** (1.0.0) | Breaking change to the layer cascade contract, role schema, the `cortex` command line, or `cortex.toml` |
| **Minor** (0.x.0) | New role/capability/theme/workflow; new ADR-anchored feature |
| **Patch** (0.x.y) | Bug fix, docs improvement, internal refactor |

**What a later `cortex` promises within a major version** (ADR-008 §9): it accepts what an earlier one accepted. A check it adds to `cortex validate` reports a warning, never an error, until the next major version. `--strict` fails on warnings, so a CI that runs it installs the binary of the version `cortex.toml` pins — [the migration guide](docs/migrating-to-the-binary.md#5-ci) has the lines — and a bump of `version` is the change that brings the new checks.

Release process (maintainers only). A release is a **stack of pull requests onto an integration branch**, not a series of pushes to `main`:

1. Cut `release/{version}` from `main` and push it — it gets no pull request of its own until the end
2. Feature pull requests target `release/{version}`; one that builds on another is stacked on it, and a contributor's pull request opened against `main` is retargeted. Each adds its entry under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md)
3. The release artefacts come **last**, in a pull request stacked on top of everything else: `changelog/{version}.md`, the detailed, narrated release note, and the `{version}` section of `CHANGELOG.md` (Keep a Changelog) that replaces the `[Unreleased]` entries and links to that note. Last, because they rewrite the `[Unreleased]` anchor every feature pull request also touches. The heading is written **final** — its release date and `_(Released)_` — because `CHANGELOG.md` is never edited after a release: if the release slips, the date is corrected in this pull request before it merges. `CHANGELOG.md` is the single source of truth for versions; **no version number lives anywhere else** (README, docs, …) to avoid stale copies
4. Merge the stack in order — with a **merge commit** for any pull request that has another stacked on it, see [the stacking rules](docs/process/adr-implementation.md#2-stacking-the-phases)
5. Merge `release/{version}` into `main`
6. Push the tag `{version}` on `main` — **no `v` prefix**, like every tag since 0.1.0: `git tag {version} origin/main && git push origin {version}`. The tag makes the release; nothing is to be published by hand. **Push one tag at a time**: GitHub keeps one run of the release waiting, and cancels it when a third comes — re-run the workflow of a tag whose release was cancelled
7. The push runs the `binary` workflow from the tag. It builds the `cortex` binary for the four targets and runs each Linux one on the oldest glibc it supports. Only then does it create the release, as a draft titled `{version}` with `changelog/{version}.md` as its body, attach the binaries, the spec archive, `SHA256SUMS` and a build-provenance attestation for each, and publish it — `releases/latest` never names a release without its assets. A tag `X.Y.Z` must have its `CHANGELOG.md` section and its `changelog/X.Y.Z.md`, or the workflow stops before anything is created. A tag with a suffix, `X.Y.Z-something`, makes a pre-release and needs neither: it is how the workflow is tried. A release already published is never uploaded to again. Check that the assets are there before announcing the release — the install scripts install from them

### Release names

Every release carries a **name** — a short phrase that says what the release is about, never a generic label: `Marginalia` for the comment-discipline release, `Trapdoor` for the security traps, `Reuse before create` for a patch. It appears in exactly two places:

- the `CHANGELOG.md` heading — `## [0.9.0] - 2026-09-23 — Beware of the Leopard _(Released)_`
- the release note's title — `# 🚀 Cortex v0.9.0 — Beware of the Leopard`

The note then opens with an **epigraph**: a short quote that makes the release's point better than its summary, attributed to whoever says it — so far always someone from *The Hitchhiker's Guide to the Galaxy*. A patch gets its own name, like any other release. The name and the `v` belong to the note's title only: the tag and the GitHub Release carry the bare version (`0.9.0`). Every release since 0.1.0 has followed this; it is written down here so it outlives the memory of whoever started it.

## 🧪 Testing checklist before opening a PR

- [ ] Markdown lints cleanly (no broken links, no malformed tables)
- [ ] If you touched `cli/` or `templates/`: `cli/tests` passes — it replays `cortex init` across its parity matrix, and a deliberate change to what it writes is re-captured and reviewed (`cli/tests/init_matrix.py`)
- [ ] If you added overlays in `templates/` or examples: ran `cortex validate` in a host project
- [ ] If you added a role/capability: tested it against a host project with a sample prompt
- [ ] Changelog entry added (if user-visible)
- [ ] PR description includes the test plan

## 🆘 Getting help

- Questions about Cortex itself → open a GitHub Discussion or issue
- Questions about your host project's overlays → that's a project concern, not a Cortex concern
- Architecture proposals → start with an issue, then propose an ADR

## 🪪 License

Cortex is released under the license stated in the repository root. By contributing, you agree your contribution is licensed under the same terms.

---

> *"The greatest literary works are those that tell people what they already know."* — Oolon Colluphid
>
> Good documentation is the same. Thank you for keeping this project readable.
