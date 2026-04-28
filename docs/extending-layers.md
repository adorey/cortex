# Extending Cortex layers — the override cascade

> *"Over-engineering is putting a glacier in a garden. Elegant but inappropriate."* — Slartibartfast

Cortex agents are built from layers (`roles/`, `capabilities/`, `personalities/`, `workflows/`). Each layer can be **extended** at the project level without forking the framework, through a 3-tier cascade.

This guide is the practical reference. For the formal contract, see [ADR-001](adr/ADR-001-layered-overrides.md).

## 🎯 When do I need an overlay?

Symptoms that an overlay is the right tool:

- *"I keep repeating the same project-specific rule in every prompt"*
- *"My agent's response is generically correct but misses our convention"*
- *"I want `@Hactar` to know our namespace rule without me telling it every time"*

Symptoms that an overlay is **not** the right tool:

- The rule fits naturally in [`project-context.md`](../templates/project-context.md.template) (stack, conventions). Put it there first.
- The rule is one-off. Just say it in the prompt.
- The rule conflicts deeply with the base role. You probably want a new custom role, not an overlay.

## 🗺️ Where do overlays live?

Overlays mirror the path of the base file under `cortex/agents/`, at one of two override levels:

```
cortex/agents/roles/engineering/lead-backend.md                              ← BASE (generic)
{workspace_root}/agents/roles/engineering/lead-backend.md                    ← WORKSPACE overlay
{service}/agents/roles/engineering/lead-backend.md                           ← SERVICE overlay
```

The **workspace** level only applies in workspace mode (multiple services under a single root).

When the Prompt Manager loads `lead-backend`, it reads **base → workspace overlay → service overlay** in that order. Most-specific wins on direct contradiction.

### Where overlays go for each layer

| Layer | Base | Overlay path |
|---|---|---|
| Roles | `cortex/agents/roles/{cat}/{role}.md` | `agents/roles/{cat}/{role}.md` |
| Capabilities | `cortex/agents/capabilities/{cat}/{techno}.md` | `agents/capabilities/{cat}/{techno}.md` |
| Personality theme | `cortex/agents/personalities/{theme}/theme.md` | `agents/personalities/{theme}/theme.md` |
| Personality character | `cortex/agents/personalities/{theme}/{Char}.md` | `agents/personalities/{theme}/{Char}.md` |
| Workflows | `cortex/agents/workflows/{cat}/{wf}.md` | `agents/workflows/{cat}/{wf}.md` |

### What you **cannot** override

- `cortex/agents/personalities/{theme}/characters.md` — reassigning role↔character mapping is a theme-level decision. To diverge, fork the entire theme. See [creating-a-theme.md](creating-a-theme.md).

## 🆕 Overlay vs custom addition

There are **two ways** to put a file in your project's `agents/` tree:

| Kind | Has `<!-- OVERLAY -->` header? | When |
|---|---|---|
| **Overlay** | ✅ Yes | You're extending an existing cortex base (adding rules to `lead-backend.md`, etc.) |
| **Custom addition** | ❌ No | You're adding something brand new that doesn't exist in cortex (a custom theme, a new role, a project-specific capability) |

This guide focuses on **overlays**. For custom additions, you just place the file at the cascade path and the PM picks it up — no header needed. The `validate-overlays.sh` script logs custom additions as informational and skips overlay-specific checks for them.

