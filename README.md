# Cortex

<p align="center">
  <img src="assets/logo.png" alt="Cortex — AI Agent Framework" width="200" height="300" />
</p>

Cortex is a framework of specialized AI agents that integrates into any project. It has **two complementary halves**:

- **The spec** — a portable, host-agnostic Markdown cascade (`agents/…`) that any AI coding tool (Claude Code, Copilot, Cursor, Codex…) reads as its system instructions. This is the design-time layer.
- **The runtime** — [`cortex-runtime`](runtime/README.md), a deployable engine that *executes* that spec as a service: a thin agnostic API, an agentic loop, persistent state, an optional security perimeter, and asynchronous execution.

> **The runtime CONSUMES the spec. The spec NEVER depends on the runtime.** ([ADR-002](docs/adr/ADR-002-cortex-runtime.md))
> The Markdown cascade stays a pure, portable knowledge layer — you can adopt the spec alone and never touch the engine.

## 🚀 Concept

Each agent is composed of **5 independent layers**:

```
┌─────────────────────────────────┐
│   project-overview.md           │  ← Vision, stakeholders, business constraints
│   project-context.md            │  ← Stack, conventions, tools
├─────────────────────────────────┤
│   capabilities/{techno}.md      │  ← Loadable technical skills (PHP, Docker…)
├─────────────────────────────────┤
│   personalities/{theme}/        │  ← Optional personality (e.g. H2G2)
├─────────────────────────────────┤
│   roles/{role}.md               │  ← Generic business skills
├─────────────────────────────────┤
│   workflows/{context}.md        │  ← Multi-agent orchestration templates
└─────────────────────────────────┘
```

> *"Let's explain this as if Earth had just been destroyed and we had to start from scratch."* — Arthur Dent

| Layer | Answers | Example |
|---|---|---|
| `roles/` | **WHAT** to do | "A lead backend structures, reviews, mentors" |
| `capabilities/` | **WHAT I CAN DO** | "In PHP: PSR-12, dependency injection..." |
| `personalities/` | **WHO** you are | "Hactar, methodical, elegant" |
| `project-overview.md` | **WHY** you work | "Mission: B2B platform, stakeholders, business constraints" |
| `project-context.md` | **WHERE / HOW** you work | "This project: Symfony 7.2, PHP 8.3, MySQL 8" |
| `workflows/` | **IN WHAT ORDER and WITH WHOM** | "Feature dev: architect → backend → QA → security → doc" |

This separation allows:
- Changing **personality** (H2G2, Star Wars, corporate…) without touching the skills
- Reusing **roles** across any tech stack
- Sharing **best practices** for a technology across all projects that use it
- Customizing the **project context** without modifying the agents
- Defining reusable **workflows** (generic in cortex) or project-specific (in the host project via `agents/workflows/`)

### 🪜 Layered overrides (cascade)

Every layer (`roles/`, `capabilities/`, `personalities/`, `workflows/`) supports a **3-tier cascade**: a host project can extend any base file with an overlay at workspace or service level, without forking cortex itself.

```
{service}/agents/{layer}/...                    ← priority 1 (most specific)
{workspace_root}/agents/{layer}/...             ← priority 2 (workspace mode only)
cortex/agents/{layer}/...                       ← priority 3 (default, ships with cortex)
```

`cortex/` names the spec: the directory that `spec` names in the project's `cortex.local.toml`, written by `cortex sync` (see [Installation](#-installation)). It is a name, not necessarily a directory of the project.

Overlays are **additive** by default (rules are appended to the base), except for `workflows/` which use **replacement** (sequence-level override). See [docs/extending-layers.md](docs/extending-layers.md) for the practical guide and [ADR-001](docs/adr/ADR-001-layered-overrides.md) for the formal contract.

## ⚙️ The Runtime

[`cortex-runtime`](runtime/README.md) is the **deployable engine**. It consumes [`cortex-core`](core/README.md) — the one implementation of the ADR-001 cascade in code ([ADR-007](docs/adr/ADR-007-cortex-core.md)) — and wraps it in a thin, domain-agnostic HTTP API that drives an agentic loop — so the same spec you use at design time can run as a 24/7 service ([ADR-002](docs/adr/ADR-002-cortex-runtime.md)).

Everything below the API is **swappable and opt-in** — you run only what you need:

