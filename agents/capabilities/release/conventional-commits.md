# Conventional Commits — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for the Conventional Commits specification.
To combine with a role (e.g. roles/engineering/lead-backend.md, lead-frontend.md, platform-engineer.md).
Companion: capabilities/release/semver.md, capabilities/release/changelog.md, capabilities/release/release-please.md.
-->

> **Reference:** [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
> **Last updated:** 2026-05

---

## 🏛️ Fundamental principles

### 1. The contract

A Conventional Commit is a commit message (or PR title) of the form:

```
<type>[optional scope][!]: <description>

[optional body]

[optional footer(s)]
```

```
feat(routing): add /elevation endpoint

Resolves long-standing user request for elevation profiles.
Backed by SRTM data through the GraphHopper adapter.

Refs: #142
```

### 2. The type drives the SemVer bump

Conventional Commits is the **input contract** that lets tooling derive a SemVer bump automatically.

| Type | Default SemVer impact | Changelog section (default) |
|---|---|---|
| `feat` | MINOR | Features / Added |
| `fix` | PATCH | Bug Fixes / Fixed |
| `perf` | PATCH | Performance |
| `revert` | PATCH (or MAJOR if reverting a feat) | Reverts |
| `docs` | none | hidden by default |
| `style` | none | hidden |
| `refactor` | none | hidden |
| `test` | none | hidden |
| `build` | none | hidden |
| `ci` | none | hidden |
| `chore` | none | hidden |

**Two BREAKING markers** force a MAJOR bump:
- An exclamation mark after the type/scope: `feat!: rename /routes` or `feat(api)!: …`
- A footer line starting with `BREAKING CHANGE:` (case-sensitive, with a colon).

```
feat!: drop Node 18 support

BREAKING CHANGE: minimum Node version is now 20.
```

Either one is enough. Both can co-exist.

### 3. The PR title is what the squash merge keeps

In repos that squash-merge PRs (the default for many teams), the **PR title becomes the commit message** on the default branch. This means:

- Enforce Conventional Commits on **PR titles**, not just commits.
- Set the GitHub repo to default the squash commit title to the PR title (Settings → General → Pull Requests).
- A single non-conforming PR title = a missed bump.

### 4. The body explains *why*

The first line ("description") explains *what*. The body, if present, explains *why* — context, trade-offs, links to issues, screenshots.

```
✅ feat(routing): add /elevation endpoint

   Users requested per-segment elevation profiles for ride planning.
   We considered computing elevation client-side from PMTiles, but the
   accuracy was insufficient for hike profiles. This route computes
   elevation server-side from SRTM and caches the result for 24h.

   Closes #142.
```

The body is what shows up in the auto-generated changelog when tools support multi-line entries.

### 5. Scopes are optional but useful

Scopes narrow down the area of change. They're not enumerated in the spec — pick a small, stable set for your repo.

```
feat(routing): ...        # routing module
feat(api): ...            # API layer
fix(deps): ...            # dependency fix
fix(ci): ...              # CI pipeline fix
```

→ A repo with too many scopes (`feat(util.helpers.string)`) loses the readability benefit. Keep the scope set to ~5-10 entries documented in the contributing guide.

---

## 📐 Recommended patterns

### Standard types — the canonical set

The widely-adopted superset (spec + Angular convention):

```
feat        New feature
fix         Bug fix
perf        Performance improvement
revert      Reverts a previous commit
docs        Documentation only
style       Whitespace, formatting, no code change
refactor    Code change that neither fixes a bug nor adds a feature
test        Adding or correcting tests
build       Build system or external dependency changes
ci          CI configuration change
chore       Anything else that doesn't fit
```

Some teams add:
- `deps` — dependency upgrades (often grouped separately in changelogs)
- `security` — security-only fixes (so they're easy to surface)

**Recommendation:** start with the canonical set; add custom types only when a clear, recurring need exists, and document them in the `commitlint` config.

### Multi-line body conventions

```
<type>(<scope>): <description>     ← max 72 chars, imperative, lowercase, no period
                                   ← blank line
<body>                             ← wrapped at 80 chars, explains *why*
                                   ← blank line
<footer>                           ← machine-parseable trailers
```

Footers follow the [git trailer](https://git-scm.com/docs/git-interpret-trailers) convention:

```
BREAKING CHANGE: <description>     # forces MAJOR
Refs: #142, #156                   # links to issues
Co-authored-by: Name <email>       # multiple authors
Reviewed-by: Name <email>          # code review trail
Release-As: 2.0.0                  # explicit version override (release-please)
```

### Imperative mood, lowercase, no period

```
✅ feat: add elevation endpoint
✅ fix: prevent NaN in altitude calculation

❌ feat: Added elevation endpoint   (past tense, capitalised)
❌ feat: adds elevation endpoint.   (third person, trailing period)
❌ feat: ELEVATION                  (shouting, vague)
```

### Linking to issues

```
Refs: #142          # general reference, doesn't auto-close
Closes: #142        # closes issue on merge to default branch (GitHub)
Fixes: #142         # synonym
```

### Reverts

```
revert: feat(routing): add /elevation endpoint

This reverts commit a1b2c3d4e5f6.
The elevation calculation produces incorrect results for routes
crossing the antimeridian; reverting until #198 is resolved.
```

A revert of a `feat:` triggers a MAJOR bump (it's a breaking change for anyone who started using the feature). Tools track this via the body's `This reverts commit <SHA>` line.

### `Release-As:` footer — overriding the auto-derived bump

Sometimes you need a specific version (rebrand, marketing-driven number, jumping to 1.0):

```
chore: bump to 1.0 for public launch

Release-As: 1.0.0
```

release-please picks this up and uses it as the next version regardless of the commit history.

---

## 🚫 Anti-patterns

```
❌ feat: stuff                            (no information)
❌ Update README                          (no type prefix → ignored)
❌ feat: Refactored the user model        (uppercase, past tense, type wrong)
❌ feat: WIP                              (work in progress should not land)
❌ chore: bump version to 1.5.0           (manual version bump bypasses tooling)
❌ feat: add A; fix: also B               (one type per commit)
❌ feat!: rename /routes (no BREAKING block)
   → the ! triggers MAJOR but a BREAKING CHANGE: footer is still recommended
     for context that flows into the changelog
❌ Long single-line message with the rationale crammed in:
   "feat: add elevation, also we considered X, Y, Z, but..."
   → Use the body for the rationale.
```

---

## 🔧 Enforcement tooling

### `commitlint`

The reference enforcer.

```bash
npm install --save-dev @commitlint/cli @commitlint/config-conventional
```

`commitlint.config.js` :

```javascript
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'perf', 'revert', 'docs', 'style', 'refactor', 'test', 'build', 'ci', 'chore', 'deps', 'security']
    ],
    'subject-case': [2, 'never', ['upper-case', 'pascal-case', 'start-case']],
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'],
    'header-max-length': [2, 'always', 72]
  }
};
```

### `commitlint` on PR titles (GitHub Actions)

```yaml
name: lint-pr-title

on:
  pull_request:
    types: [opened, edited, synchronize, reopened]

permissions:
  pull-requests: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: amannn/action-semantic-pull-request@v5
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          types: |
            feat
            fix
            perf
            revert
            docs
            style
            refactor
            test
            build
            ci
            chore
            deps
            security
          requireScope: false
          subjectPattern: ^(?![A-Z]).+$
          subjectPatternError: |
            The PR title subject must start with a lowercase letter.
```

### `commitlint` on commits (Husky pre-commit)

```bash
npm install --save-dev husky
npx husky init
echo 'npx --no -- commitlint --edit "$1"' > .husky/commit-msg
```

This catches non-conforming commits at commit time, **before** they reach a PR.

### Minimal alternative — regex check in CI

If you don't want a Node toolchain (e.g. PHP-only repo), a shell check works:

```yaml
- name: Validate PR title
  run: |
    title="${{ github.event.pull_request.title }}"
    if ! [[ "$title" =~ ^(feat|fix|perf|revert|docs|style|refactor|test|build|ci|chore|deps|security)(\(.+\))?!?:\ .+ ]]; then
      echo "❌ PR title doesn't match Conventional Commits format."
      exit 1
    fi
```

---

## 🔗 Companion capabilities

- **`release/semver.md`** — the bump rules that types map to.
- **`release/changelog.md`** — how types translate into changelog sections.
- **`release/release-please.md`** — the tool that consumes Conventional Commits to produce releases.

---

## ✅ Quick checklist

```
- [ ] Type vocabulary documented in CONTRIBUTING.md
- [ ] Scope vocabulary (if used) documented and limited (~5-10 entries)
- [ ] commitlint installed (or shell-regex fallback for non-Node repos)
- [ ] PR title validation enforced in CI
- [ ] Squash-merge default title = PR title (GitHub repo settings)
- [ ] BREAKING markers (! and BREAKING CHANGE: footer) usage documented
- [ ] Imperative-mood / lowercase / no-period rule documented
- [ ] Husky pre-commit hook for local commit-message validation (optional)
- [ ] Team trained on the format (PR template includes a reminder)
- [ ] No mixed types in a single commit (one type per commit)
- [ ] Body explains *why*, not *what*
```
