# ADR-006 — Team context in `agents/`, developer context at the workspace root

- **Status:** Accepted
- **Date:** 2026-07-20 (proposed) · 2026-07-20 (accepted)
- **Authors:** Cortex maintainers (initiated by the maintainer, drafted by @Oolon)
- **Affects:** One new, optional file pair under `{workspace_root}/agents/` (`project-overview.md` / `project-context.md`, team-shared), [`agents/roles/prompt-manager.md`](../../agents/roles/prompt-manager.md) (context aggregation), `templates/bootstrap-instructions-workspace.md`, `setup.sh` (`--workspace` scaffolding), `docs/getting-started.md`, `docs/extending-layers.md`
- **Relates to:** [ADR-001](ADR-001-layered-overrides.md) — this ADR deliberately does **not** reuse its cascade merge semantic (most-specific-tier-wins). See §2 for why.

---

## 1. Context

ADR-001 generalised the override cascade (`roles/`, `capabilities/`, `personalities/`, `workflows/`) to a 3-tier lookup rooted at `{workspace_root}/agents/...` for the workspace-shared tier. It also noted, in passing, that `project-overview.md` and `project-context.md` were "already per-service" and didn't need the same treatment — but it only looked at the *service* level. The **workspace** level has a gap ADR-001 didn't surface:

- `{workspace_root}/agents/` (workspace overlays) and `{workspace_root}/project-overview.md` / `project-context.md` (workspace context) are documented as siblings, both hanging directly off `{workspace_root}`. See [`docs/getting-started.md`](../getting-started.md) (workspace scaffolding), [`templates/bootstrap-instructions-workspace.md`](../../templates/bootstrap-instructions-workspace.md) (Steps 1-2 read them "at the workspace root"), and [`agents/roles/prompt-manager.md`](../../agents/roles/prompt-manager.md).
- `{workspace_root}` itself is **not required to be a git repo**. `docs/getting-started.md` documents two workspace flavors: 2.A (monorepo, root is a repo, `cortex` is a submodule) and **2.B (multi-repo, root is just a folder containing service clones, `cortex` is a sibling clone)**. Flavor 2.B is common at scale — one real case is a workspace root holding ~60 independent service repos, where the root folder itself has never been (and shouldn't be) a git repo.
- In flavor 2.B, `{workspace_root}/agents/` has an escape hatch teams already use in practice: nothing in cortex's resolution cares whether that folder is a plain directory or the working tree of its own git repo (cloned or submodule'd at that path). Teams wanting to share workspace-level overlays across developers just make `agents/` its own repo — undocumented, but it works today because resolution is a plain `exists()` check (ADR-001 §3.1), not a repo-boundary check.
- `project-overview.md` / `project-context.md` at the workspace root have **no such escape hatch**, and — this is the key observation — in flavor 2.B they are, in practice, already **per-developer by default**: with no git repo at the root, nothing forces two developers' root-level files to agree, to exist, or to survive a `git clone` by a teammate. Whatever a developer writes there today stays on their machine unless they manually copy it around. Cortex has just never said this out loud or given it a formal role.

Net effect: a team can share *overlays* under `agents/` but has no equivalent for a **team-agreed** workspace vision/conventions — only the de facto personal, unshared root file. That's the gap this ADR closes: give the team a genuinely shareable, versioned home for that content, without touching how the root file already works.

## 2. Decision

Recognise and formalise **two tiers**, not one:

1. **Developer tier — the existing root files, unchanged.** `{workspace_root}/project-overview.md` and `project-context.md` keep their exact current resolution, optionality, and mechanism — **zero code change**. This ADR simply names their role explicitly: they are the **per-developer** context. In flavor 2.B (no git repo at the root) this is already their de facto behavior today; this ADR just documents it as intentional instead of incidental.
2. **Team tier — new.** `{workspace_root}/agents/project-overview.md` and `agents/project-context.md`: an independent, optional pair a team creates and versions once `agents/` is a dedicated shareable repo (clone or submodule), for conventions/vision the team has explicitly agreed to formalize together.

