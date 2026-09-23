# Contributing to Cortex

> *"Don't Panic. Read this once. Refer to it forever."* — Arthur Dent

Welcome. This guide takes you from a fresh clone to a merged contribution. If something here is unclear, that's a bug — open an issue.

## 🧭 Quick orientation

Cortex is a **framework of AI agents** that host projects mount, either as a **Git submodule** (single project / monorepo) or as a **standalone clone** sitting next to independent service repos (multi-repo workspace). The contract is mostly Markdown: agents are described in role/capability/personality files that an AI tool reads at the start of each conversation.

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
├── setup.sh                           # ← Installation logic (Bash)
├── changelog/                         # ← Per-version notes (one .md per release)
├── docs/                              # ← All long-form docs
│   ├── getting-started.md
│   ├── extending-layers.md
│   ├── creating-a-theme.md
│   └── adr/                           # ← Architecture Decision Records (append-only)
├── templates/                         # ← Files copied by setup.sh into host projects
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
- Bash 4+ (for testing `setup.sh`)
- A test host project where you can mount your fork — either as a Git submodule or as a standalone clone

### Clone & test loop

```bash
# 1. Fork & clone your fork locally
git clone <your-fork-url> cortex-dev
cd cortex-dev

# 2A. Test against a throwaway single-project repo (submodule mode)
mkdir /tmp/cortex-test-single && cd /tmp/cortex-test-single
git init
git submodule add <path-to-your-fork> cortex
./cortex/setup.sh --tool claude       # or copilot/cursor/agents

# 2B. Test against a throwaway multi-repo workspace (standalone clone mode — no parent git repo)
mkdir /tmp/cortex-test-workspace && cd /tmp/cortex-test-workspace
git clone <path-to-your-fork> cortex
./cortex/setup.sh --tool claude --workspace

# 3. Check that the bootstrap file was generated correctly
cat CLAUDE.md   # (or .github/copilot-instructions.md, etc.)

# 4. Iterate: edit cortex/, re-run setup.sh, re-check
```

**Why test both modes?** Because they exercise different code paths in `setup.sh`: submodule + single project, vs standalone clone + workspace. A change that works in one may break the other.

### Validation tools

```bash
./cortex/bin/validate-overlays.sh           # checks overlay file integrity (host projects)
bash bin/check-english.sh                   # in the cortex repository: tracked content is English (CI gate)
```

If you change a base file under `cortex/agents/`, run `validate-overlays.sh` against any host project that uses overlays — your rename may break their files.

## 📥 What contributions are welcome?

| Type | Example | Difficulty |
|---|---|---|
| 🐛 Bug fix | Bash typo in `setup.sh`, broken doc link | Easy |
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

### Bash (`setup.sh` and any future scripts)

- `set -eo pipefail` at top
- Quote all variable expansions (`"$VAR"`, not `$VAR`)
- Use `[[ ... ]]` for conditionals
- Print colored output via the existing `${GREEN}` / `${RED}` / `${BLUE}` / `${YELLOW}` / `${NC}` variables
- Test with `bash -n script.sh` (syntax check) and a real run before committing

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

1. **Branch from `main`** with a descriptive name: `feat/redis-capability`, `fix/setup-workspace-template`, `docs/extending-layers-examples`
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
- `<scope>` *(optional)* — component or layer affected (`runtime`, `roles`, `capabilities`, `setup`, `adr`, `docs`, `extending-layers`, …)
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
🐛 fix(setup): use workspace template when --workspace flag is set
📝 docs(extending-layers): add example for personality character overlay
📐 docs(adr): mark ADR-001 as Accepted
♻️ refactor(setup): replace hardcoded heredoc with template loader
✅ test(validate-overlays): cover non-overridable characters.md case
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
| **Major** (1.0.0) | Breaking change to the layer cascade contract, role schema, or `setup.sh` CLI |
| **Minor** (0.x.0) | New role/capability/theme/workflow; new ADR-anchored feature |
| **Patch** (0.x.y) | Bug fix, docs improvement, internal refactor |

Release process (maintainers only). A release is a **stack of pull requests onto an integration branch**, not a series of pushes to `main`:

1. Cut `release/{version}` from `main` and push it — it gets no pull request of its own until the end
2. Feature pull requests target `release/{version}`; one that builds on another is stacked on it, and a contributor's pull request opened against `main` is retargeted. Each adds its entry under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md)
3. The release artefacts come **last**, in a pull request stacked on top of everything else: `changelog/{version}.md`, the detailed, narrated release note, and the `{version}` section of `CHANGELOG.md` (Keep a Changelog) that replaces the `[Unreleased]` entries and links to that note. Last, because they rewrite the `[Unreleased]` anchor every feature pull request also touches. `CHANGELOG.md` is the single source of truth for versions; **no version number lives anywhere else** (README, docs, …) to avoid stale copies
4. Merge the stack in order — with a **merge commit** for any pull request that has another stacked on it, see [the stacking rules](docs/process/adr-implementation.md#2-stacking-the-phases)
5. Mark the release on `release/{version}`: the final date and `_(Released)_` on its `CHANGELOG.md` heading
6. Merge `release/{version}` into `main`
7. Publish a **GitHub Release** named `{version}` that creates the tag `{version}` on `main` — **no `v` prefix**, like every tag since 0.1.0 — with the release note as its body. From the command line: `gh release create {version} --target main --title {version} --notes-file changelog/{version}.md`

### Release names

Every release carries a **name** — a short phrase that says what the release is about, never a generic label: `Marginalia` for the comment-discipline release, `Trapdoor` for the security traps, `Reuse before create` for a patch. It appears in exactly two places:

- the `CHANGELOG.md` heading — `## [0.9.0] - 2026-09-23 — Beware of the Leopard`
- the release note's title — `# 🚀 Cortex v0.9.0 — Beware of the Leopard`

The note then opens with an **epigraph**: a short quote that makes the release's point better than its summary, attributed to whoever says it — so far always someone from *The Hitchhiker's Guide to the Galaxy*. A patch gets its own name, like any other release. The name and the `v` belong to the note's title only: the tag and the GitHub Release carry the bare version (`0.9.0`). Every release since 0.1.0 has followed this; it is written down here so it outlives the memory of whoever started it.

## 🧪 Testing checklist before opening a PR

- [ ] Markdown lints cleanly (no broken links, no malformed tables)
- [ ] If you touched `setup.sh`: tested `--tool {copilot,cursor,claude,agents}` × `{single, --workspace}` matrix
- [ ] If you added overlays in `templates/` or examples: ran `validate-overlays.sh` mentally or in a host project
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
