# Getting Started — Cortex

> *"Don't Panic. And read this guide before doing anything else."* — Arthur Dent

This step-by-step guide covers both installation modes: **single project** and **multi-service workspace**.

---

## Prerequisites

- Git (to clone or submodule cortex itself)
- An AI coding tool: GitHub Copilot, Cursor, Claude Code, OpenAI Codex, or any tool that supports a custom system instructions file
- Either:
  - A Git repository (single project or monorepo) — cortex will be added as a **submodule**, **or**
  - A workspace folder containing several independent repos — cortex will sit alongside them as a **standalone clone** (the workspace itself doesn't need to be a git repo)

> **Which installation mode applies to you?** See the table at the top of [README.md → Installation](../README.md#installation). TL;DR: submodule for one-repo projects, standalone clone for multi-repo workspaces.

---

## 🚀 Mode 1 — Single project (one git repo)

### Step 1 — Add Cortex to your project

For a single-project git repo, **submodule** is the recommended path: it pins cortex's version inside your repo.

```bash
cd my-project/
git submodule add <cortex-url> cortex
```

> If your project isn't a git repo and you don't want to add submodule machinery, you can also clone cortex directly: `git clone <cortex-url> cortex`. Updates then go through `cd cortex && git pull` instead of `git submodule update --remote`.

### Step 2 — Run the setup script

```bash
# Default: H2G2 theme, GitHub Copilot
./cortex/setup.sh

# Target a specific AI tool
./cortex/setup.sh --tool copilot   # → .github/copilot-instructions.md (default)
./cortex/setup.sh --tool cursor    # → .cursor/rules/cortex.mdc
./cortex/setup.sh --tool claude    # → CLAUDE.md
./cortex/setup.sh --tool agents    # → AGENTS.md (Codex, etc.)
./cortex/setup.sh --tool custom --instructions-file path/to/file

# Without personality (neutral professional agents)
./cortex/setup.sh --no-personality

# With a custom theme
./cortex/setup.sh --theme star-wars
```

The script automatically creates:
- The instructions file for your AI tool (path depends on `--tool`)
- `project-overview.md` — to fill in: vision, stakeholders, business flows
- `project-context.md` — to fill in: stack, conventions, tools

### Step 3 — Fill in the context files

**`project-overview.md`** (the WHAT and WHY):
```markdown
@alias: my-project

## 🎯 Mission
B2B contract management platform — SaaS, SME market.

## 👥 Stakeholders
- Company admin, Manager, Employee

## 🔄 Main flows
- Contract creation / validation / signing
- Role-based permission management

## ⚠️ Constraints
- GDPR, data hosted in EU
- SLA 99.9%
```

**`project-context.md`** (the HOW and WHERE):
```markdown
@alias: my-project

## 🛠️ Tech stack
- PHP 8.3 / Symfony 7.2
- MySQL 8.0
- Docker + Kubernetes

## 📐 Conventions
- PSR-12, DDD, REST API
- PHPUnit tests, minimum 80% coverage
```

### Step 4 — First interaction

In your AI tool, simply mention the desired agent in your prompt.

**With the H2G2 theme:**
```
@Oolon I want to add a pagination system on the /contracts API
```

**Without a theme (direct role):**
```
@prompt-manager I want to add a pagination system on the /contracts API
```

### Step 5 — How dispatch works

When you call `@Oolon` (or `@prompt-manager`):

1. **Analysis** — Oolon reformulates and clarifies your request
2. **Workflow** — Searches for a matching workflow in `agents/workflows/` (generic) then in your `agents/workflows/` (project)
3. **Dispatch** — Identifies the expert: *"Handing over to @Hactar (Lead Backend)"*
4. **Capabilities** — Loads the `capabilities/` files matching your stack (e.g. `php.md`, `symfony.md`, `mysql.md`)
5. **Delivery** — The expert responds with your project's full context

---

## 🏢 Mode 2 — Multi-service workspace

For a workspace containing multiple services. **Two flavors** depending on your repo layout:

### Flavor 2.A — Monorepo (one git repo, services as subfolders)

```
workspace/                ← single git repo
├── cortex/               ← shared, as Git submodule
├── api-backend/          ← subfolder of the monorepo
├── front-web/
└── notif-service/
```

### Flavor 2.B — Multi-repo workspace (each service is its own git repo)

```
workspace/                ← just a folder, NOT a git repo (or a separate one)
├── cortex/               ← standalone clone (NOT a submodule)
├── api-backend/          ← independent git repo
├── front-web/            ← independent git repo
└── notif-service/        ← independent git repo
```

### Step 1 — Place Cortex in the parent folder

**Flavor 2.A (monorepo):**

```bash
cd workspace/      # the monorepo root
git submodule add <cortex-url> cortex
```

**Flavor 2.B (multi-repo):**

```bash
cd workspace/      # any folder containing your service clones
git clone <cortex-url> cortex
# No submodule machinery — cortex is just a sibling clone of your services.
```

The rest of the steps are identical for both flavors.

### Step 2 — Run in workspace mode

```bash
./cortex/setup.sh --workspace
# The script asks for service names to initialise:
# → Service name (e.g. api-backend, front-web): api-backend
# → Service name (e.g. api-backend, front-web): front-web
# → Service name (e.g. api-backend, front-web):  ← empty entry to finish
```

Combine with `--tool` to target your AI tool:
```bash
./cortex/setup.sh --workspace --tool cursor
```

The script creates for each service:
- `{service}/project-overview.md` — with `@alias: {service}` pre-filled
- `{service}/project-context.md` — with `@alias: {service}` pre-filled

And at the workspace root (optional):
- `project-overview.md` — global vision (shared stakeholders, common constraints)
- `project-context.md` — shared conventions (linting, CI/CD, versioning)

### Step 3 — Copy the workspace bootstrap

Use the same `--tool` option as for single project mode. The script handles the correct file path automatically.

For manual setup:
```bash
# GitHub Copilot
cp cortex/templates/bootstrap-instructions-workspace.md .github/copilot-instructions.md
# Cursor
cp cortex/templates/bootstrap-instructions-workspace.md .cursor/rules/cortex.mdc
# Claude Code
cp cortex/templates/bootstrap-instructions-workspace.md CLAUDE.md
# Codex / other
cp cortex/templates/bootstrap-instructions-workspace.md AGENTS.md
```

### Step 4 — Fill in the context per service

Each service has its own context files. The `@alias` targets a specific service:

**`api-backend/project-overview.md`**:
```markdown
<!-- @alias: api-backend -->

## 🎯 Mission
REST API — contract management, JWT authentication
```

**`front-web/project-context.md`**:
```markdown
<!-- @alias: front-web -->

## 🛠️ Stack
- TypeScript / React 18
- Vite, TailwindCSS
```

### Step 5 — Target a service in your prompts

```
@api-backend Add a pagination endpoint on /contracts
@front-web   Create a table component with sorting and filters
```

If you don't use an alias, Cortex infers the service from the active file context.

---

## ➕ Going further

### Override a base layer for your project (the cascade)

You don't need to fork Cortex to teach an agent your project's conventions. Every layer (`roles/`, `capabilities/`, `personalities/`, `workflows/`) supports **overlays** at workspace and/or service level.

Quick example — teach `@Hactar` (Lead Backend) your project's namespace rule:

```bash
# 1. Mirror the path of the base file
mkdir -p agents/roles/engineering/
cat > agents/roles/engineering/lead-backend.md <<'EOF'
<!-- OVERLAY
     Base: cortex/agents/roles/engineering/lead-backend.md
     Scope: workspace
     Semantic: additive
-->

# Lead Backend — Overlay (project conventions)

## 📏 Project rules (additive)
- Namespace `Waste\` (not `App\Waste\`)
- `bin/linters fix && bin/linters lint` mandatory before commit
EOF

# 2. Validate (recommended)
./cortex/bin/validate-overlays.sh
```

The Prompt Manager loads `cortex/agents/roles/engineering/lead-backend.md` first, then layers your overlay on top.

📖 **Full guide:** [extending-layers.md](extending-layers.md) — covers all four layers, examples, edge cases, and validation.

### Create a project workflow

Workflows are a special case of overlay (semantic: replacement).

```bash
mkdir -p agents/workflows/engineering/
cp cortex/templates/workflow.md.template agents/workflows/engineering/my-workflow.md
# Fill in the template (don't forget the OVERLAY header)
```

### Add a capability (contributing to cortex)

Capabilities live in `cortex/agents/capabilities/`. To add a *new* capability to the framework (PR upstream):

```
cortex/agents/capabilities/
├── languages/    php.md, typescript.md
├── frameworks/   symfony.md
├── databases/    mysql.md
└── security/     owasp.md
```

Copy the format of an existing capability, then declare it in the `🔌 Capabilities` section of the relevant role. See [CONTRIBUTING.md](../CONTRIBUTING.md).

For project-specific capability flavor (your conventions, your tooling) → use an overlay, not a contribution.

### Create a personality theme

See [`docs/creating-a-theme.md`](creating-a-theme.md) for the full guide.

```bash
./cortex/setup.sh --theme my-theme
```

> Theme-level reassignment (changing which character plays which role) is **not** done via overlay — it requires a full theme fork. Per-character flavor (extra quotes, project-specific behavior) **is** an overlay. See [extending-layers.md](extending-layers.md).

### Add a role (contributing to cortex)

1. Create `cortex/agents/roles/{category}/my-role.md` following the existing format
2. Add a `🔌 Capabilities` section if it's a technical role
3. If a theme is active: add the character to `characters.md` and create their `.md` card
4. Open a PR — see [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## 🗺️ Overview of the 5 layers

| Layer | Base location | Override locations | Answers |
|---|---|---|---|
| **Roles** | `cortex/agents/roles/{cat}/` | `{workspace_root}/agents/roles/`, `{service}/agents/roles/` | *WHAT* to do |
| **Capabilities** | `cortex/agents/capabilities/{cat}/` | `{workspace_root}/agents/capabilities/`, `{service}/agents/capabilities/` | *WHAT I KNOW HOW TO DO* |
| **Personalities** | `cortex/agents/personalities/{theme}/` | Same paths under `{workspace_root}/` and `{service}/` (except `characters.md`) | *WHO* you are |
| **Context** | `project-overview.md` + `project-context.md` (workspace and per-service) | n/a — these are **already** per-service | *WHERE / WHY* you work |
| **Workflows** | `cortex/agents/workflows/{cat}/` | `{workspace_root}/agents/workflows/`, `{service}/agents/workflows/` | *HOW and WITH WHOM* to orchestrate |

Override semantic: **additive** for roles/capabilities/personalities, **replacement** for workflows. See [extending-layers.md](extending-layers.md).

---

## ❓ Quick FAQ

**Q: Do I need to use a personality theme?**
No. `--no-personality` gives you streamlined, professional, neutral agents.

**Q: I don't have a matching workflow. What happens?**
The PM dispatches directly to the right expert without a template. If the case recurs, it will suggest creating a workflow using the template.

**Q: Can I call an agent directly without going through the PM?**
Yes. `@Hactar` invokes the Lead Backend directly. But going through the PM guarantees prompt optimisation and capability loading.

**Q: Is Cortex updated automatically?**
No. The update command depends on how you installed it:
- **Submodule:** `git submodule update --remote cortex`
- **Standalone clone:** `cd cortex && git pull`

Check the [changelog](../changelog/) before updating in production.

**Q: Can I use Cortex without Git at all?**
Yes — you can copy the templates by hand (see [README.md](../README.md) → "Option 2: Manual"). You'll lose the ability to receive upstream updates easily, but the framework itself works.

**Q: I have a multi-repo workspace where each service is its own git repo. Do I need a parent repo?**
No. Cortex doesn't care whether the workspace folder is a git repo. Just `git clone <cortex-url> cortex` next to your service folders, run `./cortex/setup.sh --workspace`, and you're set. This is the **standalone clone** mode.