Examples of custom additions:
- A fully custom personality theme (you don't extend `h2g2`, you create your own)
- A new role unique to your domain (e.g. `roles/data/ml-engineer.md`)
- A project-specific capability not worth PR'ing upstream

## 📜 Anatomy of an overlay file

Every overlay must start with this header:

```markdown
<!-- OVERLAY
     Base: cortex/agents/roles/engineering/lead-backend.md
     Scope: service @backend
     Semantic: additive
-->

# Lead Backend — Overlay @backend

## 🔌 Project rules (additive)

- Namespace strict : `Waste\` (pas `App\Waste\`) — cf. project-context.md
- `bin/linters fix && bin/linters lint` OBLIGATOIRE avant chaque commit
- Migrations : feature flag obligatoire

## 📏 Project anti-patterns (additive)

- ❌ `exit()` dans le code applicatif
- ❌ Queries dans les constructeurs
```

### Header fields

| Field | Purpose | Values |
|---|---|---|
| `Base:` | The file you're extending | Path under `cortex/agents/` (must exist) |
| `Scope:` | Human-readable scope label | `workspace` or `service @alias` |
| `Semantic:` | Merge mode | `additive` (default for everything except workflows) — `replacement` (workflows only) |

### Section tagging

In `additive` overlays, every section must be **explicitly marked**:

- `## ... (additive)` — content is appended to the corresponding section of the base
- `## 🚫 Disabled rules from base` — explicit list of base rules to ignore (use sparingly; each entry must reference a real rule from the base)

This explicit tagging serves two purposes:
- A human reading the file knows immediately what's an extension vs what's a deletion
- The Prompt Manager and `validate-overlays.sh` can rely on the structure deterministically

## 📚 Concrete examples

### Example 1 — Service-level role overlay

You want `@Hactar` (lead-backend) to know that in your `@backend` service, all migrations require feature flags.

**File:** `core/bluspark-backend/agents/roles/engineering/lead-backend.md`

```markdown
<!-- OVERLAY
     Base: cortex/agents/roles/engineering/lead-backend.md
     Scope: service @backend
     Semantic: additive
-->

# Lead Backend — Overlay @backend

## 📏 Project rules (additive)

- Every Doctrine migration MUST guard schema changes with a feature flag (project convention)
- `bin/linters fix && bin/linters lint` is mandatory before every commit
- Namespace `Waste\` (not `App\Waste\`)

## 🚫 Disabled rules from base
- (none)
```

### Example 2 — Workspace-level capability overlay

You want all PHP work across all your services to follow Bluspark's strict typing convention, plus its specific PHPStan baseline.

**File:** `agents/capabilities/languages/php.md` (at workspace root)

```markdown
<!-- OVERLAY
     Base: cortex/agents/capabilities/languages/php.md
     Scope: workspace
     Semantic: additive
-->

# PHP — Overlay Bluspark workspace

## 📏 Workspace conventions (additive)

- `declare(strict_types=1);` REQUIRED on every PHP file
- PHPStan level 8 minimum, baseline in `tools/phpstan/phpstan-baseline.neon`
- No `App\` namespace — domains are first-class (e.g. `Waste\`, `Billing\`)

## 🛠️ Workspace tooling (additive)

- Linters: `./bin/linters fix && ./bin/linters lint` (~10 min, hosts Docker internally)
- Static analysis: `vendor/bin/phpstan` (separate, ~5 min)
```

### Example 3 — Service-level personality character overlay

You want `@Hactar` to use Bluspark-flavored quotes and metaphors.

**File:** `core/bluspark-backend/agents/personalities/h2g2/Hactar.md`

```markdown
<!-- OVERLAY
     Base: cortex/agents/personalities/h2g2/Hactar.md
     Scope: service @backend
     Semantic: additive
-->

# Hactar — Overlay @backend (Bluspark)

## 💬 Project-flavored quotes (additive)

- *"I have computed the optimal Doctrine migration: feature-flagged, idempotent, and reversible. As all things should be."*
- *"Your N+1 query is the cosmic equivalent of asking the same question 200 times. We have JOINs for that."*

## 📏 Project-flavored behavior (additive)

- Always reference Bluspark's `bin/linters` workflow when discussing PHP commits
- When proposing a refactor, cross-check the conventions in `core/bluspark-backend/project-context.md`
```

### Example 4 — Workspace workflow override (replacement)

You have a Bluspark-specific feature-development flow that requires @Marvin's security review at step 2.5.

**File:** `agents/workflows/engineering/feature-development.md` (at workspace root)

```markdown
<!-- OVERLAY
     Base: cortex/agents/workflows/engineering/feature-development.md
     Scope: workspace
     Semantic: replacement
-->

# Workflow: Feature development — Bluspark

## 🎯 Triggers
[same as base, see cortex/agents/workflows/engineering/feature-development.md]

## 📋 Steps

### Step 1 — Scoping
[...]

### Step 2 — Implementation
[...]

### Step 2.5 — Pre-merge security checkpoint (Bluspark-specific)
**Agent:** `security-engineer`
**Objective:** Mandatory @Marvin review before any PR merges to master.
[...]

### Step 3 — Tests
[...]
```

## ✅ Validating your overlays

Before committing overlays, run:

```bash
./cortex/bin/validate-overlays.sh                                     # check everything
./cortex/bin/validate-overlays.sh --service core/bluspark-backend     # check one service
./cortex/bin/validate-overlays.sh --strict                            # warnings → errors
```

The validator catches the common mistakes:
- Overlay header missing or malformed
- `Base:` points to a non-existent file (typo, or upstream removed it)
- Overlay path doesn't mirror the base path
- Trying to override a non-overridable file (`characters.md`)
- `replacement` semantic used outside `workflows/`

CI integration is recommended — fail the pipeline if `validate-overlays.sh --strict` returns non-zero.

## 🔄 Upgrade workflow

When you update cortex (the command depends on how you installed it):

- **Submodule mode:** `git submodule update --remote cortex`
- **Standalone clone:** `cd cortex && git pull`

After updating:

1. Run `./cortex/bin/validate-overlays.sh` immediately
2. Investigate any error reported (most common: a base file was renamed upstream)
3. Update overlay headers to point to the new path, OR delete the overlay if it's no longer needed
4. Read the [`cortex/changelog/`](../changelog/) entry for the new version — it lists breaking renames

## 🤔 FAQ

**Q: Can I have multiple overlays for the same role at the same level?**
No. One overlay per `(level, layer, file)` pair. If you need to organize rules, use sections within the overlay.

**Q: What if I disagree fundamentally with a generic role's design?**
You probably want a custom role rather than an overlay. Add `cortex/agents/roles/{cat}/my-role.md` upstream (PR), or copy it under your project's `agents/roles/` for a project-only role.

**Q: Can I override an overlay?**
Service overlay > workspace overlay > base. That's the cascade. There's no fourth level.

**Q: Are overlays detected automatically?**
Yes. The PM checks for the overlay paths at boot. No registration step needed.

**Q: Performance impact?**
Negligible. Each layer triggers at most 2 extra `exists()` checks and reads. Total overhead per conversation: ≤ a few KB of context.

## 📖 References

- [ADR-001 — Layered overrides](adr/ADR-001-layered-overrides.md) — formal contract
- [getting-started.md](getting-started.md) — installation walkthrough
- [creating-a-theme.md](creating-a-theme.md) — when overlay isn't enough, fork the theme
- [../CONTRIBUTING.md](../CONTRIBUTING.md) — contributing back upstream
