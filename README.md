# Cortex

<p align="center">
  <img src="assets/logo.png" alt="Cortex — AI Agent Framework" width="200" height="300" />
</p>

Cortex is a framework of specialized AI agents, ready to integrate into any project.

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

## 📁 Structure

```
cortex/
├── README.md                          # This file
├── setup.sh                           # Installation script
├── templates/
│   ├── bootstrap-instructions.md            # Bootstrap — single project mode (any AI tool)
│   ├── bootstrap-instructions-workspace.md  # Bootstrap — multi-project workspace mode
│   ├── project-overview.md.template         # Template: project overview (vision & business)
│   ├── project-context.md.template          # Template: technical context
│   └── workflow.md.template                 # Template for creating a project workflow
│
├── agents/
│   ├── roles/                         # Layer 1: Business roles (stack-agnostic)
│   │   ├── prompt-manager.md         # Entry point (root, always active)
│   │   ├── engineering/               # Design & technical delivery
│   │   │   ├── architect.md
│   │   │   ├── lead-backend.md
│   │   │   ├── lead-frontend.md
│   │   │   ├── dba.md
│   │   │   ├── platform-engineer.md
│   │   │   ├── performance-engineer.md
│   │   │   ├── consultant-platform.md
│   │   │   └── qa-automation.md
│   │   ├── product/                   # Product vision & business
│   │   │   ├── product-owner.md
│   │   │   └── business-analyst.md
│   │   ├── security-compliance/       # Security & compliance
│   │   │   ├── security-engineer.md
│   │   │   └── compliance-officer.md
│   │   ├── data/                      # Data & analytics
│   │   │   └── data-analyst.md
│   │   └── communication/             # Content & documentation
│   │       └── tech-writer.md
│   │
│   ├── capabilities/                   # Layer 2: Loadable technical skills
│   │   ├── languages/
│   │   │   ├── php.md
│   │   │   └── typescript.md
│   │   ├── frameworks/
│   │   │   └── symfony.md
│   │   ├── infrastructure/
│   │   │   ├── docker.md
│   │   │   └── kubernetes.md
│   │   ├── databases/
│   │   │   ├── mysql.md
│   │   │   ├── postgresql.md
│   │   │   └── mongodb.md
│   │   └── security/
│   │       └── owasp.md
│   │
│   ├── personalities/                 # Layer 3: Personality themes
│   │   └── h2g2/                      # H2G2 theme (The Hitchhiker's Guide)
│   │       ├── theme.md
│   │       ├── characters.md
│   │       └── {character}.md        # Individual personality card
│   │
│   └── workflows/                     # Layer 4: Multi-agent orchestration templates
│       ├── engineering/               # Development & technical
│       │   └── feature-development.md
│       ├── intelligence/              # Research & analysis
│       │   └── tech-watch.md
│       └── README.md
│
└── docs/
│   ├── getting-started.md             # Step-by-step installation guide
│   └── creating-a-theme.md            # Guide for creating a theme
│
└── changelog/                             # Release notes
    ├── 0.1.0.md                           # First stable foundation
    └── 0.2.0.md                           # Layered overrides + ADRs
```

> **Note on overlays:** the `agents/{roles,capabilities,personalities,workflows}/` trees described above also exist (mirrored) in host projects under `{workspace}/agents/...` and `{service}/agents/...` — those are the override locations, not part of cortex itself.

## 🔧 Installation

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

- [**Getting Started**](docs/getting-started.md) — step-by-step installation guide (single project & workspace)
- [**Extending layers**](docs/extending-layers.md) — overlay your project's rules onto roles, capabilities, personalities, and workflows
- [**Creating a theme**](docs/creating-a-theme.md) — customize the tone and style of agents
- [**Architecture Decision Records**](docs/adr/) — the *why* behind the framework's design
- [**Contributing**](CONTRIBUTING.md) — how to add roles, capabilities, themes, workflows, or fix bugs

## 📋 Changelog

> Latest release: **[v0.2.0](changelog/0.2.0.md)** — Layered overrides: cascade resolution for all agent layers, ADR-001, validation tooling, contributor guide.
>
> Previous: **[v0.1.0](changelog/0.1.0.md)** — First stable foundation.

All releases are documented in the [`changelog/`](changelog/) directory.

## 🎯 Philosophy

- **Zero project dependency**: roles are stack-agnostic, the stack lives in `project-context.md`
- **Plug & Play**: `setup.sh` and you're ready — single project mode or multi-project workspace
- **Composable**: role + capabilities + personality + context + workflow = complete agent
- **Two context files**: `project-overview.md` (vision & business) + `project-context.md` (stack & conventions) — separated to never mix the WHAT and the HOW
- **Loadable capabilities**: `capabilities/` cards are reusable across projects, automatically loaded by the PM based on the active role and project stack
- **Multi-project**: workspace mode with `@alias` per service — Cortex detects the active service from the prompt or open files
- **Layered overrides**: every layer can be extended at workspace or service level via overlays — host projects teach Cortex their conventions without forking ([ADR-001](docs/adr/ADR-001-layered-overrides.md))
- **Append-only ADRs**: significant design decisions are documented and traceable in [docs/adr/](docs/adr/)
- **Scalable**: add your own roles, capabilities, themes, workflows or services

> *"Documentation is like the developer's tea: nobody wants it until they desperately need it."* — Arthur Dent
