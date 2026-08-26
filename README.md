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

Overlays are **additive** by default (rules are appended to the base), except for `workflows/` which use **replacement** (sequence-level override). See [docs/extending-layers.md](docs/extending-layers.md) for the practical guide and [ADR-001](docs/adr/ADR-001-layered-overrides.md) for the formal contract.

## ⚙️ The Runtime

[`cortex-runtime`](runtime/README.md) is the **deployable engine**. It compiles the ADR-001 cascade into an executable resolver and wraps it in a thin, domain-agnostic HTTP API that drives an agentic loop — so the same spec you use at design time can run as a 24/7 service ([ADR-002](docs/adr/ADR-002-cortex-runtime.md)).

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
cd runtime && pip install -e ".[serve]"
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
├── setup.sh                           # Installation script (design-time spec)
├── bin/
│   └── validate-overlays.sh           # Overlay integrity checker (CI-friendly)
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
├── runtime/                           # ── ⚙️ cortex-runtime — the deployable engine ──
│   ├── cortex_runtime/                # resolver, agnostic API, agentic loop, StateStore,
│   │                                  #   security gate, job queue, model backends
│   ├── tests/                         # unit + integration suite
│   └── docs/                          # e.g. claude-cli-setup.md
│
├── mcp/                               # MCP servers (e.g. Jira Service Management)
├── deploy/                            # Docker image, compose stack, Traefik, DBHub profile
│
├── docs/
│   ├── getting-started.md             # Step-by-step install (design-time spec)
│   ├── extending-layers.md            # Practical guide for overlays (the cascade)
│   ├── creating-a-theme.md            # Guide for creating a personality theme
│   ├── adr/                           # Architecture Decision Records (ADR-001 … ADR-005)
│   └── api/                           # OpenAPI spec + Postman collection
│
└── changelog/                         # Per-version release notes (index: CHANGELOG.md)
```

> **Note on overlays:** the `agents/{roles,capabilities,personalities,workflows}/` trees also exist (mirrored) in host projects under `{workspace}/agents/...` and `{service}/agents/...` — those are the override locations, not part of cortex itself.

## 🔧 Installation

> This section covers the **design-time spec**. To run the engine, jump to [The Runtime](#-the-runtime).

Cortex can be consumed in **two ways**, depending on how your project is structured. Both are first-class — pick the one that fits your repo layout.

| Mode | When to use | Workspace must be a git repo? |
|---|---|---|
| **Submodule** | Single project (one git repo) or monorepo containing multiple services | ✅ Yes |
| **Standalone clone** | Multi-repo workspace where each service is its own git repo (cortex sits as a peer) | ❌ No |

### Option 1A: Submodule (single project or monorepo)

```bash
# From inside your project's git repo
git submodule add <cortex-url> cortex
./cortex/setup.sh                       # single project
./cortex/setup.sh --workspace           # monorepo with multiple services
```

Update cortex later: `git submodule update --remote cortex`.

### Option 1B: Standalone clone (multi-repo workspace)

When your workspace is just a folder containing several independent git repos (e.g. `backend/`, `frontend/`, `infra/`), cortex doesn't need to be a submodule of anything — it lives next to them as a sibling clone.

```bash
# In your workspace folder (not necessarily a git repo)
# workspace/
# ├── cortex/         ← cloned here (not a submodule)
# ├── service-a/      ← independent repo
# └── service-b/      ← independent repo

git clone <cortex-url> cortex
./cortex/setup.sh --workspace
# The script interactively asks for the names of services to initialize.
# It creates project-overview.md and project-context.md in each service
# with the correct @alias pre-filled.
```

Update cortex later: `cd cortex && git pull`.

### Common options (both modes)

```bash
./cortex/setup.sh --tool claude          # generate CLAUDE.md (vs Copilot's .github/copilot-instructions.md by default)
./cortex/setup.sh --no-personality       # neutral professional agents (no theme)
./cortex/setup.sh --theme star-wars      # use a specific theme
```

Each service declares its `@alias` in its `project-overview.md`. To target a service in a prompt:
```
@backend Add a pagination endpoint on /users
@frontend Create a sortable table component
```
If no alias is mentioned, Cortex infers the service from the active file context.

### Option 2: Manual

1. Copy the appropriate bootstrap template for your AI tool into the right location:
   - **GitHub Copilot**: `cortex/templates/bootstrap-instructions.md` → `.github/copilot-instructions.md`
   - **Cursor**: `cortex/templates/bootstrap-instructions.md` → `.cursor/rules/cortex.mdc`
   - **Claude Code**: `cortex/templates/bootstrap-instructions.md` → `CLAUDE.md`
   - **Codex / other**: `cortex/templates/bootstrap-instructions.md` → `AGENTS.md`

   For workspace mode, use `bootstrap-instructions-workspace.md` instead.
2. Copy `cortex/templates/project-overview.md.template` → `project-overview.md` and fill in the vision
3. Copy `cortex/templates/project-context.md.template` → `project-context.md` and fill in the stack
4. Invoke an agent by mentioning the desired role or character name in your prompt

## 📚 Documentation

**The spec (design-time)**
- [**Getting Started**](docs/getting-started.md) — step-by-step installation guide (single project & workspace)
- [**Extending layers**](docs/extending-layers.md) — overlay your project's rules onto roles, capabilities, personalities, and workflows
- [**Creating a theme**](docs/creating-a-theme.md) — customize the tone and style of agents

**The runtime (the engine)**
- [**cortex-runtime**](runtime/README.md) — the deployable engine: API, agentic loop, backends, state, security, async
- [**Deployment**](deploy/README.md) — Docker/compose stack, Traefik, security setup (admin CLI, HMAC secrets, token minting)
- [**API reference**](docs/api/) — OpenAPI spec + Postman collection
- [**Claude CLI setup**](runtime/docs/claude-cli-setup.md) — run the runtime against a Pro/Max subscription

**Design & contribution**
- [**Architecture Decision Records**](docs/adr/) — the *why* behind the framework and the runtime (ADR-001 … ADR-005)
- [**Contributing**](CONTRIBUTING.md) — how to add roles, capabilities, themes, workflows, or fix bugs

## 📋 Changelog

The full, versioned history lives in **[`CHANGELOG.md`](CHANGELOG.md)** (Keep a Changelog format) — the single source of truth for versions. Each entry links to its detailed, narrated release note in [`changelog/`](changelog/).

## 🎯 Philosophy

**The spec**
- **Zero project dependency**: roles are stack-agnostic, the stack lives in `project-context.md`
- **Plug & Play**: `setup.sh` and you're ready — single project mode or multi-project workspace
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
