# Architecture Decision Records

> *"Fjords take millions of years. A good architecture deserves at least an hour of thought — and a written trace."* — Slartibartfast

This folder gathers the **Architecture Decision Records** (ADRs) of the Cortex framework itself.

An ADR documents a **significant architectural decision**: the context that triggered it, the alternatives considered, the chosen option, and its consequences. ADRs are **append-only** — they freeze the reasoning of a moment in time.

## Why ADRs?

- **Memory** — Future contributors (humans or AI) understand *why* a decision was made, not just *what* was decided.
- **Reversibility lens** — The "Consequences" section forces us to face the cost of the decision, not just its benefits.
- **Onboarding** — Reading ADRs in order is the fastest path to understanding the framework's design philosophy.

## Conventions

| Aspect | Rule |
|---|---|
| **Filename** | `ADR-{NNN}-{kebab-case-title}.md` (e.g. `ADR-001-layered-overrides.md`) |
| **Numbering** | Strict sequential, never reused — even for superseded ADRs |
| **Status** | One of: `Proposed`, `Accepted`, `Deprecated`, `Superseded by ADR-XXX` |
| **Modification policy** | Append-only. To revise: write a new ADR that supersedes the old one. Mark the old one `Superseded by ADR-XXX` (only metadata change allowed). |
| **Scope** | Decisions that affect Cortex's structure, contracts, or behavior. Not implementation details. |

## Required sections

Every ADR must contain:

1. **Status** + date
2. **Context** — What situation triggers the decision?
3. **Decision** — What is decided, in clear terms?
4. **Detailed contract** — How exactly does it work? (schemas, examples, edge cases)
5. **Consequences** — Positive, negative, neutral impacts
6. **Alternatives considered** — What was rejected and why
7. **References** — Linked files, related ADRs, external sources

## Index

| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-001](ADR-001-layered-overrides.md) | Layered overrides — cascade resolution for all agent layers | Accepted | 2026-04-28 |

## Authoring an ADR

1. Copy the latest ADR as a starting structure
2. Increment the number
3. Open a PR — the discussion happens in the PR review, not in the ADR text
4. Once accepted, change `Status: Proposed` → `Status: Accepted` + commit
5. Update the index above
