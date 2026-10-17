# release-please — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for release-please (Google).
To combine with a role (e.g. roles/engineering/platform-engineer.md, lead-backend.md).
Companion: capabilities/release/semver.md, capabilities/release/changelog.md, capabilities/release/conventional-commits.md.
-->

> **Reference version:** release-please-action v4.x | **Last updated:** 2026-05
> **Official docs:** [github.com/googleapis/release-please](https://github.com/googleapis/release-please)

---

## 🧠 Mental model

### The "Release PR" pattern

release-please does **not** release on every merge. It does **not** create release branches. It maintains **one continuously-updated pull request** on the default branch:

```
main ──────────●─────●─────●─────●──────●─────●─────►
               │     │     │     │      │     │
               │     │     │     │      │     │   ┌─────────────────┐
               └─────┴─────┴─────┴──────┴─────┴──►│ Release PR #142 │
                                                  │ chore: release  │
                                                  │      1.5.0      │
                                                  └────────┬────────┘
                                                           │
                                                  reviewed │ merged by
                                                  by maintainer  ▼
                                                  ┌──────────────────┐
                                                  │  tag v1.5.0      │
                                                  │  GitHub Release  │
                                                  └──────────────────┘
```

**Properties of the Release PR:**
- Opened automatically the first time a `feat:` / `fix:` lands after a release.
- Re-written automatically on every subsequent merge to the default branch.
- Contains **only** version bump + changelog update — never application code.
- **Nobody commits into it.** Manual edits are overwritten on the next reconciliation.
- Merging it triggers tag creation + GitHub Release creation.

**Source of truth = git history.** No state file. Each run reads commits since the last tag and re-derives the next version.

### Why this design wins

- **Decoupled from CI/CD** : the tool only owns version + changelog. Build and deploy hook on the resulting tag.
- **Human in the loop** : merging the Release PR is a deliberate go/no-go gate.
- **Polyglot-friendly** : the same model works for Node, PHP, Python, Go, Rust, plain text.
- **Stateless** : losing the action's history doesn't lose your release state.

---

## 🏛️ Fundamental principles

### 1. Conventional Commits are mandatory

Without `feat:` / `fix:` prefixes (or equivalent), release-please cannot derive a bump. It will simply not open a Release PR.

```
✅ feat: add /elevation endpoint    →  MINOR bump candidate
✅ fix: timezone offset in imports   →  PATCH bump candidate
✅ feat!: rename /routes            →  MAJOR bump candidate
❌ Update README                     →  ignored (no prefix)
❌ work in progress                  →  ignored
```

→ Combine with `commitlint` or a CI check that rejects PRs whose **squash-merge title** doesn't match Conventional Commits.

### 2. One config, one manifest

Two files at the repo root drive everything:

```
release-please-config.json       # what to release, how
.release-please-manifest.json    # current version of each package
```

The action **reads and writes** the manifest — it is your single source of truth for "what version is this repo currently at?".

### 3. `release-type` per package

The `release-type` tells release-please which manifest format to update.

| `release-type` | Reads/writes | Use for |
|---|---|---|
| `node` | `package.json`, `package-lock.json` | npm packages, Node apps |
| `php` | `composer.json` | Composer packages, Symfony apps |
| `python` | `pyproject.toml` / `setup.cfg` / `setup.py` | Python projects |
| `go` | `version.go` (configurable) | Go modules |
| `rust` | `Cargo.toml`, `Cargo.lock` | Rust crates |
| `simple` | A single `version.txt` file (path configurable) | Anything that doesn't fit the above (infra repos, frameworks, docs) |
| `helm` | `Chart.yaml` | Helm charts |
| `terraform-module` | `versions.tf` | Terraform modules |

→ The full list is in the [release-please docs](https://github.com/googleapis/release-please/blob/main/docs/manifest-releaser.md).

### 4. Permissions stay minimal

```yaml
permissions:
  contents: write          # to create tags and push the Release PR
  pull-requests: write     # to open and update the Release PR
```

Nothing else. The action does not need workflow access, packages access, or admin.

### 5. The first run requires a seeded version

A repo that has never used release-please needs to know "where am I?". Seed `.release-please-manifest.json` with the current version before the first run:

```json
{
  ".": "1.4.2"
}
```

Without this, release-please will open a Release PR for `1.0.0` (or worse, fail to detect prior tags).

---

## 📐 Configuration patterns

### Single-package repo (most common)

`release-please-config.json` :

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "node",
  "packages": {
    ".": {
      "package-name": "my-app",
      "changelog-path": "CHANGELOG.md",
      "include-component-in-tag": false,
      "draft": false,
      "prerelease": false
    }
  }
}
```

`.release-please-manifest.json` :

```json
{
  ".": "1.4.2"
}
```

`.github/workflows/release-please.yml` :

```yaml
name: release-please

on:
  push:
    branches: [main]

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        with:
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
```

### Multi-package monorepo

`release-please-config.json` :

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "packages": {
    "packages/core": {
      "release-type": "node",
      "package-name": "@org/core",
      "changelog-path": "CHANGELOG.md"
    },
    "packages/cli": {
      "release-type": "node",
      "package-name": "@org/cli",
      "changelog-path": "CHANGELOG.md"
    }
  },
  "plugins": [
    {
      "type": "linked-versions",
      "groupName": "main",
      "components": ["@org/core", "@org/cli"]
    }
  ]
}
```

The `linked-versions` plugin keeps both packages on the same version. Omit it to let each package version independently.

### Custom changelog sections

By default, only `feat:` and `fix:` produce changelog entries. To surface more:

```json
{
  "changelog-sections": [
    { "type": "feat",     "section": "Features" },
    { "type": "fix",      "section": "Bug Fixes" },
    { "type": "perf",     "section": "Performance" },
    { "type": "deps",     "section": "Dependencies" },
    { "type": "revert",   "section": "Reverts" },
    { "type": "docs",     "section": "Documentation", "hidden": false },
    { "type": "chore",    "section": "Miscellaneous", "hidden": true }
  ]
}
```

`hidden: true` keeps the type recognised but excluded from the changelog.

### Synchronising version into extra files

When a Dockerfile, OpenAPI spec, helm chart, or any other file embeds the version, declare it as `extra-files`:

```json
{
  "packages": {
    ".": {
      "release-type": "node",
      "extra-files": [
        "Dockerfile",
        { "type": "json", "path": "openapi.json", "jsonpath": "$.info.version" },
        { "type": "yaml", "path": "helm/Chart.yaml", "jsonpath": "$.appVersion" }
      ]
    }
  }
}
```

Inside `Dockerfile`, mark the line release-please should rewrite:

```dockerfile
LABEL version="1.4.2" # x-release-please-version
```

The `# x-release-please-version` annotation is the marker the action looks for.

### Pre-release branches

For an `alpha` / `beta` / `rc` cadence, point release-please at a non-default branch:

```yaml
on:
  push:
    branches: [main, next]

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        with:
          target-branch: ${{ github.ref_name }}   # main or next
```

And declare the prerelease type per branch in the config:

```json
{
  "branches": {
    "main": { "release-type": "node" },
    "next": { "release-type": "node", "prerelease": true, "prerelease-type": "rc" }
  }
}
```

---

## 🔁 The full lifecycle

```
1. Developer opens PR with title "feat: add X" (commitlint validated in CI).
2. Developer merges PR via squash merge → main now contains a "feat: add X" commit.
3. release-please action runs on push to main:
     a. Reads commits since last tag.
     b. Detects "feat" → bump candidate is MINOR.
     c. Updates or creates the Release PR with:
        - manifest version bumped (e.g. 1.4.2 → 1.5.0)
        - CHANGELOG.md updated with new "[1.5.0] - YYYY-MM-DD" section
        - .release-please-manifest.json updated
4. Other PRs merge over time → Release PR is re-derived each time.
5. Maintainer reviews the Release PR (changelog phrasing, version), edits any wording, merges.
6. release-please action runs again on push to main:
     a. Detects the Release PR was merged → creates tag v1.5.0.
     b. Creates GitHub Release with the changelog body.
7. Downstream workflows (build / publish / deploy) hook on:
     - push of tag v* (use `on: push: tags: ['v*']`)
     - or release-please outputs (e.g. `if: ${{ steps.release.outputs.release_created }}`)
```

### Hooking the build/deploy pipeline

```yaml
jobs:
  release-please:
    runs-on: ubuntu-latest
    outputs:
      release_created: ${{ steps.release.outputs.release_created }}
      tag_name:        ${{ steps.release.outputs.tag_name }}
    steps:
      - uses: googleapis/release-please-action@v4
        id: release
        with:
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json

  build-and-publish:
    needs: release-please
    if: ${{ needs.release-please.outputs.release_created == 'true' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ needs.release-please.outputs.tag_name }}
      # ... build, publish, deploy ...
```

This guarantees the build runs **only** on tagged commits, never on intermediate `main` pushes.

---

## 🚫 Anti-patterns

```
❌ git tag + git push --tags manually while release-please is active
   → release-please loses track; it expects to be the only tagger.

❌ Editing the Release PR body or its commits to "fix the changelog"
   → overwritten on next reconciliation. Edit phrasing through commit messages
     instead, or use the `Release-As: X.Y.Z` footer to override the bump.

❌ Squash-merging a `feat: …` PR with a generic squash title
   ("Update routes (#142)") → the prefix is lost, no bump triggered.
   → Configure GitHub repo to default the squash title to the PR title,
     and enforce commitlint on PR titles.

❌ Running release-please AND semantic-release on the same repo.

❌ Forgetting `permissions: contents: write, pull-requests: write` in the workflow.

❌ Forgetting to seed `.release-please-manifest.json` for an existing repo
   → release-please starts from `1.0.0` or guesses badly.

❌ Using `include-component-in-tag: true` on a single-package repo
   → tags become `package-name-v1.0.0` instead of `v1.0.0`, breaking conventions.
```

---

## 🩺 Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No Release PR created after merging `feat:` | Squash title lost the prefix | Force PR-title-as-squash-title; enforce commitlint |
| Release PR shows wrong starting version | Manifest not seeded or stale | Edit `.release-please-manifest.json` to current version |
| Tag created but no GitHub Release | Workflow lacks `contents: write` permission | Update workflow `permissions:` |
| Pre-release identifiers not appearing | `prerelease: true` missing in config | Add it to the `next` branch config |
| Multiple manifests bumped together | `linked-versions` plugin enabled when not wanted | Remove the plugin or split into independent groups |
| `feat:` ignored | Commit had `BREAKING CHANGE:` footer that was malformed | Footer must be exactly `BREAKING CHANGE: …` (uppercase, with colon) |
| Want to force a specific version | Add `Release-As: 2.0.0` footer in any commit since last release | release-please uses it for the next bump |

---

## 🔗 Companion capabilities

- **`release/semver.md`** — what bump rules release-please applies.
- **`release/changelog.md`** — what `CHANGELOG.md` format the action produces (Keep a Changelog).
- **`release/conventional-commits.md`** — the input contract that drives the bump.

These four cards compose the full "release engineering" toolkit. A role that loads all four can reason end-to-end about versioning, commit conventions, changelog generation, and tooling orchestration.

---

## ✅ Quick checklist

```
- [ ] release-please-config.json present at repo root
- [ ] .release-please-manifest.json present and seeded with current version
- [ ] .github/workflows/release-please.yml present
- [ ] Workflow has permissions: contents:write + pull-requests:write
- [ ] Conventional Commits enforced (commitlint in CI on PR titles)
- [ ] Squash-merge default-title = PR title (repo settings)
- [ ] Build/deploy pipeline triggered by `release_created == 'true'` or tag push
- [ ] Single-package repos use include-component-in-tag: false
- [ ] Multi-package repos document the linking strategy (linked-versions or independent)
- [ ] Manual git tag commands forbidden in team docs
- [ ] No semantic-release or other auto-tagger in parallel
- [ ] CHANGELOG.md generation verified on first dry-run
```