| Capability | What it does | ADR | How to enable |
|---|---|---|---|
| **Agnostic API** | `POST /run` (+ project aliases), `/resolve`, `/reply`, `/webhook/{source}`; read-only monitoring `GET /runs`; `/health` + `/ready` | [002](docs/adr/ADR-002-cortex-runtime.md) | always on |
| **Model backends** | `demo` (no key/CLI), `claude-cli` (Pro/Max subscription), `anthropic-api` (Console key) | 002 | `CORTEX_BACKEND` |
| **Persistence** | `StateStore` for conversation state, run history & metrics, audit log — InMemory / SQLite / PostgreSQL | [003](docs/adr/ADR-003-persistence-state-layer.md) | `CORTEX_DB` / `CORTEX_DATABASE_URL` |
| **Security perimeter** | Bearer + HMAC auth, tenant registry, per-tenant budget caps, rate-limiting, admin CLI | [004](docs/adr/ADR-004-api-security.md) | `CORTEX_AUTH=on` |
| **Async execution** | Job queue, `POST /run` → `202` + poll, readiness `/ready`, graceful drain | [005](docs/adr/ADR-005-execution-model-resilience.md) | `CORTEX_ASYNC=on` |

**Quick start** (no key, no CLI — runs the whole wire):

```bash
cd runtime && pip install -e ../core -e ".[serve]"   # cortex-core first: the runtime depends on it
CORTEX_BACKEND=demo python -m cortex_runtime      # serves on 127.0.0.1:8000
```

Or bring up the container stack (runtime + optional Postgres/DBHub, behind Traefik):

```bash
cd deploy && docker compose up -d                 # see deploy/README.md
```

Full engine docs live in [runtime/README.md](runtime/README.md); deployment & security setup in [deploy/README.md](deploy/README.md); the HTTP contract in [docs/api/](docs/api/) (OpenAPI + Postman).

## 📁 Structure

```
cortex/
├── README.md                          # This file
├── install.sh                         # One-line install of the `cortex` command (Linux, macOS)
├── install.ps1                        # One-line install of the `cortex` command (Windows)
├── bin/
│   ├── check-english.sh               # English-only check (CI)
│   └── setup-labels.sh                # GitHub labels for multi-phase ADRs
│
├── templates/
│   ├── bootstrap-instructions.md            # Bootstrap — single project mode (any AI tool)
│   ├── bootstrap-instructions-workspace.md  # Bootstrap — multi-project workspace mode
│   ├── project-overview.md.template         # Template: project overview (vision & business)
│   ├── project-context.md.template          # Template: technical context
│   └── workflow.md.template                 # Template for creating a project workflow
│
├── agents/                            # ── The spec (portable Markdown cascade) ──
│   ├── roles/                         # Layer 1: Business roles (stack-agnostic)
│   │   ├── prompt-manager.md          # Entry point (root, always active)
│   │   ├── engineering/               # architect, lead-backend/frontend, dba, platform…
│   │   ├── product/                   # product-owner, business-analyst
│   │   ├── security-compliance/       # security-engineer, compliance-officer
│   │   ├── data/                      # data-analyst
│   │   └── communication/             # tech-writer
│   │
│   ├── capabilities/                  # Layer 2: Loadable technical skills
│   │   ├── languages/                 # php, typescript
│   │   ├── frameworks/                # symfony, vue, starlight
│   │   ├── infrastructure/            # docker, kubernetes
│   │   ├── databases/                 # mysql, postgresql, mongodb
│   │   ├── search/                    # opensearch
│   │   ├── testing/                   # component-testing, e2e-testing
│   │   ├── practices/                 # code-comments
│   │   └── security/                  # owasp
│   │
│   ├── personalities/                 # Layer 3: Personality themes
│   │   └── h2g2/                      # H2G2 theme (The Hitchhiker's Guide)
│   │
│   └── workflows/                     # Layer 4: Multi-agent orchestration templates
│       ├── engineering/               # feature-development
│       └── intelligence/              # tech-watch
│
├── core/                              # ── cortex-core — the cascade in code (ADR-007) ──
│   ├── cortex_core/                   # resolution, merge semantics, capability catalog,
│   │                                  #   prompt assembly — standard library only
│   └── tests/                         # runs on Python 3.9+ with nothing installed
│
├── cli/                               # ── the `cortex` command (ADR-008) ──
│   ├── cortex_cli/                    # init, sync, validate — built into a native binary
│   └── tests/
│
├── runtime/                           # ── ⚙️ cortex-runtime — the deployable engine ──
│   ├── cortex_runtime/                # agnostic API, agentic loop, StateStore,
│   │                                  #   security gate, job queue, model backends
│   ├── tests/                         # unit + integration suite
│   └── docs/                          # e.g. claude-cli-setup.md
│
├── mcp/                               # MCP servers (e.g. Jira Service Management)
├── deploy/                            # Docker image, compose stack, Traefik, DBHub profile
│
├── docs/
│   ├── getting-started.md             # Step-by-step install (design-time spec)
│   ├── migrating-to-the-binary.md     # From a git submodule or clone to the `cortex` command
│   ├── extending-layers.md            # Practical guide for overlays (the cascade)
│   ├── creating-a-theme.md            # Guide for creating a personality theme
│   ├── adr/                           # Architecture Decision Records (ADR-001 … ADR-008)
│   └── api/                           # OpenAPI spec + Postman collection
│
└── changelog/                         # Per-version release notes (index: CHANGELOG.md)
```