**No third file.** There is no `.local.md` companion, and no gitignore convention introduced inside `agents/` for context files. An earlier draft of this ADR explored exactly that (a gitignored per-developer file living *inside* the team repo) — rejected; see §5. Personal context already has a home: the root.

**Honest caveat.** In flavor 2.A (monorepo, root *is* a git repo), the root file may already be tracked and shared through that monorepo — this ADR does not change or restrict that pre-existing setup. "Per-developer" describes the role this ADR is designed around and the behavior root already has whenever nothing else makes it shared; it is not a new rule forbidding a team from committing it in a monorepo if that's what they were already doing.

**Merge semantic — pure aggregation, no override.** Unlike ADR-001's cascade, where the most specific tier wins on direct contradiction (a project role overlay beats the shipped base), team and developer context represent different **owners**, not different specificities of the *same* rule — there's no single "correct" winner to pick. The Prompt Manager reads whichever tiers exist and keeps each **labeled by scope** (e.g. a `## Team context` / `## Developer notes` section) rather than silently blending them. **Aggregation order: team first, then developer** — the shared, canonical baseline is read before the individual's personal layer on top, so personal notes read as an addition/deviation from the team baseline, not the other way around. A contradiction between the two stays visible as-is; reconciling it is left to the reader, not the resolver.

## 3. Detailed contract

### 3.1 Developer tier — unchanged

`{workspace_root}/project-overview.md` and `project-context.md`: same resolution, same optionality, same git status as before this ADR. No code path touching them changes. This ADR only adds documentation of their role and one new lookup elsewhere (§3.2).

### 3.2 Team tier — resolution

```text
function resolveTeamContext(file):   # file ∈ {project-overview.md, project-context.md}
    path = workspace_root + "/agents/" + file
    return path if exists(path) else null   # independent of whether the root (developer) file exists
```

### 3.3 Aggregation order in the prompt

The Prompt Manager loads, in this fixed order, every tier that resolves to an existing file, each under its own labeled section — neither tier is skipped because the other exists, and neither overrides the other's content:

1. **Team** (`{workspace_root}/agents/project-overview.md` / `project-context.md`) — new, if present.
2. **Developer** (`{workspace_root}/project-overview.md` / `project-context.md`) — existing, if present.

A workspace can have neither, either, or both files present for a given logical context (overview vs context); whatever exists gets read, in that order.

### 3.4 `setup.sh` scaffolding

- **Root (developer) scaffolding** — unchanged, exactly as today.
- **New, opt-in via detection, no new CLI flag:** if `{workspace_root}/agents/` is itself a git working tree (`git -C "$TARGET_DIR/agents" rev-parse 2>/dev/null` succeeds) and `agents/project-overview.md` / `project-context.md` don't already exist there, scaffold those templates too — the presence of a git-backed `agents/` is the signal that the team wants a shared home, mirroring how the framework already avoids adding config surface for a decision that can be inferred (see ADR-001 §5's rejection of a templating/config layer for the same reason).

### 3.5 Doc/template updates required

