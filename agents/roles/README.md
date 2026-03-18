# Roles — Cortex Agents

> Each file in this folder defines a **generic business role**, independent of any tech stack or personality.

## Principle

A role contains:
- The **responsibilities** of the position
- The **universal principles** to follow
- Reusable **checklists** and **frameworks**
- **Interactions** with other roles
- The **`🔌 Capabilities`** section declaring categories to load from `capabilities/`

A role does **NOT** contain:
- A specific tech stack (→ see `capabilities/`)
- Personality or tone (→ see `personalities/`)
- Project-specific data (→ see `project-context.md`)

## Available roles

### Entry Point

| File | Role | Description |
|---------|------|-------------|
| `prompt-manager.md` | Prompt Manager | Analysis, dispatch, workflow lookup, capability loading |

### `engineering/` — Design & technical delivery

| File | Role | Domain |
|---------|------|---------|
| `architect.md` | Lead Architect | System architecture, design patterns |
| `lead-backend.md` | Lead Backend | Backend development, APIs, services |
| `lead-frontend.md` | Lead UI/UX & Frontend | User interface, components, UX |
| `dba.md` | Database Administrator | DB, SQL optimization, migrations |
| `platform-engineer.md` | Platform & DevOps Lead | Infrastructure, CI/CD, IDP |
| `performance-engineer.md` | Performance Engineer | Optimization, scalability, monitoring |
| `consultant-platform.md` | Consultant Platform | Audit, strategic advice, governance |
| `qa-automation.md` | QA Automation Engineer | Unit, integration, E2E tests |

### `product/` — Product vision & business

| File | Role | Domain |
|---------|------|---------|
| `product-owner.md` | Product Owner | Product vision, backlog, prioritization |
| `business-analyst.md` | Business Analyst | Functional specifications, business needs |

### `security-compliance/` — Security & compliance

| File | Role | Domain |
|---------|------|---------|
| `security-engineer.md` | Security Engineer (CISO) | Application, infra, data security |
| `compliance-officer.md` | Compliance Officer | GDPR, compliance, ethics |

### `data/` — Data & analytics

| File | Role | Domain |
|---------|------|---------|
| `data-analyst.md` | Data Analyst | Data analysis, dashboards, KPIs |

### `communication/` — Content & documentation

| File | Role | Domain |
|---------|------|---------|
| `tech-writer.md` | Technical Writer | Documentation, onboarding |

## How it works

At runtime, an agent is composed of 5 layers:

```
┌─────────────────────────────────┐
│   project-context.md            │  ← Stack, business rules, conventions
├─────────────────────────────────┤
│   capabilities/{category}/      │  ← Loaded technical skills
├─────────────────────────────────┤
│   personalities/{theme}/        │  ← Tone, quotes, traits (optional)
├─────────────────────────────────┤
│   roles/{category}/{role}.md    │  ← Skills, responsibilities
├─────────────────────────────────┤
│   workflows/{context}.md        │  ← Orchestration template (optional)
└─────────────────────────────────┘
```

## Adding a role

1. Identify the appropriate **category** (or create a new one)
2. Create `roles/{category}/my-new-role.md`
3. Follow the structure: Profile → Mission → Responsibilities → Principles → `🔌 Capabilities` → Checklists → Interactions
4. Stay **technically agnostic** (no specific framework or language)
5. If a personality theme is active, add the mapping in `personalities/{theme}/characters.md`

## Planned future categories

- `management/` — CTO, Team Lead, HR Manager, Engineering Manager...
- `sales-marketing/` — Sales Engineer, Content Strategist, Growth...
- `legal-finance/` — Legal Counsel, CFO, Financial Controller...
