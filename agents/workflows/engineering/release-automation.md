# Workflow: Release automation setup & maintenance

<!-- GENERIC WORKFLOW — cortex
     Can be overridden by {workspace_root}/agents/workflows/engineering/release-automation.md
     or by {service}/agents/workflows/engineering/release-automation.md
-->

## 🎯 Triggers

This workflow activates when the prompt contains formulations such as:
- "set up release-please", "automate releases", "automate versioning"
- "configure changelog", "set up commitlint", "enforce conventional commits"
- "release strategy", "versioning strategy", "tagging strategy"
- "first release", "publish v1.0.0", "cut a release"
- "migrate changelog", "consolidate release notes"

## 👥 Agents involved

| Step | Role | Responsibility |
|---|---|---|
| 1 | `roles/engineering/architect.md` | Versioning & release strategy decision (ADR) |
| 2 | `roles/engineering/platform-engineer.md` | CI workflows (release-please, commitlint), branch protection, repo settings |
| 3 | `roles/engineering/lead-backend.md` and/or `lead-frontend.md` | Manifest seeding, runtime version exposure (health endpoint, build-time injection) |
| 4 | `roles/engineering/qa-automation.md` | Validation: dry-run on a fixture branch, regression check on existing tags |
| 5 | `roles/communication/tech-writer.md` | CONTRIBUTING.md, CHANGELOG migration, ADR writeup, public docs |
| 6 | `roles/security-compliance/security-engineer.md` | Permissions audit on the release workflow, signed-tag policy |

## 📋 Steps

### Step 1 — Strategy & Decision
**Agent:** `architect`
**Objective:** Decide the versioning + release strategy and capture it as an ADR.

**Checklist:**
- [ ] Identify the deployment coupling (services ship together vs independently)
- [ ] Choose a SemVer strategy: locked, independent, or workspace + per-service tags
- [ ] Choose the release tooling: release-please / semantic-release / changesets / manual
- [ ] Choose the changelog format: Keep a Changelog (single file) and/or release notes (folder/blog)
- [ ] Identify how the version is exposed at runtime (health endpoint, footer, label, etc.)
- [ ] Document the mapping from existing commit/PR conventions to Conventional Commits
- [ ] Capture the decision in an ADR

**Deliverable:** Validated ADR. The team has a single source of truth for "how do we release here?".

**Capabilities to load:** `release/semver.md`, `release/conventional-commits.md`, `release/changelog.md`, `release/release-please.md`.

---

### Step 2 — CI/CD wiring
**Agent:** `platform-engineer`
**Objective:** Make the chosen tooling actually run in CI on every push to the default branch.

The checklist is written for release-please, the tool `release/release-please.md` covers. With another tool chosen in Step 1, map each item to its equivalent.

**Checklist:**
- [ ] Create `release-please-config.json` and `.release-please-manifest.json` per repo
- [ ] Seed the manifest with the current version of each repo (via existing tag or manifest version)
- [ ] Create `.github/workflows/release-please.yml` with minimal permissions
- [ ] Create `.github/workflows/lint-pr-title.yml` for PR-title validation
- [ ] Hook the build/deploy pipeline on `release_created == 'true'` or on tag push
- [ ] Configure repo settings: squash-merge default title = PR title
- [ ] Configure branch protection: only release managers can merge the Release PR
- [ ] Document any required GitHub secrets / tokens (`GITHUB_TOKEN` is enough for release-please)
- [ ] Run a dry-run on a fixture branch to confirm the Release PR opens

**Deliverable:** A repo where merging a `feat:` PR to main causes a Release PR to appear.

