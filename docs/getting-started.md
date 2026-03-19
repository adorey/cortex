# Getting Started — Cortex

> *"Don't Panic. And read this guide before doing anything else."* — Arthur Dent

This step-by-step guide covers both installation modes: **single project** and **multi-service workspace**.

---

## Prerequisites

- A Git repository (or a workspace folder for multi-repo mode)
- An IDE compatible with Copilot instructions: VS Code + GitHub Copilot, Cursor, etc.
- Git installed (for the submodule)

---

## 🚀 Mode 1 — Single project

### Step 1 — Add Cortex as a submodule

```bash
cd my-project/
git submodule add <cortex-url> cortex
```

### Step 2 — Run the setup script

```bash
# With the H2G2 theme (default)
./cortex/setup.sh

# Without personality (neutral professional agents)
./cortex/setup.sh --no-personality

# With a custom theme
./cortex/setup.sh --theme star-wars
```

The script automatically creates:
- `.github/copilot-instructions.md` — bootstrap read by your IDE at every session
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

In your IDE, simply mention the desired agent.

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

For a workspace containing multiple services (microservices, monorepo, multi-repo):

```
workspace/
├── cortex/          ← shared submodule
├── api-backend/
├── front-web/
└── notif-service/
```

### Step 1 — Place Cortex in the parent folder

```bash
cd workspace/
git submodule add <cortex-url> cortex
```

### Step 2 — Run in workspace mode

```bash
./cortex/setup.sh --workspace
# The script asks for service names to initialise:
# → Service name (e.g. api-backend, front-web): api-backend
# → Service name (e.g. api-backend, front-web): front-web
# → Service name (e.g. api-backend, front-web):  ← empty entry to finish
```

The script creates for each service:
- `{service}/project-overview.md` — with `@alias: {service}` pre-filled
- `{service}/project-context.md` — with `@alias: {service}` pre-filled

And at the workspace root (optional):
- `project-overview.md` — global vision (shared stakeholders, common constraints)
- `project-context.md` — shared conventions (linting, CI/CD, versioning)

### Step 3 — Copy the workspace bootstrap

```bash
cp cortex/templates/copilot-instructions-workspace.md .github/copilot-instructions.md
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

If you don't use an alias, Cortex infers the service from the files open in the IDE.

---

## ➕ Going further

### Create a project workflow

Cortex workflows are in `cortex/agents/workflows/` (generic, shared across projects).

To create a workflow specific to your project:

```bash
mkdir -p agents/workflows/engineering/
cp cortex/templates/workflow.md.template agents/workflows/engineering/my-workflow.md
# Fill in the template
```

The PM looks first in your `agents/workflows/` (higher priority), then in `cortex/agents/workflows/`.

### Add a capability

Capabilities are in `cortex/agents/capabilities/`. To add one to the framework:

```
cortex/agents/capabilities/
├── languages/    php.md, typescript.md
├── frameworks/   symfony.md
├── databases/    mysql.md
└── security/     owasp.md
```

Copy the format of an existing capability, then declare it in the `🔌 Capabilities` section of the relevant role.

### Create a personality theme

See [`docs/creating-a-theme.md`](creating-a-theme.md) for the full guide.

```bash
./cortex/setup.sh --theme my-theme
```

### Add a role

1. Create `cortex/agents/roles/{category}/my-role.md` following the existing format
2. Add a `🔌 Capabilities` section if it's a technical role
3. If a theme is active: add the character to `characters.md` and create their `.md` card

---

## 🗺️ Overview of the 5 layers

| Layer | Files | Answers |
|---|---|---|
| **Roles** | `cortex/agents/roles/{cat}/` | *WHAT* to do (business skills) |
| **Capabilities** | `cortex/agents/capabilities/` | *WHAT I KNOW HOW TO DO* (tech stack) |
| **Personalities** | `cortex/agents/personalities/{theme}/` | *WHO* you are (tone, style) |
| **Context** | `project-overview.md` + `project-context.md` | *WHERE / WHY* you work |
| **Workflows** | `agents/workflows/` or `cortex/agents/workflows/` | *HOW and WITH WHOM* to orchestrate |

---

## ❓ Quick FAQ

**Q: Do I need to use a personality theme?**
No. `--no-personality` gives you streamlined, professional, neutral agents.

**Q: I don't have a matching workflow. What happens?**
The PM dispatches directly to the right expert without a template. If the case recurs, it will suggest creating a workflow using the template.

**Q: Can I call an agent directly without going through the PM?**
Yes. `@Hactar` invokes the Lead Backend directly. But going through the PM guarantees prompt optimisation and capability loading.

**Q: Is the Cortex submodule updated automatically?**
No. To update: `git submodule update --remote cortex`. Check the changelog before updating in production.

**Q: Can I use Cortex without a Git submodule?**
Yes, using the manual option: copy the templates by hand (see [README.md](../README.md#option-2--manual)).