- `agents/roles/prompt-manager.md` — dispatch protocol reads and aggregates both tiers (§3.3), each labeled by scope.
- `templates/bootstrap-instructions-workspace.md` — same aggregation, spelled out for the bootstrap steps; make explicit that the root file's role is now named "developer context."
- `docs/getting-started.md` — document the new team pair next to the existing "workspace root (optional)" section; state plainly that nothing about the root files' mechanism changed.
- `docs/extending-layers.md` — clarify `agents/project-overview.md` / `project-context.md` are **not overlays** (no `<!-- OVERLAY -->` header — they're a new file, not an override of the root one).

No change to `bin/validate-overlays.sh` is needed: with exactly two tiers, both optional and both additive, there is no duplication/ambiguity class of bug to detect (unlike the rejected v1 draft's root-vs-`agents/` fallback, where "which one wins" needed a check).

## 4. Consequences

### Positive
- **Zero risk to existing installs** — no behavior change to the root file's mechanism at all; nothing to migrate.
- **Closes the sharing gap** for multi-repo workspaces (flavor 2.B): a team gets a genuinely shareable, versionable home for conventions, exactly like it already has for overlays.
- **Names something that already existed informally** — flavor 2.B's root file was always de facto per-developer; this ADR just gives that a name and a documented purpose instead of leaving it accidental.
- **Simplest possible shape** — exactly two files per context type, both optional, both additive. No precedence rule, no ambiguity detection, no gitignore convention to teach.

### Negative
- **No override means silent divergence is possible** — if the team file and a developer's root file say contradictory things, both are shown to the model as-is; reconciling that is left to the reader (human or LLM). Deliberate trade-off (§2), not an oversight.
- **The "per-developer" framing is only fully accurate in flavor 2.B** — in flavor 2.A (monorepo root), a team that already commits the root file to their shared repo gets a "per-developer" label on something that is, in their setup, actually shared. This ADR doesn't change their behavior, but the documentation should be honest that the label is descriptive of intent, not an enforced guarantee.

### Neutral
- **Cortex still doesn't dictate `agents/` repo topology** — plain folder, clone, or submodule remain equally valid.
- **Service-level context is untouched** — this ADR is scoped to the workspace tier only.
- **Both tiers are optional** — a workspace can adopt neither, either, or both.

## 5. Alternatives considered

| Alternative | Rejected because |
|---|---|
| **Relocate the root file to `agents/` with a root-wins fallback** (an earlier draft of this ADR) | Treated the root file and an `agents/` file as two possible locations for *one* logical file — requiring a precedence rule, a migration story, and an ambiguity-detection check for the "both exist" case. Unnecessary once the root file is recognised as its own tier (developer) rather than a candidate location for the team tier. |
| **Three tiers: root (project-level), `agents/project-overview.md` (team), `agents/project-overview.local.md` (developer, gitignored inside the team repo)** (a second earlier draft) | Explicitly rejected by the maintainer: no `.local.md` file, and no gitignore convention, inside `agents/`. Personal context already has an unambiguous home — the root — so a third file inside the shared repo adds a file to teach and a gitignore rule to maintain for no benefit over what already works. |
| **New dedicated top-level folder** (e.g. `workspace-meta/`) for the team pair, separate from `agents/` | Splits the "one shareable repo" story into two folders to clone/manage instead of one; `agents/` already exists and is already the workspace-shareable concept — reusing it is simpler. |
| **Symlink-only workaround** (document "symlink `project-context.md` into your own repo," no cortex change) | Works as a manual escape hatch but stays invisible to newcomers reading the docs and differs across OSes (Windows symlink permissions); not worth enshrining as *the* first-class answer when a second lookup is this cheap to add. |
| **Force `{workspace_root}/agents/` to always be a git repo/submodule, enforced by `setup.sh`** | Overreaches — cortex has never dictated the host project's repo topology (single clone vs submodule is already the user's call per flavor 2.A/2.B); shouldn't start enforcing it for one folder. |
| **Configurable path via a new config file** (e.g. `.cortex-workspace.yml` naming custom context locations) | Over-engineering for a fixed, small set of well-known filenames; contradicts ADR-001's own rejection of a templating/config layer for a similar reason (§5, "Templating engine" row). |

## 6. Follow-ups (out of scope for this ADR)

1. Implement team-tier resolution + two-tier aggregation in `agents/roles/prompt-manager.md` and `templates/bootstrap-instructions-workspace.md` (§3.2-§3.3).
2. Update `setup.sh --workspace` scaffolding to detect a git-backed `agents/` and offer the team templates there (§3.4); root scaffolding stays untouched.
3. Update `docs/getting-started.md` and `docs/extending-layers.md` (§3.5) — emphasize the root file's mechanism is unchanged, only its documented role (developer context) is new, and document the new team pair.

## 7. References

- [ADR-001 — Layered overrides](ADR-001-layered-overrides.md) — the cascade this ADR deliberately diverges from for context files (aggregation instead of most-specific-wins)
- [docs/getting-started.md](../getting-started.md) — workspace mode flavors 2.A/2.B
- [docs/extending-layers.md](../extending-layers.md) — overlay convention `agents/` already hosts
- [templates/bootstrap-instructions-workspace.md](../../templates/bootstrap-instructions-workspace.md) — bootstrap steps that read workspace context
- [agents/roles/prompt-manager.md](../../agents/roles/prompt-manager.md) — dispatch protocol
