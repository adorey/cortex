# Changelog Discipline — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for changelog management.
To combine with a role (e.g. roles/communication/tech-writer.md, roles/engineering/lead-backend.md).
Reference: Keep a Changelog 1.1.0.
-->

> **Reference:** [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
> **Last updated:** 2026-05

---

## 🏛️ Fundamental principles

### 1. A changelog is for humans

A changelog is **not** the git log. A git log records every commit; a changelog records every **notable** change, written so a non-author can understand it without reading the diff.

```
Audience          | Source of truth
------------------|----------------------
Machines          | git log + tags
Humans (devs)     | CHANGELOG.md
End-users         | Release notes / blog
```

### 2. One canonical file: `CHANGELOG.md` at the repo root

```
repo/
├── CHANGELOG.md        ✅ The single source of truth
├── README.md           ✅ Links to CHANGELOG.md from "Releases" section
└── ...
```

**Rule:** never split a changelog across multiple folders or files. Tooling, GitHub UIs, package registries, and dependency bots all look for `CHANGELOG.md` at the root by convention.

> *If you need a richer narrative per release (with prose, diagrams, migration walkthroughs), that's **release notes** — see "Changelog vs release notes" below.*

### 3. Reverse chronological order

Most recent release at the top. New consumers care about what is current; archeology comes later.

### 4. Every release is linkable

Each version section should be a Markdown anchor that maps to a git tag and ideally to a compare URL.

```markdown
## [1.5.0] - 2026-05-08

### Added
- New `/itineraries/{id}/elevation` endpoint.

[1.5.0]: https://github.com/org/repo/compare/v1.4.2...v1.5.0
[1.4.2]: https://github.com/org/repo/compare/v1.4.0...v1.4.2
```

### 5. The `[Unreleased]` buffer

A permanent section at the top that accumulates entries between releases. Emptied (renamed `[X.Y.Z] - DATE`) on each release.

```markdown
## [Unreleased]

### Added
- New `/health` endpoint (in progress).

## [1.5.0] - 2026-05-08
...
```

This is what enables **per-PR discipline**: every PR adds its line to `[Unreleased]`, no last-minute scramble before the release.

### 6. Released sections are immutable

Once `[1.5.0]` is published, you don't edit it. Errata go to a new patch (`[1.5.1]`), not into the past.

---

## 📐 The 6 canonical sections

Use only these section titles. They map cleanly to SemVer bump categories.

| Section | When to use | SemVer impact |
|---|---|---|
| `### Added` | New features, new endpoints, new optional config | MINOR |
| `### Changed` | Behaviour changes, defaults, deprecation announcements | MINOR (or MAJOR if breaking) |
| `### Deprecated` | Features marked for future removal | MINOR (additive — the removal triggers MAJOR later) |
| `### Removed` | Features actually deleted | **MAJOR** |
| `### Fixed` | Bug fixes | PATCH |
| `### Security` | Security fixes (CVEs, vulnerabilities) | PATCH (and surfaced prominently) |

A release with **only** `Fixed` / `Security` sections → PATCH bump.
Any `Added` / `Changed` (non-breaking) → MINOR bump.
Any `Removed` (or `Changed` with breaking semantics) → MAJOR bump.

> Use the section titles **even if the section is empty** to make the diff loud and clear. Better one empty heading than a forgotten category.

---

## ✍️ Writing entries

### Audience-oriented phrasing

```markdown
❌ refactor: extract route normalisation into a service
✅ Routes returned by `/itineraries` now consistently include a normalised
   `distance.meters` field whether the source data was metric or imperial.

❌ fix: bump lodash to 4.17.21
✅ Pinned `lodash` to 4.17.21 to address [CVE-2021-23337]
   (prototype pollution).

❌ feat: implement option XYZ
✅ Added `options.xyz` (default: `false`) to opt into the new XYZ behaviour;
   existing callers see no change.
```

**Rule of thumb:** if a reader who never saw your codebase cannot tell from the entry whether it affects them, the entry is useless. Re-write it.

### Linking to issues, PRs, and CVEs

```markdown
### Fixed
- Elevation gain miscalculation for routes crossing the antimeridian
  ([#142](https://github.com/org/repo/pull/142), thanks @contributor).

### Security
- Updated `symfony/http-kernel` to 6.4.7 to address
  [CVE-2026-XXXX](https://github.com/advisories/GHSA-xxxx-xxxx-xxxx).
```

Footer-style links keep the body readable:

```markdown
- Elevation miscalculation for antimeridian-crossing routes [#142].

[#142]: https://github.com/org/repo/pull/142
```

### Documenting BREAKING changes — migration block

For any BREAKING change, embed a migration snippet inside the entry:

```markdown
## [2.0.0] - 2026-06-01

### Changed
- **BREAKING:** renamed `/routes` endpoint to `/itineraries`.

  > **Migration:**
  > ```diff
  > - GET /routes?profile=hike
  > + GET /itineraries?profile=hike
  > ```
  > The legacy path returns `410 Gone` from 2.0.0 onwards. A `Link: </itineraries>; rel="successor-version"` header is included to help automated migration.

### Removed
- Removed deprecated `routes.distance_m` field. Use `distance.meters` instead
  (deprecated since 1.7.0).
```

---

## 🆚 Changelog vs release notes — they are not the same

| | Changelog (`CHANGELOG.md`) | Release notes (GitHub Release body, blog post) |
|---|---|---|
| Format | Structured, terse, 6 canonical sections | Free-form narrative |
| Audience | Developers, dependency bots, package consumers | End-users, stakeholders, marketing |
| Content | "What changed" | "What this release means, why it matters, how to use it" |
| Length | A few lines per entry | Multiple paragraphs, screenshots, diagrams |
| Generation | Often automated (release-please, changesets, git-cliff) | Often hand-crafted, sometimes seeded from changelog |
| Mutability | Immutable once released | Editable on the platform |

**Both can co-exist.** A common, healthy pattern:
- The changelog (machine-friendly) is auto-generated from Conventional Commits.
- The release notes (human-friendly) are written by the tech writer / release manager and posted as the GitHub Release body, sometimes embedding the changelog at the bottom.

Some teams keep richly-narrated release notes in a **separate folder** like `release-notes/v1.5.0.md` — that is fine and *complementary* to `CHANGELOG.md`, not a replacement for it. The folder approach for **narrative** content is legitimate; only the structured changelog itself must stay a single file.

---

## 🔁 Per-PR workflow patterns

Three patterns for keeping the changelog up-to-date with minimal overhead:

### A. Manual `[Unreleased]` discipline

Each PR adds its line under `[Unreleased]`. Reviewers check the entry exists and is well-phrased.

```
Pros : human-controlled, rich phrasing, no tooling.
Cons : easy to forget, merge conflicts when many PRs target the same section.
```

### B. Conventional Commits + auto-generation

Each PR title follows Conventional Commits (`feat:` / `fix:` / `feat!:`). A tool (release-please, changesets, git-cliff) generates the changelog automatically at release time.

```
Pros : zero per-PR overhead beyond the title prefix.
Cons : entries inherit the commit-message phrasing — sometimes terse.
```

### C. Hybrid — auto-generate + curate

Tooling drafts the changelog; the release manager edits the draft for clarity before merging the release. This is what `release-please` enables natively (the "Release PR" *is* the curation moment).

```
Pros : best of both worlds — automation does the boring work, humans polish.
Cons : requires a maintainer to actually do the polishing pass.
```

**Recommendation:** start with **C (hybrid)**. It scales from solo to large teams.

---

## 🚫 Anti-patterns

```
❌ "Misc improvements" / "Various fixes" / "Bump dependencies"
   → empty noise; describe what actually changed.

❌ Pasting raw `git log --oneline` output as the changelog.

❌ Mixing categories: a fix listed under `### Added`.

❌ Editing a released section to "correct" history.

❌ Internal-only refactor entries with no observable user impact.
   ("Extracted helper into utils/") — keep these in the commit log.

❌ Multi-language CHANGELOGs that drift apart over time.
   If you must localise, generate the second language from the first.

❌ Forgetting to advance `[Unreleased]` → `[X.Y.Z]` at release time.

❌ Splitting the changelog into per-version files in a folder.
   This breaks every consumer that expects `CHANGELOG.md` at the root
   (GitHub UI, dependabot, npm, Packagist, release-please).
```

### Prefer

| ❌ Avoid | ✅ Prefer |
|---|---|
| "Fix bug" | "Fixed timezone offset bug in `/imports` for routes crossing the antimeridian" |
| "Update dep" | "Bumped `symfony/http-kernel` to 6.4.7 (CVE-2026-XXXX)" |
| "Refactor" | If user-visible: describe the change. If not: omit from changelog. |
| Folder of `vX.Y.Z.md` files | One `CHANGELOG.md` + optional separate `release-notes/` for narrative |
| Cryptic shortcodes | Plain English |

---

## 🔧 Tooling

| Tool | Type | When to use |
|---|---|---|
| [release-please](https://github.com/googleapis/release-please) | Auto-bump + auto-changelog | Polyglot repos / multi-package monorepos with a "Release PR" gate |
| [semantic-release](https://semantic-release.gitbook.io/) | Auto-bump + auto-publish | Node-first, high-trust automation, no human gate |
| [changesets](https://github.com/changesets/changesets) | Per-PR `.changeset/*.md` | Monorepos where rich, curated entries are valued |
| [git-cliff](https://git-cliff.org/) | Local changelog generation | Polyglot, fully customizable templates, no service dependency |
| [conventional-changelog-cli](https://github.com/conventional-changelog/conventional-changelog) | Local Node-only generation | Simple Node projects |
| commitlint | PR-title / commit linting | Enforce Conventional Commits format in CI |

---

## ✅ Quick checklist

```
- [ ] Single CHANGELOG.md at the repo root (no folder, no split)
- [ ] Reverse chronological order (newest at top)
- [ ] [Unreleased] section present, used as buffer
- [ ] Sections are exactly: Added / Changed / Deprecated / Removed / Fixed / Security
- [ ] Each entry is intelligible to someone who never saw the code
- [ ] Issue / PR / CVE links present where relevant
- [ ] BREAKING entries include a Migration block
- [ ] Released sections are not edited after publication
- [ ] Compare URLs at the bottom (one per version)
- [ ] CHANGELOG entry verified in every PR (CI check or PR template)
- [ ] Release-time: rename [Unreleased] → [X.Y.Z] - DATE
- [ ] Optional: separate release-notes/ folder for rich narrative content
```
