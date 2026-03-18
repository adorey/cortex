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

## 📁 Two levels

```
cortex/agents/workflows/                 ← Generic workflows (this folder)
    ├── engineering/                         ← Development & technical
    │   └── feature-development.md
    ├── intelligence/                        ← Research & analysis
    │   └── tech-watch.md
    ├── ops/                                 ← Deployment & incident (future)
    └── product/                             ← Discovery & roadmap (future)

{project}/agents/workflows/              ← Workflows specific to the host project
    ├── engineering/
    │   └── my-workflow.md
    └── ...
```

**Priority rule:** the project workflow overrides the generic workflow with the same name.

## 🔄 Prompt Manager role

The Prompt Manager is the **single entry point**. For every request it:

1. Analyses the prompt
2. Searches for a matching workflow — first in `{project}/agents/workflows/`, then here
3a. **Workflow found** → announces it, activates it and orchestrates the steps
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

Use the `cortex/templates/workflow.md.template` template and place your file in `{project}/agents/workflows/{category}/`.
