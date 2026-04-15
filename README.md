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

## 📁 Structure

```
cortex/
├── README.md                          # This file
├── setup.sh                           # Installation script
├── templates/
│   ├── copilot-instructions.md              # Bootstrap — single project mode
│   ├── copilot-instructions-workspace.md    # Bootstrap — multi-project workspace mode
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
    └── 0.1.0.md                           # Current release
```

## 🔧 Installation

### Option 1: Automatic script (recommended)

```bash
# Add as a Git submodule
git submodule add <cortex-url> cortex

# Install — single project (H2G2 theme by default)
./cortex/setup.sh

# Without personality
./cortex/setup.sh --no-personality

# With a specific theme
./cortex/setup.sh --theme star-wars
```

### Workspace mode — multi-projects

For a workspace containing multiple services/repos (microservices, monorepo, multi-repo VSCode):

```bash
# Place cortex in the parent folder (not necessarily a git repo)
# workspace/
# ├── cortex/
# ├── service-a/
# └── service-b/

./cortex/setup.sh --workspace
# The script interactively asks for the names of services to initialize
# It creates project-overview.md and project-context.md in each service
# with the correct @alias pre-filled
```

Each service declares its `@alias` in its `project-overview.md`. To target a service in a prompt:
```
@backend Add a pagination endpoint on /users
@frontend Create a sortable table component
```
If no alias is mentioned, Cortex infers the service from the active file context.

### Option 2: Manual

1. Copy the appropriate template for your AI tool into the right location:
   - **GitHub Copilot**: `cortex/templates/copilot-instructions.md` → `.github/copilot-instructions.md`
   - **Cursor**: `cortex/templates/copilot-instructions.md` → `.cursor/rules/cortex.mdc`
   - **Claude Code**: `cortex/templates/copilot-instructions.md` → `CLAUDE.md`
   - **Codex / other**: `cortex/templates/copilot-instructions.md` → `AGENTS.md`
2. Copy `cortex/templates/project-overview.md.template` → `project-overview.md` and fill in the vision
3. Copy `cortex/templates/project-context.md.template` → `project-context.md` and fill in the stack
4. Invoke an agent by mentioning the desired role or character name in your prompt

## 📚 Documentation

- [**Getting Started**](docs/getting-started.md) — step-by-step installation guide (single project & workspace)
- [**Creating a theme**](docs/creating-a-theme.md) — customize the tone and style of agents

## 📋 Changelog

> Latest release: **[v0.1.0](changelog/0.1.0.md)** — First stable foundation: 3-layer architecture, 15 agent roles with behavioral rules & anti-patterns, H2G2 theme, dispatch protocol, and 9 capability files.

All releases are documented in the [`changelog/`](changelog/) directory.

## 🎯 Philosophy

- **Zero project dependency**: roles are stack-agnostic, the stack lives in `project-context.md`
- **Plug & Play**: `setup.sh` and you're ready — single project mode or multi-project workspace
- **Composable**: role + capabilities + personality + context + workflow = complete agent
- **Two context files**: `project-overview.md` (vision & business) + `project-context.md` (stack & conventions) — separated to never mix the WHAT and the HOW
- **Loadable capabilities**: `capabilities/` cards are reusable across projects, automatically loaded by the PM based on the active role and project stack
- **Multi-project**: workspace mode with `@alias` per service — Cortex detects the active service from the prompt or open files
- **Scalable**: add your own roles, capabilities, themes, workflows or services

> *"Documentation is like the developer's tea: nobody wants it until they desperately need it."* — Arthur Dent
