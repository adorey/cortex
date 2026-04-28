# ADR-001 — Layered overrides: cascade resolution for all agent layers

- **Status:** Proposed
- **Date:** 2026-04-27
- **Authors:** Cortex maintainers (initiated by @Slartibartfast)
- **Affects:** `cortex/agents/{roles,capabilities,personalities,workflows}/`, [Prompt Manager protocol](../../agents/roles/prompt-manager.md), bootstrap templates, `setup.sh`

---

## 1. Context

Cortex is designed as a **plug-and-play layer**: a host project mounts it (as a Git submodule for single projects / monorepos, or as a standalone clone for multi-repo workspaces), runs `setup.sh`, and gets a multi-agent AI team. The framework promises *"zero project dependency: roles are stack-agnostic, the stack lives in `project-context.md`"* ([cortex/README.md:185](../../README.md#L185)).

In practice this promise has a **hole**:

- `project-overview.md` and `project-context.md` are **per-service** in workspace mode — full extensibility ✅
- `workflows/` has a **2-tier cascade** (`{service}/agents/workflows/` overrides `cortex/agents/workflows/`) — extensible ✅
- `roles/`, `capabilities/`, `personalities/` are **only readable from `cortex/`** — **not extensible** ❌

A host project that wants to teach `@Hactar` (Lead Backend) a project-specific convention (e.g. *"namespace `Waste\` without `App\\`"*) has only three ungraceful options:

1. Repeat the rule in every prompt (tiring, error-prone)
2. Bury it in `project-context.md` and hope the LLM connects the dots (works partially)
3. Fork `cortex/` itself (loses upstream updates, regardless of whether you mounted it as submodule or standalone clone)

The need is real and recurring. Bluspark, the first non-trivial workspace using Cortex, hit it within weeks of adoption.

## 2. Decision

We introduce a **3-tier cascade** that mirrors the existing workflow override mechanism, generalized to **all** agent layers (`roles/`, `capabilities/`, `personalities/`, `workflows/`):

```
Priority 3 (lowest)  cortex/agents/{layer}/...                          # generic, ships with cortex
Priority 2           {workspace_root}/agents/{layer}/...                # workspace-shared (workspace mode only)
Priority 1 (highest) {service}/agents/{layer}/...                       # per-service
```

The Prompt Manager resolves each layer file through this cascade at boot.

## 3. Detailed contract

### 3.1 Resolution algorithm

```text
function resolveLayer(layer, fileRelPath):
    files = []
    base = "cortex/agents/" + layer + "/" + fileRelPath
    if exists(base): files.append(base)

    if workspaceMode:
        wsOverlay = "agents/" + layer + "/" + fileRelPath
        if exists(wsOverlay): files.append(wsOverlay)

    if activeService:
        svcOverlay = activeService + "/agents/" + layer + "/" + fileRelPath
        if exists(svcOverlay): files.append(svcOverlay)

    return files  # ordered: base → workspace → service
```

The PM **reads each file** in order, then applies the layer-specific merge semantic.

### 3.2 Merge semantics — per layer

| Layer | Semantic | Rationale |
|---|---|---|
| `workflows/` | **Replacement** | A workflow is an ordered sequence; merging two sequences would create chaos. The most specific overlay wins entirely. *(Pre-existing behavior, preserved.)* |
| `roles/` | **Additive** | A role is a set of rules (responsibilities, anti-patterns, principles). Overlays *add* project-specific rules to the generic role. |
| `capabilities/` | **Additive** | Same logic — overlays add project-specific patterns to a generic technical capability. |
| `personalities/{theme}/theme.md` | **Additive** | Overlays may extend a theme's narrative context for a project, not redefine it. |
| `personalities/{theme}/{character}.md` | **Additive** | Overlays may add project-flavored quotes, traits, or behavioral notes to a character. |
| `personalities/{theme}/characters.md` | **Not overridable** | Reassigning role↔character mapping is a thematic decision, not a project-level concern. To diverge, fork the entire theme. |

**Key invariant:** within a single conversation, *Priority 1 wins on direct contradiction*. Otherwise the LLM concatenates rules from base → workspace → service and treats them as cumulative.

### 3.3 Overlay file convention

Every overlay file (any layer, any priority) **must start** with this header:

```markdown
<!-- OVERLAY
     Base: cortex/agents/{layer}/{path}
     Scope: {workspace | service @alias}
     Semantic: additive
-->
```

| Field | Purpose | Allowed values |
|---|---|---|
| `Base:` | Path of the file being extended | Existing file under `cortex/agents/` |
| `Scope:` | Human-readable scope | `workspace` *or* `service @alias` |
| `Semantic:` | Merge mode | `additive` (any layer except workflows) *or* `replacement` (workflows only) |

Sections inside the overlay must be **explicitly tagged**:

- `## ... (additive)` — content appended to the corresponding section of the base
- `## 🚫 Disabled rules from base` — explicit list of rules from the base to ignore (use sparingly, each entry must reference a rule that exists in the base)

**Filename rule:** the overlay shares the **same filename and same relative path** as its base — no suffix, no prefix. The overlay's location (workspace vs service) is the disambiguator.

### 3.4 Validation

Overlays are validated by `cortex/bin/validate-overlays.sh` (script to ship with this ADR). The validator runs three tiers of checks:

**🔴 Tier 1 — Blocking (always enforced):**
- Header `<!-- OVERLAY ... -->` is present and parseable
- Required fields `Base:`, `Scope:`, `Semantic:` are present
- `Base:` points to an existing file under `cortex/agents/`
- The overlay's relative path mirrors the base's relative path
- `Semantic:` ∈ `{additive, replacement}`
- `Semantic: replacement` is only allowed for files under `agents/workflows/`

**🟡 Tier 2 — Warnings (errors when `--strict`):**
- Layer is overridable (no overlay of `personalities/{theme}/characters.md`)
- File is in a known layer directory
- `Scope:` matches the file's location (workspace overlay vs service overlay)
- Sections in `additive` overlays are tagged `(additive)` or are explicitly listed

**🟢 Tier 3 — Info (advisory, planned for v0.3):**
- Verbatim duplication detection between overlay and base
- Disabled-rule references actually exist in the base
- Per-service / per-layer overlay counts (recap)

**Exit code:** `0` clean, `1` if any blocking check fails (or any warning in `--strict` mode).

### 3.5 Detection rules

| Signal | How the PM detects it |
|---|---|
| Workspace mode | Bootstrap template is `bootstrap-instructions-workspace.md` AND a services table is declared |
| Active service | Explicit `@alias` in prompt, otherwise inferred from the IDE's currently-open file path; falls back to asking the user if ambiguous |
| Layer overlay present | File exists at the cascade path (cheap `exists()` check, no scanning) |

## 4. Consequences

### Positive

- **Project sovereignty** — Host projects can teach Cortex agents project-specific rules without forking cortex itself.
- **Symmetry** — All four layers follow the same cascade pattern; one rule to remember.
- **Backward compatibility** — Pre-existing workflow override behavior is preserved unchanged.
- **Upstream evolution** — Cortex remains plug-and-play; upstream updates flow without breaking project overlays (provided the base file paths remain stable). This holds whether the host mounts cortex as a submodule or as a standalone clone.
- **Per-character personality flavor** — A project can teach `@Hactar` its tone without redefining `@Hactar` upstream.

### Negative

- **Maintenance burden shifts to the project** — Overlays are a project responsibility; if upstream renames a base file, project overlays break.
- **Cognitive overhead** — A new contributor must learn the cascade convention before adding overlays.
- **Validation tooling is now part of the contract** — Without `validate-overlays.sh`, overlays can drift silently. The script must ship in the same release.
- **Slight context inflation at boot** — The PM may load 2-3 files per layer instead of 1. In practice negligible (<1KB per file in most cases).

### Neutral

- **Theme integrity preserved** — `characters.md` non-overridability is intentional; it forces theme forks rather than Frankenstein themes.
- **Setup script footprint grows** — `setup.sh` should optionally scaffold empty `agents/` skeletons in workspace and services. The pre-existing `--workspace` bug (script previously hardcoded the bootstrap content instead of using the workspace template) was fixed as part of this ADR's implementation: setup.sh now reads the renamed `bootstrap-instructions[-workspace].md` templates.

## 5. Alternatives considered

| Alternative | Rejected because |
|---|---|
| **Frontmatter YAML `extends:`** instead of HTML comment header | Cortex already uses HTML comments for system prompts (`<!-- SYSTEM PROMPT -->`); HTML comments stay invisible in rendered Markdown. Stylistic consistency matters. |
| **Single override level** (workspace OR service, not both) | Doesn't cover cross-service rules in workspaces (e.g. *"all Bluspark services require @Marvin review pre-merge"* is workspace-shared, not per-service). |
| **Filename suffix** (`lead-backend.overlay.md`) | Breaks symmetry with `workflows/`, makes glob patterns less predictable. |
| **Templating engine** (Jinja-style `{{include}}`) | Over-engineering. We're orchestrating LLM prompts, not generating config. Adds a dependency. |
| **Replace cortex base files at install time** (rendered files copied into the project) | Loses the ability to receive upstream updates; effectively forks cortex regardless of mount mode. |
| **Allow `replacement` semantic on all layers** | Contradicts the role/capability/personality nature (additive by design). Reduces flexibility instead of increasing it. |

## 6. Follow-ups (out of scope for this ADR)

These items are **dependent on this ADR** but tracked separately:

1. **Implement `cortex/bin/validate-overlays.sh`** — Tier 1+2 checks, ship in v0.2.0
2. **(DONE)** Refactor `setup.sh` to use the renamed `bootstrap-instructions[-workspace].md` templates in single/workspace mode — completed alongside this ADR's first implementation pass
3. **Optional `agents/` scaffolding** in `setup.sh` (creates empty mirror trees with `.gitkeep` and a README pointer)
4. **Tier 3 validations** (verbatim duplicates, recap stats) — planned for v0.3.0
5. **Theme inheritance discussion** (separate from layer overrides) — explicit non-goal here; may justify a future ADR

## 7. References

- [cortex/README.md](../../README.md) — Framework philosophy
- [cortex/agents/roles/prompt-manager.md](../../agents/roles/prompt-manager.md) — PM dispatch protocol
- [cortex/agents/workflows/README.md](../../agents/workflows/README.md) — Pre-existing workflow cascade (the model for this generalization)
- [cortex/docs/extending-layers.md](../extending-layers.md) — User-facing reference for the cascade
- [cortex/CONTRIBUTING.md](../../CONTRIBUTING.md) — How to contribute, including overlay creation
