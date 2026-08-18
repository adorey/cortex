# Changelog

All notable changes to Cortex are recorded here — **this file is the single source of truth for versions**.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Each entry links to its detailed, narrated
release note under [`changelog/`](changelog/).

## [Unreleased]

## [0.7.0] - 2026-08-17 — End to End
[Full notes](changelog/0.7.0.md)

### Added
- `testing/` capabilities: framework-agnostic `e2e-testing` and `component-testing`; a `frameworks/vue` card; a `frontend-testing` workflow.
- `regulatory-compliance-writer` role + **@Pag** character.

### Changed
- Symfony reference gains an "End-to-end & functional testing" section **and three more traps that pass every gate**; `lead-frontend` and `qa-automation` now load the `testing/` category.

## [0.6.0] - 2026-08-13 — Trapdoor
[Full notes](changelog/0.6.0.md)

### Added
- Five Symfony "security traps that pass every gate"; a `qa-automation` role card.

### Changed
- Translated API error responses (translatable HTTP exceptions, never a raw throw) documented in the Symfony card.

## [0.5.0] - 2026-08-10 — Publishable
[Full notes](changelog/0.5.0.md)

### Added
- A licence and community documentation; CI for the framework layer.

### Changed
- English throughout (including the archive template); line endings pinned to LF.

## [0.4.1] - 2026-07-28 — Reuse before create
[Full notes](changelog/0.4.1.md)

### Added
- A dispatch-protocol step that checks whether an existing script/playbook/job already covers the case before writing a new one.

## [0.4.0] - 2026-07-20 — Team & developer context tiers (ADR-006)
[Full notes](changelog/0.4.0.md)

### Added
- Two aggregated context tiers: team context in `agents/`, developer context at the root — no change to existing root files.

## [0.3.2] - 2026-07-20 — Cortex reads its own instructions
[Full notes](changelog/0.3.2.md)

### Changed
- Self-hosted `CLAUDE.md` so Cortex bootstraps itself.

## [0.3.1] - 2026-07-09 — Docs catch up with the engine
[Full notes](changelog/0.3.1.md)

### Changed
- README and docs now cover both halves of Cortex (framework + runtime).

## [0.3.0] - 2026-07-09 — The runtime comes alive
[Full notes](changelog/0.3.0.md)

### Added
- The Cortex Runtime executable engine (ADR-002/003), persistence & state, API security & trust model (ADR-004), async execution & resilience (ADR-005), webhooks, and deploy/DevEx tooling.

## [0.2.2] - 2026-06-02 — Cortex Runtime direction (ADR-002)
[Full notes](changelog/0.2.2.md)

### Added
- ADR-002 (Cortex Runtime) accepted, with supporting documentation.

## [0.2.0] - 2026-04-28 — Layered overrides
[Full notes](changelog/0.2.0.md)

### Added
- The cascade/overlay convention for all agent layers, the overlay file convention, and `validate-overlays.sh`.

## [0.1.2] — Minimal Dependencies Principle
[Full notes](changelog/0.1.2.md)

### Added
- A "Minimal Dependencies" universal principle; role-card updates.

## [0.1.1] — Starlight Capability & Archiving Revamp
[Full notes](changelog/0.1.1.md)

### Added
- A Starlight capability; Archiving Protocol v2.

## [0.1.0] — First Release
[Full notes](changelog/0.1.0.md)

### Added
- The 3-layer architecture, 15 agent roles, the H2G2 personality theme, the Prompt Manager & dispatch protocol, the workflows layer, and setup & tooling.