> **Note on overlays:** the `agents/{roles,capabilities,personalities,workflows}/` trees also exist (mirrored) in host projects under `{workspace}/agents/...` and `{service}/agents/...` — those are the override locations, not part of cortex itself.

## 🔧 Installation

> This section covers the **design-time spec**. To run the engine, jump to [The Runtime](#-the-runtime).

Cortex is one command, `cortex`, installed once per machine. It needs no Python and no Bash, and no copy of Cortex inside your projects: the spec lives once on the machine, and each project pins the version it uses ([ADR-008](docs/adr/ADR-008-cortex-binary.md)).

### 1. Install the `cortex` command (once per machine)

```bash
curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh              # Linux, macOS
curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh -s -- 1.0.0  # a given version
```

```powershell
irm https://raw.githubusercontent.com/adorey/cortex/main/install.ps1 | iex                    # Windows PowerShell
```

The binary goes into `~/.cortex/bin` (`%USERPROFILE%\.cortex\bin` on Windows): `install.ps1` adds that directory to your user `PATH`, `install.sh` prints the line to add to your shell profile. When another `cortex` command comes first on `PATH`, the scripts install it as `cortex-ai` instead; `--name cortex` (`-Name cortex` for `install.ps1`) forces the name. Running a script again upgrades the binary. Built for Linux x86_64 and aarch64 (glibc 2.28 or later), macOS on Apple silicon and Windows x86_64.

The spec lives in the store, `~/.cortex/versions/X.Y.Z`: one read-only directory per version, filled on demand — the binary's own version from itself, any other downloaded and checked against its release's `SHA256SUMS`. `$CORTEX_HOME` moves `~/.cortex` elsewhere.

### 2. Make a project a Cortex project

```bash
cd my-project/
cortex init                         # H2G2 theme, GitHub Copilot's .github/copilot-instructions.md
cortex init --tool claude           # CLAUDE.md — or cursor, agents, custom --instructions-file PATH
cortex init --no-personality        # neutral professional agents (no theme)
```

`cortex init` writes `cortex.toml` — committed: the Cortex `version` the project uses and the team's `theme` — adds `cortex.local.toml` to `.gitignore` and runs `cortex sync`. It then writes the AI tool's instructions file, `project-overview.md` and `project-context.md` when they are missing; an existing instructions file is kept unless `--force`, which keeps the old one as `FILE.bak`. [Getting Started](docs/getting-started.md) goes through every option.

### 3. After a clone: `cortex sync`

Each developer runs `cortex sync` in a fresh clone, as they would `npm install`. It writes `spec` in `cortex.local.toml`, which git ignores: where the spec is on this machine. By default nothing of the spec enters the project — the AI tool reads it in place, and `cortex/` in the instructions, the docs and every overlay's `Base:` header names that directory.

A tool that needs the spec inside the project gets it with `cortex sync --link` (`cortex/` links to the store; a junction on Windows) or `--copy` (a read-only copy in `cortex/`). `sync = "link"` or `sync = "copy"` in `cortex.toml` makes it the team's default. Which mode a tool needs is measured, not assumed: so far Claude Code only, which asks once per session for permission to read the store, and needs nothing in `copy` mode. `claude_access = true` in `cortex.toml` — offered by `cortex init --tool claude` — has `cortex sync` let it read the store without asking; `cortex sync --claude-access` does it for you alone. The table is in [Moving to the `cortex` binary](docs/migrating-to-the-binary.md).

### Workspace mode (several services)

In a monorepo, or a folder holding several repositories, run `cortex init --workspace` at the workspace root. Nothing of Cortex sits next to the services any more:

```bash
cd workspace/
cortex init --workspace --service backend --service apps/frontend
```

Each `--service` is a folder of the workspace and gets its own `project-overview.md` and `project-context.md`, with the folder's name as its `@alias` (`apps/frontend` → `@frontend`). On a terminal with no `--service`, the command asks for the services. When `agents/` is its own git repository, the team's `agents/project-overview.md` and `agents/project-context.md` are scaffolded too ([ADR-006](docs/adr/ADR-006-workspace-shareable-repo.md)).

To target a service in a prompt, use its alias:
```
@backend Add a pagination endpoint on /users
@frontend Create a sortable table component
```
If no alias is mentioned, Cortex infers the service from the active file context.

### Validate and upgrade

```bash
cortex validate              # overlay checks: 0 clean, 1 errors, 2 cannot run
cortex validate --strict     # warnings fail too — what CI runs
```

In CI: install the binary of the version `cortex.toml` pins, then `cortex sync` and `cortex validate --strict` — [the migration guide](docs/migrating-to-the-binary.md#5-ci) has the lines.

To move a project to another Cortex version, change `version` in `cortex.toml`, then run `cortex sync`. To upgrade the binary, run the install script again. A binary serves every version from 1.0.0 up to its own, and refuses a project pinned to a newer one with the command that upgrades it.

### Coming from a git submodule or clone

`cortex init` refuses while `cortex/` is a git submodule or a clone of Cortex, and prints the commands that remove it. [Moving to the `cortex` binary](docs/migrating-to-the-binary.md) covers the switch.

## 📚 Documentation

**The spec (design-time)**
- [**Getting Started**](docs/getting-started.md) — step-by-step installation guide (single project & workspace)
- [**Moving to the `cortex` binary**](docs/migrating-to-the-binary.md) — from a git submodule or clone of Cortex, and which sync mode each AI tool needs
- [**Extending layers**](docs/extending-layers.md) — overlay your project's rules onto roles, capabilities, personalities, and workflows
- [**Creating a theme**](docs/creating-a-theme.md) — customize the tone and style of agents

**The runtime (the engine)**
- [**cortex-runtime**](runtime/README.md) — the deployable engine: API, agentic loop, backends, state, security, async
- [**Deployment**](deploy/README.md) — Docker/compose stack, Traefik, security setup (admin CLI, HMAC secrets, token minting)
- [**API reference**](docs/api/) — OpenAPI spec + Postman collection
- [**Claude CLI setup**](runtime/docs/claude-cli-setup.md) — run the runtime against a Pro/Max subscription

**Design & contribution**
- [**Architecture Decision Records**](docs/adr/) — the *why* behind the framework and the runtime (ADR-001 … ADR-008)
- [**Contributing**](CONTRIBUTING.md) — how to add roles, capabilities, themes, workflows, or fix bugs

## 📋 Changelog

The full, versioned history lives in **[`CHANGELOG.md`](CHANGELOG.md)** (Keep a Changelog format) — the single source of truth for versions. Each entry links to its detailed, narrated release note in [`changelog/`](changelog/).

## 🎯 Philosophy

**The spec**
- **Zero project dependency**: roles are stack-agnostic, the stack lives in `project-context.md`
- **Plug & Play**: one install per machine, `cortex init` per project — single project mode or multi-project workspace
- **Composable**: role + capabilities + personality + context + workflow = complete agent
- **Two context files**: `project-overview.md` (vision & business) + `project-context.md` (stack & conventions) — separated to never mix the WHAT and the HOW
- **Loadable capabilities**: `capabilities/` cards are reusable across projects, automatically loaded by the PM based on the active role and project stack
- **Multi-project**: workspace mode with `@alias` per service — Cortex detects the active service from the prompt or open files
- **Layered overrides**: every layer can be extended at workspace or service level via overlays — host projects teach Cortex their conventions without forking ([ADR-001](docs/adr/ADR-001-layered-overrides.md))

**The runtime**
- **The firewall**: the runtime consumes the spec; the spec never depends on the runtime — the Markdown cascade stays portable ([ADR-002](docs/adr/ADR-002-cortex-runtime.md))
- **Domain-agnostic**: the engine keys everything on an opaque `subject` — it never knows it is dealing with a "ticket", a dashboard, or a cron key
- **Swappable everything**: model backend, state store, and secret provider all sit behind interfaces — from a keyless `demo` to Postgres + Anthropic API in production
- **Opt-in hardening**: security and async are off by default and switch on per environment — dev stays frictionless, prod gets the perimeter

**Both**
- **Append-only ADRs**: significant design decisions are documented and traceable in [docs/adr/](docs/adr/)
- **Scalable**: add your own roles, capabilities, themes, workflows, services — or backends behind the runtime interfaces

> *"Documentation is like the developer's tea: nobody wants it until they desperately need it."* — Arthur Dent
