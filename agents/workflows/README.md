# Workflows

> *"A plan is a list of things that won't happen exactly as planned — but it's still better framing than total improvisation."* — Ford Prefect

## 🎯 What is a workflow?

A workflow is an **orchestration template**: a sequence of steps, agents and checklists to follow for a recurring context.

It is not a rigid script. It is a safety net to ensure nothing is forgotten.

| Layer | Answers |
|---|---|
| `roles/` | **WHAT** to do |
| `capabilities/` | **WHAT I KNOW HOW TO DO** |
| `personalities/` | **WHO** you are |
| `project-context.md` | **WHERE** you work |
| `workflows/` | **IN WHAT ORDER and WITH WHOM** |

## 📁 Three levels (workspace mode) / Two levels (single project)

```
cortex/agents/workflows/                       ← priority 3 — Generic workflows (this folder)
    ├── engineering/                                 ← Development & technical
    │   └── feature-development.md
    ├── intelligence/                                ← Research & analysis
    │   └── tech-watch.md
    ├── ops/                                         ← Deployment & incident (future)
    └── product/                                     ← Discovery & roadmap (future)

{workspace_root}/agents/workflows/             ← priority 2 — workspace-shared (workspace mode only)

{service}/agents/workflows/                    ← priority 1 — service-specific
```

**Priority rule:** the most specific workflow with the same name **replaces** the generic one (semantic: `replacement`). This is the workflow-specific behavior; other layers (roles, capabilities, personalities) use **additive** overlays.

For details on the cascade as it applies to all layers, see [docs/extending-layers.md](../../docs/extending-layers.md) and [ADR-001](../../docs/adr/ADR-001-layered-overrides.md).

## 🔄 Prompt Manager role

The Prompt Manager is the **single entry point**. For every request it:

1. Analyses the prompt
2. Searches for a matching workflow — `{service}/agents/workflows/` → `{workspace_root}/agents/workflows/` → here
3a. **Workflow found** → announces it, activates it and orchestrates the steps (most specific match wins)
3b. **No workflow** → classic dispatch to the expert
3c. **Recurring case without a workflow** → proposes creating one

## 📝 Available workflows

| Category | File | Activation context |
|---|---|---|
| `engineering/` | `feature-development.md` | Developing a new feature |
| `intelligence/` | `tech-watch.md` | Technology watch on a subject or tool |

## 🗂️ Categories

| Category | Purpose | Examples of future workflows |
|---|---|---|
| `engineering/` | Development & technical | `bug-fix`, `code-review`, `refactoring` |
| `intelligence/` | Research & analysis | `security-audit`, `competitive-watch` |
| `ops/` | Deployment & incident | `deployment`, `incident-response` |
| `product/` | Discovery & roadmap | `backlog-grooming`, `user-story-mapping` |

## ➕ Creating a project workflow

Use the `cortex/templates/workflow.md.template` template and place your file in either:

- `{workspace_root}/agents/workflows/{category}/` — if the workflow is shared across services
- `{service}/agents/workflows/{category}/` — if the workflow is specific to one service

The workflow file **must** start with the OVERLAY header (Base, Scope, Semantic). See [docs/extending-layers.md](../../docs/extending-layers.md#example-4--workspace-workflow-override-replacement) for an example.
