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

`cortex/` in these paths — and in every `Base:` header — is the directory `spec` names in `cortex.local.toml`. By default that is the version `cortex.toml` pins, read in place from the store (`~/.cortex/versions/X.Y.Z`). When the project is synced with `cortex sync --link` or `--copy`, it is a `cortex/` directory of the project. Either way, overlays live in your project's own `agents/` tree, never under `cortex/`.

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

This guide focuses on **overlays**. For custom additions, you just place the file at the cascade path and the PM picks it up — no header needed. `cortex validate` logs custom additions as informational and skips overlay-specific checks for them.

A file with no header that sits **at the path of a cortex base** is not a custom addition: it shadows that base, and the cascade stacks it as an overlay. The validator reports it as `MISSING_HEADER` — a warning, and an error under `--strict`. Add the header, or rename the file if it was never meant to extend the base. The one exception is `personalities/{theme}/characters.md`: it cannot be overridden at all, so a copy at the path of a base is `NON_OVERRIDABLE`, an error, header or not. A theme of your own, with no base of that name, is a custom addition. A `README.md` is documentation: the cascade never reads one, and the validator never reports it.

Examples of custom additions:
- A fully custom personality theme (you don't extend `h2g2`, you create your own)
- A new role unique to your domain (e.g. `roles/data/ml-engineer.md`)
- A project-specific capability not worth PR'ing upstream

**A third thing you'll find in `agents/`, that is neither of the above:** `agents/project-overview.md` and `agents/project-context.md` are the **team-shared context** tier introduced by [ADR-006](adr/ADR-006-workspace-shareable-repo.md). They don't carry an `<!-- OVERLAY -->` header (there's no base file at `cortex/agents/project-*.md` to extend) and they're not part of the roles/capabilities/personalities/workflows cascade — they're read *additively* alongside the workspace-root context files (the **developer** tier), not cascaded through base → workspace → service. `cortex validate` doesn't check them; there's nothing overlay-shaped about them.

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
- `bin/linters fix && bin/linters lint` is MANDATORY before every commit
- Migrations : feature flag obligatoire

## 📏 Project anti-patterns (additive)

- ❌ `exit()` in application code
- ❌ Queries in constructors
```

### Header fields

| Field | Purpose | Values |
|---|---|---|
| `Base:` | The file you're extending | Path under `cortex/agents/` (must exist in the version `cortex.toml` pins) |
| `Scope:` | Human-readable scope label | `workspace` or `service @alias` |
| `Semantic:` | Merge mode | `additive` (default for everything except workflows) — `replacement` (workflows only) |

### Section tagging

In `additive` overlays, every section must be **explicitly marked**:

- `## ... (additive)` — content is appended to the corresponding section of the base
- `## 🚫 Disabled rules from base` — explicit list of base rules to ignore (use sparingly; each entry must reference a real rule from the base)

This explicit tagging serves two purposes:
- A human reading the file knows immediately what's an extension vs what's a deletion
- The Prompt Manager and `cortex validate` can rely on the structure deterministically

## 📚 Concrete examples

### Example 1 — Service-level role overlay

You want `@Hactar` (lead-backend) to know that in your `@backend` service, all migrations require feature flags.

**File:** `core/acme-backend/agents/roles/engineering/lead-backend.md`

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

You want all PHP work across all your services to follow Acme's strict typing convention, plus its specific PHPStan baseline.

**File:** `agents/capabilities/languages/php.md` (at workspace root)

```markdown
<!-- OVERLAY
     Base: cortex/agents/capabilities/languages/php.md
     Scope: workspace
     Semantic: additive
-->

# PHP — Overlay Acme workspace

## 📏 Workspace conventions (additive)

- `declare(strict_types=1);` REQUIRED on every PHP file
- PHPStan level 8 minimum, baseline in `tools/phpstan/phpstan-baseline.neon`
- No `App\` namespace — domains are first-class (e.g. `Waste\`, `Billing\`)

## 🛠️ Workspace tooling (additive)

- Linters: `./bin/linters fix && ./bin/linters lint` (~10 min, hosts Docker internally)
- Static analysis: `vendor/bin/phpstan` (separate, ~5 min)
```

### Example 3 — Service-level personality character overlay

You want `@Hactar` to use Acme-flavored quotes and metaphors.

**File:** `core/acme-backend/agents/personalities/h2g2/Hactar.md`

```markdown
<!-- OVERLAY
     Base: cortex/agents/personalities/h2g2/Hactar.md
     Scope: service @backend
     Semantic: additive
-->

# Hactar — Overlay @backend (Acme)

## 💬 Project-flavored quotes (additive)

- *"I have computed the optimal Doctrine migration: feature-flagged, idempotent, and reversible. As all things should be."*
- *"Your N+1 query is the cosmic equivalent of asking the same question 200 times. We have JOINs for that."*

## 📏 Project-flavored behavior (additive)

- Always reference Acme's `bin/linters` workflow when discussing PHP commits
- When proposing a refactor, cross-check the conventions in `core/acme-backend/project-context.md`
```

### Example 4 — Workspace workflow override (replacement)

You have a Acme-specific feature-development flow that requires @Marvin's security review at step 2.5.

**File:** `agents/workflows/engineering/feature-development.md` (at workspace root)

```markdown
<!-- OVERLAY
     Base: cortex/agents/workflows/engineering/feature-development.md
     Scope: workspace
     Semantic: replacement
-->

# Workflow: Feature development — Acme

## 🎯 Triggers
[same as base, see cortex/agents/workflows/engineering/feature-development.md]

## 📋 Steps

### Step 1 — Scoping
[...]

### Step 2 — Implementation
[...]

### Step 2.5 — Pre-merge security checkpoint (Acme-specific)
**Agent:** `security-engineer`
**Objective:** Mandatory @Marvin review before any PR merges to master.
[...]

### Step 3 — Tests
[...]
```

## ✅ Validating your overlays

Before committing overlays, run:

```bash
cortex validate                                   # check everything
cortex validate --service core/acme-backend       # check one service
cortex validate --strict                          # warnings → errors
```

`cortex validate` checks the project's overlays against the spec `spec` names — the version `cortex.toml` pins. It exits `0` when clean, `1` on errors (or on warnings under `--strict`), and `2` on bad arguments or when it has no spec to check against: run `cortex sync` first.

The validator catches the common mistakes:
- Overlay header missing or malformed — including a headerless file at the path of a base (`MISSING_HEADER`)
- `Base:` points to a non-existent file (typo, or upstream removed it)
- Overlay path doesn't mirror the base path
- Trying to override a non-overridable file (`characters.md`)
- `replacement` semantic used outside `workflows/`

CI integration is recommended — fail the pipeline if `cortex validate --strict` returns non-zero. The CI job installs the binary of the version `cortex.toml` pins — its checks are that version's — then runs `cortex sync`:

```bash
version="$(LC_ALL=C tr -d '\357\273\277' < cortex.toml | sed -n "s/^[[:space:]]*version[[:space:]]*=[[:space:]]*[\"']\([^\"']*\)[\"'].*/\\1/p" | head -n 1)"
[ -n "$version" ] || { echo "cortex.toml pins no version" >&2; exit 1; }
curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh -s -- "$version"
export PATH="$HOME/.cortex/bin:$PATH"
cortex sync
cortex validate --strict
```

On a Windows runner, in PowerShell:

```powershell
$pinned = Select-String -Path cortex.toml -Pattern '^\s*version\s*=\s*["'']([^"'']+)["'']' | Select-Object -First 1
if (-not $pinned) { throw "cortex.toml pins no version" }
$version = $pinned.Matches[0].Groups[1].Value
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/adorey/cortex/main/install.ps1))) -Version $version
$env:Path = "$env:USERPROFILE\.cortex\bin;$env:Path"
cortex sync; if ($LASTEXITCODE) { exit $LASTEXITCODE }
cortex validate --strict; if ($LASTEXITCODE) { exit $LASTEXITCODE }
```

## 🔄 Upgrade workflow

To move a project to another Cortex version:

1. Change `version` in `cortex.toml`
2. Run `cortex sync` — it puts that version in the store, downloaded once per machine, and points `spec` at it. A version newer than the installed binary is refused, with the command that upgrades the binary. Teammates run `cortex sync` after they pull the change
3. Run `cortex validate` immediately
4. Investigate any error reported (most common: a base file was moved or renamed upstream, breaking a `Base:` header)
5. Update overlay headers to point to the new path, OR delete the overlay if it's no longer needed
6. Read the entry for the new version in Cortex's [`changelog/`](../changelog/) — it lists breaking renames

Still on a git submodule or a standalone clone of Cortex? See [Moving to the `cortex` binary](migrating-to-the-binary.md).

## 🤔 FAQ

**Q: Can I have multiple overlays for the same role at the same level?**
No. One overlay per `(level, layer, file)` pair. If you need to organize rules, use sections within the overlay.

**Q: What if I disagree fundamentally with a generic role's design?**
You probably want a custom role rather than an overlay. Add `cortex/agents/roles/{cat}/my-role.md` upstream (PR), or copy it under your project's `agents/roles/` for a project-only role.

**Q: Can I edit the base file instead?**
No. The spec is read-only — in the store, and in a project's linked or copied `cortex/` — so an edit of a base file through a project fails. Write an overlay. To change the base for everyone, open a PR on Cortex, and test it in a throwaway host project with `cortex sync --from PATH`, `PATH` your checkout of the Cortex repository.

**Q: Can I override an overlay?**
Service overlay > workspace overlay > base. That's the cascade. There's no fourth level.

**Q: Are overlays detected automatically?**
Yes. The PM checks for the overlay paths at boot. No registration step needed.

**Q: Performance impact?**
Negligible. Each layer triggers at most 2 extra `exists()` checks and reads. Total overhead per conversation: ≤ a few KB of context.

## 📖 References

- [ADR-001 — Layered overrides](adr/ADR-001-layered-overrides.md) — formal contract
- [getting-started.md](getting-started.md) — installation walkthrough
- [migrating-to-the-binary.md](migrating-to-the-binary.md) — moving a project to the `cortex` binary
- [creating-a-theme.md](creating-a-theme.md) — when overlay isn't enough, fork the theme
- [../CONTRIBUTING.md](../CONTRIBUTING.md) — contributing back upstream
