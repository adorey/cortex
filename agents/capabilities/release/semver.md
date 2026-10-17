# Semantic Versioning (SemVer) — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for Semantic Versioning 2.0.0.
To combine with a role (e.g. roles/engineering/platform-engineer.md, lead-backend.md, architect.md, communication/tech-writer.md).
Contains NO language- or framework-specific references — versioning methodology only.
-->

> **Reference version:** SemVer 2.0.0 | **Last updated:** 2026-05
> **Official spec:** [semver.org](https://semver.org/spec/v2.0.0.html)

---

## 🏛️ Fundamental principles

### 1. The MAJOR.MINOR.PATCH contract

```
  1   .   4   .   2
  │       │       │
  │       │       └── PATCH → backward-compatible bug fix
  │       └────────── MINOR → backward-compatible new feature
  └────────────────── MAJOR → backward-incompatible change (BREAKING)
```

**Rules:**
- A version MUST take the form `X.Y.Z` where X, Y, Z are non-negative integers without leading zeros.
- Once a versioned package has been released, the contents of that version MUST NOT be modified. Any change MUST be released as a new version.
- Version `0.y.z` is the **initial development phase** — anything MAY change at any time. The public API SHOULD NOT be considered stable.
- Version `1.0.0` defines the **public API**. From that moment on, every increment is dictated by the nature of the change.

### 2. When to bump what

| Change type | Bump | Example |
|---|---|---|
| Bug fix, no API change | **PATCH** | `1.4.2` → `1.4.3` |
| Backward-compatible feature added | **MINOR** | `1.4.3` → `1.5.0` |
| Backward-incompatible change | **MAJOR** | `1.5.0` → `2.0.0` |
| Public API marked deprecated | **MINOR** | The removal will trigger MAJOR later |
| Refactor with no public API change | **PATCH** | Internal-only |

**Rule:** When you bump MINOR, PATCH MUST reset to `0`. When you bump MAJOR, MINOR and PATCH MUST reset to `0`.

```
1.4.7 → MINOR bump → 1.5.0   ✅  (not 1.5.7)
1.5.0 → MAJOR bump → 2.0.0   ✅  (not 2.5.0)
```

### 3. What counts as a BREAKING change

A change is **MAJOR** (breaking) if it forces consumers to modify their code:

- Removing or renaming a public endpoint, parameter, field, function, class, env var, CLI flag, config key.
- Changing a response shape (removed field, type change, semantic change).
- Tightening validation rules that previously accepted certain inputs.
- Changing default behaviour in a way that flips an observable outcome.
- Raising a minimum required dependency / runtime version (PHP, Node, browser…).
- Changing the wire format of an event, queue message, or persisted artifact.

A change is **MINOR** (additive) if it strictly adds capability:

- New endpoint, optional parameter, optional field in response.
- New event type that subscribers can opt into.
- New optional config key with a sensible default that preserves prior behaviour.

A change is **PATCH** if it is invisible to a correctly-written consumer:

- Bug fix that brings the code in line with documented behaviour.
- Performance improvement, refactor, dependency security update with no observable API change.

### 4. Pre-release identifiers

```
1.0.0-alpha           Pre-release, lower precedence than 1.0.0
1.0.0-alpha.1         Numbered pre-release
1.0.0-beta.2
1.0.0-rc.1            Release candidate
1.0.0                 Stable release
```

**Precedence (sorting):**
```
1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta
< 1.0.0-beta < 1.0.0-beta.2 < 1.0.0-beta.11
< 1.0.0-rc.1 < 1.0.0
```

Identifiers MUST be ASCII alphanumerics + hyphens, separated by dots, no leading zeros on numeric identifiers.

### 5. Build metadata

```
1.0.0+20260508         Build metadata after the +
1.0.0-rc.1+exp.sha.5114f85
```

Build metadata is **ignored** for precedence comparisons. Use it to attach build info (commit SHA, CI build number) without affecting version ordering.

---

## 📐 Recommended patterns

### Initial version & 0.y.z phase

```
0.1.0   First public draft, internal API can change at any time
0.x.y   Increment freely while the API is unstable
1.0.0   First public stable release — API is now a contract
```

**Rule:** Do not stay below `1.0.0` once consumers depend on you in production. Cutting `1.0.0` is the moment you commit to SemVer discipline.

### Deprecation flow before a MAJOR bump

```
1.4.0  Feature A introduced
1.7.0  Feature A marked @deprecated, replacement B introduced (MINOR — additive)
2.0.0  Feature A removed (MAJOR — breaking)
```

**Always provide at least one MINOR cycle of deprecation** before removing a feature in a MAJOR.

### Version ranges in dependency manifests

```json
// package.json — Node ecosystem
{
  "dependencies": {
    "express":   "^4.18.0",   // ✅ >=4.18.0 <5.0.0  — accept MINOR + PATCH
    "lodash":    "~4.17.21",  // ✅ >=4.17.21 <4.18.0 — accept PATCH only
    "react":     "18.2.0"     // ⚠️  pinned — security updates blocked
  }
}
```

```json
// composer.json — PHP ecosystem
{
  "require": {
    "symfony/console":  "^7.0",   // ✅ >=7.0.0 <8.0.0
    "doctrine/orm":     "~3.1.0", // ✅ >=3.1.0 <3.2.0
    "vendor/lib":       "3.1.4"   // ⚠️  pinned
  }
}
```

**Rule:** In libraries published to others, prefer `^X.Y.Z` (MINOR + PATCH compatible). In application repos with a lockfile (`package-lock.json`, `composer.lock`), exact reproducibility is given by the lockfile — keep `^` constraints to allow security patches.

### Conventional Commits → SemVer mapping

When the project uses [Conventional Commits](https://www.conventionalcommits.org/), the bump can be derived automatically:

| Commit type | Bump |
|---|---|
| `fix:` | PATCH |
| `feat:` | MINOR |
| `feat!:` or any commit with `BREAKING CHANGE:` footer | MAJOR |
| `chore:`, `docs:`, `style:`, `refactor:`, `test:`, `ci:` | No bump |

```
feat: add geo-routing constraint resolver        → MINOR
fix: prevent NaN in elevation gain calculation   → PATCH
feat!: rename /routes endpoint to /itineraries   → MAJOR
```

This is the foundation of automated release tooling (release-please, semantic-release, changesets).

### Multi-package / monorepo strategies

| Strategy | Description | When to use |
|---|---|---|
| **Fixed / locked** | All packages share one version, bumped together (Lerna fixed mode) | Monorepo where packages are tightly coupled |
| **Independent** | Each package has its own SemVer line | Independent libraries published to a registry |
| **Workspace + per-service tags** | Each service in the workspace tags `service-name@vX.Y.Z` | Polyglot workspace with independently-deployed services |

> The right strategy depends on **deployment coupling**: if services ship together, lock the version; if they ship independently, version them independently. The project-level overlay should record which strategy is in force.

### Git tagging convention

```bash
# ✅ Annotated tag, signed when possible
git tag -a v1.4.2 -m "release v1.4.2"
git push origin v1.4.2

# ✅ Pre-release tag
git tag -a v2.0.0-rc.1 -m "release candidate 2.0.0-rc.1"
```

**Rule:** Always prefix the tag with `v`. Always use **annotated** tags (`-a`), never lightweight tags, so the release author and date are recorded.

### Release artefacts must match the tag

The version inside `package.json` / `composer.json` / `__version__` / etc. MUST match the git tag. Tooling that reads the version at build time MUST read it from the manifest, not from a hard-coded constant duplicated elsewhere.

### CHANGELOG discipline

Keep a `CHANGELOG.md` at the repo root, following [Keep a Changelog](https://keepachangelog.com/) sections:

```markdown
## [1.5.0] - 2026-05-08

### Added
- New `/itineraries/{id}/elevation` endpoint.

### Changed
- `/routes` response now paginates by default (page size: 25).

### Deprecated
- `/routes` legacy field `distance_m` — use `distance.meters` instead.

### Removed
- (nothing yet)

### Fixed
- Elevation gain miscalculation for routes crossing the antimeridian.

### Security
- Bumped `symfony/http-kernel` to address CVE-2026-XXXX.
```

The CHANGELOG is the **source of truth** for what changed; the SemVer bump follows from the sections present (`Removed` or anything labelled BREAKING → MAJOR; `Added` → MINOR; only `Fixed` / `Security` → PATCH).

---

## 🚫 Anti-patterns

### NEVER do this

```
❌ 1.0 → 1.1 → 1.2          # Two-segment versions are not SemVer
❌ 1.4.07                   # Leading zeros are forbidden
❌ v1.4.2-FINAL-final-2     # Use pre-release identifiers, not free-form suffixes
❌ Bumping MINOR without resetting PATCH (1.4.7 → 1.5.7)
❌ Re-tagging an existing version (force-pushing v1.4.2 to a new commit)
❌ Releasing breaking changes as MINOR or PATCH "because the change is small"
❌ Hiding a removal as a "fix" to avoid a MAJOR bump
❌ Bumping the version manually in 4 different files and hoping they stay in sync
```

### Prefer

| ❌ Avoid | ✅ Prefer |
|---|---|
| Free-form suffixes (`-FINAL`, `-prod`) | Spec-compliant pre-release (`-alpha.1`, `-rc.2`) |
| Lightweight git tags | Annotated tags (`git tag -a`) |
| Pinning every dep to an exact version | `^X.Y.Z` + lockfile |
| Manual version bumping across multiple files | Single source (manifest) + automated tooling |
| Breaking change in a MINOR "to avoid alarming users" | Honest MAJOR bump + migration guide |
| Skipping the CHANGELOG | CHANGELOG entry per release, mandatory in PR template |
| Tagging from a feature branch | Tag only on the release branch (`main` / `release/*`) |

---

## 🔧 Recommended tooling

| Tool | Ecosystem | Role |
|---|---|---|
| [release-please](https://github.com/googleapis/release-please) | Polyglot (Node, PHP, Python, Go…) | Automated releases driven by Conventional Commits, opens a "Release PR" on each merge to main |
| [semantic-release](https://semantic-release.gitbook.io/) | Node-first | Fully automated release on every merge (bump + tag + changelog + publish) |
| [changesets](https://github.com/changesets/changesets) | Monorepo / npm workspaces | Per-PR changeset files, ideal for monorepos with independent packages |
| [standard-version](https://github.com/conventional-changelog/standard-version) | Node | Local-only changelog + bump (no publish) |
| `npm version` / `composer config version` | Node / PHP | Manual bump aligned with the manifest |
| [commitlint](https://commitlint.js.org/) | Polyglot | Enforces Conventional Commits in pre-commit / CI |
| [svu](https://github.com/caarlos0/svu) | Go / shell | Computes the next SemVer from git history |

**Choosing a tool:**
- **Solo developer / small team, manual control wanted** → `standard-version` or manual `npm version` / `composer config version` + a hand-written `CHANGELOG.md`.
- **Single Node package, full automation** → `semantic-release` (publishes to npm on every merge to main).
- **Polyglot or multi-service repository** → `release-please` (Release PR pattern, supports many manifest formats, no surprise releases).
- **Monorepo with multiple independently-versioned packages** → `changesets` (per-PR changeset files reviewed by humans).

In all cases, **combine the tool with [Conventional Commits](https://www.conventionalcommits.org/) or a similarly machine-parseable convention** in commit messages or PR titles, so the bump can be derived automatically.

---

## 🧭 Decision flowchart — "Which bump?"

```
                  ┌──────────────────────────┐
                  │ Is the public API broken?│
                  └────────────┬─────────────┘
                               │
                  ┌────yes─────┴────no──────┐
                  ▼                         ▼
              MAJOR bump          ┌─────────────────────┐
              (X+1.0.0)           │ Was new behaviour   │
                                  │ added?              │
                                  └────────┬────────────┘
                                           │
                                ┌──yes─────┴────no──────┐
                                ▼                       ▼
                            MINOR bump              PATCH bump
                            (X.Y+1.0)               (X.Y.Z+1)
```

> When in doubt between PATCH and MINOR → choose MINOR.
> When in doubt between MINOR and MAJOR → choose MAJOR. Consumers will thank you for the honest signal.

---

## ✅ Quick checklist

```
- [ ] Version is X.Y.Z (three segments, no leading zeros)
- [ ] Tag is prefixed with `v` and annotated (`git tag -a`)
- [ ] Manifest version (package.json / composer.json / pyproject.toml…) matches the tag
- [ ] Bump category matches the change (BREAKING → MAJOR, additive → MINOR, fix → PATCH)
- [ ] Lower segments reset to 0 when a higher segment bumps
- [ ] CHANGELOG.md entry written for this release (Keep a Changelog format)
- [ ] Pre-release identifiers (-alpha / -beta / -rc) used for unstable releases
- [ ] Deprecations announced in a MINOR before being removed in a MAJOR
- [ ] No hard-coded version duplicated across files (single source of truth)
- [ ] Conventional Commits used in commit messages / PR titles to enable automation
- [ ] Release artefact published only after CI is green on the tagged commit
```