**Capabilities to load:** `release/release-please.md`, `release/conventional-commits.md`, `infrastructure/` (project's CI stack).

---

### Step 3 — Manifest & runtime version exposure
**Agent:** `lead-backend` (and/or `lead-frontend` if a frontend repo)
**Objective:** Ensure the version is readable at runtime by humans and monitoring.

**Checklist:**
- [ ] Add `version` field to the relevant manifest if missing (`package.json`, `composer.json`, `pyproject.toml`, etc.)
- [ ] If `release-type: simple` → create the `version.txt` (or equivalent) file
- [ ] Inject the version at build time into the runtime artefact (binary, image, page footer)
- [ ] Expose the version on a `/health` or `/version` endpoint (for backend services)
- [ ] Add a `LABEL version=...` directive in the Dockerfile (release-please can sync it)
- [ ] Verify the version is correctly reported in production after the next release

**Deliverable:** `curl https://api.example.com/health` returns the actual deployed version.

**Capabilities to load:** project's language + framework cards.

---

### Step 4 — Validation & dry-run
**Agent:** `qa-automation`
**Objective:** Confirm the automation behaves as expected on edge cases.

**Checklist:**
- [ ] Open a PR with `feat: …` and verify the Release PR opens with a MINOR bump
- [ ] Open a PR with `fix: …` and verify the Release PR updates with the new entry, no version change
- [ ] Open a PR with `feat!: …` and verify the bump becomes MAJOR
- [ ] Open a PR with `docs: …` and verify it does not trigger a bump
- [ ] Open a PR with a non-conforming title and verify CI rejects it
- [ ] Squash-merge the Release PR on a fixture and verify the tag + GitHub Release are created
- [ ] If `extra-files` are configured, verify they are updated correctly
- [ ] Verify downstream build/deploy is triggered exactly once per release

**Deliverable:** Test report confirming the pipeline behaves correctly across the standard cases.

---

### Step 5 — Documentation
**Agent:** `tech-writer`
**Objective:** Make the new system understandable for current and future contributors.

**Checklist:**
- [ ] Update `CONTRIBUTING.md` with the Conventional Commits expectations and PR-title rules
- [ ] Update the PR template with a checklist (changelog entry, breaking marker, scope)
- [ ] Migrate any pre-existing changelog content into `CHANGELOG.md` (Keep a Changelog format)
- [ ] If the team kept rich narrative release notes, document the split between `CHANGELOG.md` (machine-friendly) and `release-notes/` (human-friendly)
- [ ] Write a "How releases work here" page in the public docs site
- [ ] Cross-link the ADR from Step 1
- [ ] Document the rollback procedure if a Release PR is merged by mistake

**Deliverable:** A new contributor can read the docs and understand how to ship a release without asking.

**Capabilities to load:** `release/changelog.md`, `release/conventional-commits.md`.

---

### Step 6 — Permissions & security audit
**Agent:** `security-engineer`
**Objective:** Confirm the automation does not over-grant.

**Checklist:**
- [ ] Verify the `release-please.yml` workflow uses minimal permissions (`contents: write`, `pull-requests: write`)
- [ ] Verify the workflow does not depend on personal access tokens (only `GITHUB_TOKEN`)
- [ ] If tags must be signed, verify the bot is configured with a GPG key or sigstore equivalent
- [ ] Verify branch protection prevents bypass (e.g. force-push, manual tag) on the default branch
- [ ] Document the rotation policy for any token used by the deploy pipeline

**Deliverable:** Sign-off that the automation cannot be used as a privilege-escalation path.

---

## ✅ Definition of done

- [ ] ADR merged in the project's documentation
- [ ] release-please workflow active in every targeted repo
- [ ] Conventional Commits enforced in CI
- [ ] CHANGELOG.md present and consistent with the chosen format
- [ ] Runtime version exposure verified
- [ ] Dry-run validated end-to-end
- [ ] Public documentation updated (CONTRIBUTING.md + project docs site)
- [ ] Security audit signed off
- [ ] First automated release shipped successfully

## 🔗 Related workflows

- `feature-development.md` — feeds the system: every feature PR follows Conventional Commits.
- `code-review.md` — checks the PR-title format as part of the review.
- `tech-watch.md` — if a new dependency or runtime is introduced, the bump rules may need revisiting.
