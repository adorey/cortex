# ADR-009 — The release cycle: every merge into `main` is a release, drafted by CI, published from GitHub

- **Status:** Proposed
- **Date:** 2026-10-30 (proposed)
- **Authors:** Cortex maintainers (initiated by the maintainer, drafted by @Oolon)
- **Affects:** `.github/workflows/` (`binary.yml` and the release jobs, the triggers of the test workflows), new composite actions under `.github/actions/`, `cli/build.py` (the spec archives a binary knows), a new `bin/setup-release.sh`, the repository's settings (the ruleset of `main`, immutable releases), `CONTRIBUTING.md` (the commit convention, versioning & releases), `docs/process/adr-implementation.md` (§2, §8, §9)
- **Relates to:** [ADR-008](ADR-008-cortex-binary.md) — §3.1 (how a release is made), §3.3 (the spec archives a binary knows) and the amendments of its §9 on pre-releases, which this ADR replaces; ADR-008 records it in its own amendments when this ADR is implemented

---

## 1. Context

A release of Cortex is made today by a tag (ADR-008 §3.1, CONTRIBUTING's steps 6 and 7). The maintainer pushes `X.Y.Z` on `main`. The `binary` workflow builds the four targets, creates the release as a draft from `changelog/X.Y.Z.md`, attaches the assets and publishes it. Nothing is published by hand.

On 2026-10-29 that broke three times in one evening. The maintainer publishes releases from the Releases page, whose button creates the tag and a **published** release in one step, with no assets. For 1.1.2, 1.2.0 and 1.2.1 in turn:

- `releases/latest/download/SHA256SUMS` answered `404`: the one-line install was broken for everyone;
- every build of the binary failed, the tag's own included. `cli/build.py --fetch-known-specs` refuses a published release without `SHA256SUMS`, and has to: a binary built without that checksum would check the version against its `SHA256SUMS` alone;
- the publish job refused to upload to a release that was already published.

Each one was recovered by hand: the release deleted, its tag kept, the tag's run started again. For 1.2.1 the tag's push had started no run at all, and the tag was pushed a second time.

The workflow is right about what it protects — a release is never `latest` without its assets — and wrong about who releases. The maintainer publishes on GitHub, and the pipeline has to fit that, not the reverse.

GitHub has offered **immutable releases** since 2025-10-28. Once a release is published, its assets cannot be added, changed or deleted, and its tag is locked to its commit; a draft stays editable. That is the order the workflow already follows, enforced by GitHub instead of by a script.

Four more things shape the decision:

- **`main` is meant to receive releases only, and nothing enforced it.** CONTRIBUTING's stack model merges everything into an integration branch, then that branch into `main`, once. But the ruleset of `main` let an administrator bypass it, and every merge method was allowed.
  - On 2026-10-30, after the rewrite below, the maintainer applied by hand most of what §3.10 makes a script own: no bypass, merge commits only, the head branch up to date before it merges, head branches deleted on merge, and immutable releases.
  - A push to `main` without a release is still a `0.0.0-dev.N` build.
  - The tests are still not required: their workflows have a `paths` filter, so a pull request that touches none of those paths never reports them (§3.10).
- **Pre-releases are throwaway** (ADR-008 §9). `X.Y.Z-something` tests the release workflow, and is then deleted or built again under its tag. The maintainer wants real ones — alpha, beta and release candidates, which a tester installs and a project pins.
- **The commit convention is not checked.** Eight commits written after the rule (2026-06-03) broke it: one with a `Co-Authored-By` trailer, one more with a body, six with no `type(scope):`. On 2026-10-30 their messages were rewritten on `main`:
  - every tree is unchanged, and the release tags 0.6.0 to 1.2.1 moved to the rewritten commits;
  - the previous history is kept on GitHub at `refs/archive/pre-rewrite-2026-10-30`, since the attestations and the spec archives of 1.0.0 to 1.2.1 name its commits;
  - it is the last rewrite this repository can have: once its releases are immutable, their tags no longer move.
- **The maintainer's other projects need the same cycle** — a few repositories first, the rest once the cycle is proven. Written into Cortex's workflow files only, it would be copied, and the copies would drift.

## 2. Decision

**Every merge into `main` is a release, and nothing else reaches `main`. The version is the release note the pull request adds, checked before it may merge. CI builds the merge and leaves it as a draft release with every asset on it. The maintainer publishes it from the Releases page, and GitHub creates the tag then. A published release is immutable. Pre-releases — alpha, beta, release candidates — are versions too, cut by hand from the integration branch through the same draft. The cycle is written once, as composite actions in this repository, which Cortex calls first and other projects pin by a release.**

For the maintainer, a release becomes: merge the release pull request, wait for the draft, press *Publish release*. Nobody pushes a version tag.

This ADR does not change:

- `CHANGELOG.md` as the single source of versions;
- the release names and epigraphs;
- the assets and their names;
- the install scripts, the store and `cortex sync`.

The one exception is that a binary also knows the spec archives of immutable pre-releases (§3.7).

## 3. Detailed contract

### 3.1 The cycle, end to end

1. The work lands on an integration branch — `release/X.Y.Z`, or `release/adr-NNN-slug` for an ADR — through stacked pull requests, each checked by the tests and by the commit messages check (§3.8).
2. Optionally, pre-releases are cut from that branch: *Run workflow*, then the draft, then *Publish release* (§3.7).
3. The release artefacts come last: `changelog/X.Y.Z.md` and the `CHANGELOG.md` section, as today.
4. The pull request into `main` runs the release gate, which names `X.Y.Z` (§3.2), and the builds. It is merged with a merge commit.
5. About a quarter of an hour later, the draft `X.Y.Z` is on the Releases page, with its assets (§3.3).
6. The maintainer presses *Publish release*. GitHub creates the tag, the release is immutable, and the guard checks it (§3.4, §3.5).

### 3.2 The release gate — what may merge into `main`

The release gate is a check on every pull request into `main`, required by the ruleset (§3.10). It reads the pull request's diff against its base and the repository's releases, and it passes only when:

1. the pull request adds **exactly one** release note, `changelog/X.Y.Z.md`, where `X.Y.Z` is a version with no suffix;
2. the first section of `CHANGELOG.md` after `## [Unreleased]` is `## [X.Y.Z] - YYYY-MM-DD — <name> _(Released)_`, with the same `X.Y.Z`, the base's `CHANGELOG.md` has no section for `X.Y.Z`, and `YYYY-MM-DD` is the day the gate runs, in UTC;
3. `X.Y.Z` is higher than every release, that is every version tag without a suffix, and no tag or release — draft included — is named `X.Y.Z`. Pre-releases do not count: those of `X.Y.Z` precede it, and those of a later version — a `2.0.0-alpha.1` cut from a long-lived branch — must not block a 1.x release;
4. no draft release is waiting: one release is in flight at a time.

The gate names the version in its summary. It infers nothing from the state of the repository after the merge: the version is what the pull request adds, checked before the pull request can merge. The name of the branch does not matter.

Precedence follows semver.org §11, as `cli/cortex_cli/semver.py` does, never `sort -V`, which puts `1.3.0` before `1.3.0-beta.1`.

**A release is dated by the day it merges, in UTC.** UTC is the time zone of GitHub's own dates and of a workflow's schedule, and it assumes nothing about where a project's maintainers are. The date cannot be the day of publication: `CHANGELOG.md` is in the spec archive, which is the merge commit's, and a draft can wait. Three dates used to drift apart — the one written, the merge's and the publication's: 1.2.1 says 2026-10-30, and was merged and published on 2026-10-29. A gate that passed the day before would let a stale date merge, so the gate runs again on the day of the merge:

- **where the repository has a merge queue**, every required check, the gate included, also runs on the merge group, at the moment of merging, and that run decides. The queue takes one pull request at a time, so that a push to `main` still carries one release (§3.3);
- **where it has none** — GitHub offers merge queues to repositories owned by an organisation — a scheduled job re-runs, just after midnight UTC every night, the gate of every open pull request into `main`. A date gone stale turns red, and the pull request cannot merge until its date is corrected.

The release job also compares the date with its merge commit's (§3.3), and reports a difference as a warning in its summary. It does not fail for it: failing there would spend the version over a date.

### 3.3 The draft — what a merge into `main` produces

A push to `main` runs the release job, with no `paths` filter: every push is a release.

- **The version** comes from the push the same way: the release note added between the push's `before` and `after`. If there is not exactly one, the job fails and creates nothing. Such a push has bypassed the gate, which the ruleset (§3.10) makes impossible, and the failure is the alarm.
- **The date** of the release is compared with the merge commit's, in UTC. A difference is a warning in the job's summary, not a failure (§3.2).
- **The build** is the `binary` workflow's, at `X.Y.Z`:
  - the four targets, the CLI's suite replayed through each binary, and the glibc floor;
  - the spec archive, from `git archive` of the merge commit;
  - `SHA256SUMS`, and an attestation for each asset and for each binary.
- **The draft** is titled `X.Y.Z`, with `changelog/X.Y.Z.md` as its body and the six assets. Its `target_commitish` is the merge commit's SHA, not `main`, which may move. It creates no tag: a draft has none until it is published.
- **The draft is created last**, once the six assets are built and checked, so that a failure while building leaves nothing behind. Uploading them can still fail half-way, which the next rule recovers.
- **A draft is never rebuilt from another commit.** If a release named `X.Y.Z` exists, the job looks at it:
  - a published release, or a draft whose `target_commitish` is another commit: the job stops and changes nothing. A new commit is a new version, through a new pull request;
  - a draft whose `target_commitish` is this push's merge commit is the job's own, left by a run that failed: the job deletes it and makes it again. A re-run after a lost runner or a cut upload ends with a complete draft, and costs no version number, since a draft has no tag and immutability applies from publication.
- **A draft is either published or discarded.**
  - A discarded draft's number is spent: its section is in `main`'s `CHANGELOG.md`, so the gate refuses it again (§3.2, 2).
  - The fix is the next patch, whose release pull request marks the spent version's section `_(Not published)_`.

The draft appears a quarter of an hour or so after the merge, and the Windows build is most of that time.

### 3.4 Publishing — the maintainer, from the Releases page

The maintainer opens the draft, reads the note and presses *Publish release*. GitHub creates the tag `X.Y.Z` on the draft's target commit, and the release becomes immutable (§3.6).

- **Nobody pushes a version tag.** The `binary` workflow no longer runs on tags, so a tag pushed by hand starts nothing, and the gate refuses the version it names (§3.2, 3).
- **No release is created from scratch on the Releases page.** *Draft a new release* makes a release with no assets. Once published, the guard reports it (§3.5), and since it is immutable, its version is spent.
- **The *Set as the latest release* box does not matter.** The guard sets `latest` right, whatever was ticked.

### 3.5 The guard — what a publication is checked against

On `release: published`, for releases and pre-releases alike, a job checks the following and reports it in its summary:

1. the tag is a version: `X.Y.Z` or `X.Y.Z-(alpha|beta|rc).N`;
2. the build provenance of every asset names the tag's commit;
3. the six assets are there, and `SHA256SUMS` matches them;
4. the release is immutable;
5. `latest` is the highest version without a suffix. The guard moves it back when an older line or a pre-release took it.

The guard repairs item 5 only, because immutability locks everything else. On any other failure it fails, and opens an issue labelled `type:infra` naming what it found and the only fix: the release cannot be repaired, only deleted, and its version is spent. The next patch ships what it should have.

### 3.6 Immutable releases

The switch (phase 4) turns them on for the repository. From then on, a published release:

- **cannot change its assets**: none can be added, changed or deleted;
- **keeps its tag**: the tag cannot be moved or deleted while the release exists, and a deleted release's tag name is never used again;
- **stays editable** in its title and notes, and in its pre-release and latest flags;
- **gets a release attestation** from GitHub, naming its tag, its commit and its assets.

Consequences:

- **GitHub enforces what the publish job's script enforced** — a published release is never uploaded to again — and it does so for tags as well.
- **The recovery of 2026-10-29 no longer exists.** Deleting the release, keeping the tag and building again cannot happen. A mistake costs a version number.
- **Releases published before the switch stay mutable** — 1.2.1 and older: GitHub applies the setting to releases published after it.
- **A project can pin the composite actions (§3.9) by a release tag of Cortex.** An immutable tag is as fixed as a commit SHA.

### 3.7 Pre-releases

**They are versions**, with lower precedence than the release they prepare: `1.3.0-alpha.1` < `1.3.0-beta.1` < `1.3.0-rc.1` < `1.3.0-rc.2` < `1.3.0`. They are written in lowercase, with the number after a dot. SemVer compares an identifier that mixes letters and digits as text, so `RC10` would come before `RC2`, whereas `rc.10` comes after `rc.2`.

**They are cut from the integration branch, never from `main`.** Symfony tags `v7.3.0-BETA1`, `v7.3.0-RC1` and `v7.3.0` on its `7.3` branch, while its default branch carries the next version. Here, the branch is `release/X.Y.Z` or `release/adr-NNN-slug`, and the release itself is the merge into `main`. The stages:

| Stage | The branch |
|---|---|
| `alpha` | content still landing |
| `beta` | feature freeze: fixes only |
| `rc` | complete, its release note included |

Each stage is optional: a patch goes straight to the release.

**They are cut by hand**, with *Run workflow* on the branch and the version as its input. The job refuses unless:

- the branch is a `release/**` branch;
- the version is `X.Y.Z-(alpha|beta|rc).N`, `X.Y.Z` is higher than every release, and the version is higher than every pre-release of `X.Y.Z` (no beta after an rc);
- no tag or release is named after it, and no draft is waiting.

It then makes the same build and the same draft as a release (§3.3), marked as a pre-release and not latest, with the branch's commit as its target. A re-run of that run recovers its own draft by the same rule. The maintainer publishes it, and the guard checks it.

**The note** opens with a banner saying it is a pre-release of `X.Y.Z`, not for production. The rest is `changelog/X.Y.Z.md` when the branch has it, and otherwise the `[Unreleased]` section of the branch's `CHANGELOG.md`. A pre-release has no section of its own in `CHANGELOG.md`: the release's section covers it.

**They are installed and pinned on purpose.** A pre-release is never `latest`, so `releases/latest` and the default install never take it.

- `install.sh 1.3.0-beta.1` installs it, and so does `install.ps1 -Version 1.3.0-beta.1`.
- A project pins it with `version = "1.3.0-beta.1"`. A binary older than the pre-release refuses that project with the upgrade command, as for any newer version (ADR-008 §3.3).
- The binary of `1.3.0` serves a project pinned to `1.3.0-rc.1`, which precedes it.

**A binary knows their spec archives.** ADR-008 left pre-releases out of the checksums a binary embeds, because a pre-release could be built again under its tag ([#151](https://github.com/adorey/cortex/issues/151)). An immutable one cannot. `--fetch-known-specs` therefore takes the published, immutable pre-releases from 1.0.0 on, and still leaves out mutable ones.

**A release candidate tests the release pipeline.** A release that changes the pipeline must publish at least one `rc` before its pull request into `main` opens. The pipeline here means `binary.yml`, the release jobs, the composite actions, `cli/build.py` and the install scripts. *Run workflow* runs the workflow files of the branch it starts on, so the candidate goes through the new pipeline. The throwaway pre-release of ADR-008 §9 is gone: it would stay forever now, and a candidate that stays proves more.

**The integration branch merges into `main` with a merge commit** (§3.10). Squashed or rebased, the commits the pre-releases are tagged on would fall out of `main`'s history.

### 3.8 The commit messages check

This check runs on every pull request and is required on `main` (§3.10). It applies to every commit of the pull request, from the base to the head, merge commits excluded, because GitHub writes those. Each commit must:

- **have a subject that matches the repository's pattern.** For Cortex that is CONTRIBUTING's `<gitmoji> <type>(<scope>): <subject>`: the gitmoji a single emoji, the type one of the mapping table's, and an optional `#<issue>` before the subject for ADR work;
- **have no body**, except a `BREAKING CHANGE:` footer, which CONTRIBUTING allows when it is strictly required;
- **carry no trailer**: no `Co-Authored-By`, no `Signed-off-by`, nothing else.

It lists every commit that fails, and why.

**Pull requests are checked, not history.** A commit already on the base is never checked again. The pull request into `main` carries every commit of its integration branch, so nothing reaches `main` unchecked, even a commit merged into the integration branch past a red check.

### 3.9 One cycle, several projects — composite actions

The logic of §3.2 to §3.8 lives in composite actions under `.github/actions/`. Each one has its script beside it, standard library Python only, like `cortex_core`, and its tests:

| Action | Does |
|---|---|
| `release-gate` | §3.2 — the version a pull request adds, or why it may not merge |
| `release-version` | §3.3, §3.7 — the version a push to `main` adds, or the pre-release a run was given, or a failure |
| `release-draft` | §3.3, §3.7 — the draft, from the assets the calling job built: note, target, latest flag, attestations |
| `release-guard` | §3.5 |
| `commit-messages` | §3.8, with the pattern as an input |

**Inputs fit the actions to another project**: where its changelog and its notes are, its commit pattern, and the assets a release must carry. What a project builds stays its own: Cortex builds its binaries, another project a container image or a chart.

**Cortex calls them first**, from its own workflows and by path (`./.github/actions/…`), so the release that ships them is released through them. **Another project pins them by a release of Cortex**, for example `uses: adorey/cortex/.github/actions/release-gate@<version>`, which immutability makes as fixed as a commit (§3.6).

### 3.10 The repository's settings — `bin/setup-release.sh`

A repository's settings are not in the repository, so a script applies them. Like `bin/setup-labels.sh`, it is idempotent, and `--check` reports drift without changing anything. An administrator runs it, with their own token: CI has no administrator rights, and should not. It takes the repository as its argument, so the same script sets up the maintainer's other repositories.

- **The ruleset of the default branch:**
  - changes through a pull request only;
  - no force push and no deletion;
  - merge commits only;
  - required checks: the release gate, the commit messages, and the summary job of every workflow that gates a pull request into `main` — the repository checks, the builds and the tests;
  - the head branch up to date with `main` before it merges, so that the commit checked is the commit released;
  - **no bypass, for anyone, administrators included**.
- **Immutable releases**: on.
- **Head branches deleted on merge**, which is what makes a stack collapse ([docs/process/adr-implementation.md](../process/adr-implementation.md) §2).
- **The merge queue of `main`**, where the repository has one: one pull request per group, merged with a merge commit (§3.2). Where it has none, the nightly re-run of the gate is a workflow of the repository, not a setting.

**A required check must report on every pull request into `main`.** GitHub waits for a required check by its name, and three things keep a name from ever being reported:

- a workflow that a `paths` filter does not start: its checks stay pending, and the pull request cannot merge;
- a matrix job skipped before its matrix expands, because a job it needs failed: it reports under its unexpanded name, as `glibc 2.28 (${{ matrix.target }})` did when a build failed;
- a matrix that changes, which renames its jobs.

So every workflow that gates `main`:

- runs on every pull request, with no `paths` filter;
- starts with a job that reads the changed files, and skips the jobs that no changed file concerns, which GitHub counts as passing;
- ends with one summary job. It runs whatever happened before it (`if: always()`), fails when a job it needs failed or was cancelled, and passes when they all passed or were skipped.

The ruleset requires the summary jobs, by names that no matrix changes.

## 4. Phases

Execution order: **1 → 2 → 3 → 4**. All four gate the release that ships this ADR: that release is the first one made by the cycle.

### Phase 1 — The checks on pull requests

The `commit-messages` and `release-gate` actions, wired into Cortex's workflows; the summary jobs, and the test workflows' triggers without `paths` filters (§3.10); and `bin/setup-release.sh`.

Acceptance criteria:

- a pull request that touches only `README.md` reports every required check: the tests are skipped, their summaries pass, and it can merge
- a pull request that breaks a test of the CLI fails the summary of the CLI tests and cannot merge, and so does one whose build fails
- no required check of the ruleset is the name of a matrix job
- a pull request with a commit that has a body, a trailer, or a subject off the pattern fails the commit messages check, which names the commit and the reason; a `BREAKING CHANGE:` footer alone passes; GitHub's merge commits are not checked
- the release gate fails a pull request into `main` in each of these cases:
  - it adds no release note, or two;
  - it adds a version that is not higher than every release by SemVer precedence, while a published `2.0.0-alpha.1` does not block a `1.4.0`;
  - it adds a version that already has a section in the base's `CHANGELOG.md`;
  - the first section of its `CHANGELOG.md` is another version;
  - its release is dated another day than the day the gate runs, in UTC;
  - a draft is waiting
- a pull request whose gate passed the day before turns red after the nightly re-run, and cannot merge until its date is corrected; where the repository has a merge queue, the gate's run on the merge group refuses a date of another day
- the release gate passes a fixture's release pull request and names its version
- the actions' SemVer ordering agrees with `cli/cortex_cli/semver.py` on one shared table of cases, which includes the `sort -V` counter-example
- on a throwaway repository, `bin/setup-release.sh --check` reports every setting of §3.10 that differs and exits non-zero; after one run without `--check`, it reports none, and a second run changes nothing

### Phase 2 — The draft

The `release-version` and `release-draft` actions. The release job runs on a push to `main` and by *Run workflow* for pre-releases. The tag trigger is removed, and `--fetch-known-specs` takes the immutable pre-releases.

Acceptance criteria:

- a push to `main` that adds `changelog/X.Y.Z.md` leaves a draft `X.Y.Z` with the six assets, the note as its body and the pushed commit as its target, and creates no tag
- a push that adds no note or two, or whose version already has a published release or a draft of another commit, fails, and creates and changes nothing
- a re-run after a run that failed while uploading leaves one complete draft, with the six assets
- a re-run once the release is published changes nothing
- a version tag pushed by hand starts no release job
- *Run workflow* on a `release/**` branch with `X.Y.Z-rc.1` leaves a draft pre-release, not latest, whose note opens with the banner
- *Run workflow* fails and creates nothing in each of these cases: run on `main`; given `X.Y.Z-rc1`; given a beta after an rc; given a taken number
- `--fetch-known-specs` includes an immutable pre-release from 1.0.0 on and excludes a mutable one

### Phase 3 — The guard

The `release-guard` action, on `release: published`.

Acceptance criteria:

- publishing a draft made by phase 2 runs the guard, which passes
- the guard fails and opens one issue naming what it found, on a fixture release with any of these: a missing asset, a `SHA256SUMS` that does not match, a tag on another commit than the provenance names, or a mutable release
- with `latest` on a lower version or on a pre-release, the guard moves `latest` to the highest version and says so

### Phase 4 — The switch

The phase points the documentation at the cycle:

- `CONTRIBUTING.md`: the commit convention now names its check, and *Versioning & releases* replaces steps 6 and 7 with §3.1;
- `docs/process/adr-implementation.md`:
  - §2 — `main` takes merge commits only, the last pull request of a stack included;
  - §8 and §9 — the release is the merge, then the draft;
- ADR-008: an amendment pointing here.

It then runs `bin/setup-release.sh` on this repository and publishes the release candidate, then the release.

Acceptance criteria:

- `bin/setup-release.sh --check adorey/cortex` reports no drift
- a direct push to `main` is refused, with an administrator's token too
- a release candidate of the release that ships this ADR is published from the integration branch through phases 2 and 3, installed by `install.sh <version>` on a clean machine, and pinned and synced by a throwaway project
- the release that ships this ADR is made by the cycle: its draft is built from the merge, published from the Releases page, and its guard is green; `releases/latest/download/SHA256SUMS` answers `200` throughout
- `CONTRIBUTING.md` tells nobody to push a tag
- ADR-008 carries the amendment pointing at this ADR

## 5. Consequences

### Positive

- **The maintainer releases from the Releases page**, as before the incidents: merge, wait for the draft, publish.
- **`releases/latest` never names a release without its assets.** A release made by mistake without them is reported by the guard the moment it is published.
- **A published release cannot change**, by anyone: GitHub enforces on assets and tags what the workflow's script used to.
- **`main` is the list of releases**: every merge commit on it is one, checked before it merged.
- **No tag to push and no `paths` filter to satisfy**: the run that never started for 1.2.1 cannot happen again.
- **Real pre-releases**, which a tester installs and a project pins, with the guarantees of a release.
- **The commit convention holds** without a reviewer having to catch it.
- **One cycle for several projects**, pinned by an immutable release.

### Negative

- **A mistake after publication costs a version number.** The release can be deleted, but its tag name is never reused.
- **Nobody can push to `main` or bypass a check, administrators included.** An urgent fix is a patch release through a pull request, its checks included.
- **A waiting draft blocks the next merge into `main`**: publish it or discard it first.
- **The draft comes a quarter of an hour after the merge**, and the Windows build is most of that time.
- **Every workflow starts on every pull request**, a documentation one included. A first job reads the changed files and skips the rest, at the cost of a few seconds of runner.
- **Pre-releases stay forever** in the Releases list. This is why the candidates are `rc` and never `test`.
- **The cycle relies on GitHub** — immutable releases, rulesets, `release: published` — in every project that adopts it.
- **A history rewrite, which this repository had on 2026-10-30, becomes impossible.** That is the point, and also the cost.

### Neutral

- `CHANGELOG.md` stays the single source of versions. A release's note, name and epigraph are written as before, by its release pull request.
- The assets, their names, the install scripts, the store and `cortex sync` are unchanged. Releases up to 1.2.1 stay mutable.
- Branches and pull requests still build `0.0.0-dev.N`.

## 6. Alternatives considered

| Alternative | Why not |
|---|---|
| **Attach the assets after publication**, on `release: published` | `latest` would name a release without assets for the length of the build, and for good when a target fails: what ADR-008 removed. With immutable releases, it is not possible at all. |
| **A *Run workflow* button that tags, builds and publishes** | The release is made from the Actions tab, not from the Releases page; the version is typed by hand; and nobody reads the note before it is public. |
| **Keep the tag push** | The incidents of 2026-10-29: a tag that starts no run, and a release published by hand beside it. |
| **Rebuild the draft on every push to `main`** | `main` gets commits that are not releases, and a draft changes under the maintainer's review. |
| **Infer the version from the repository after the merge** — the release note with no published release | Ambiguous with two waiting notes or a leftover draft, and decided too late to refuse anything. |
| **release-please** — a Release PR, the version derived from the commit types | The version is decided by the commits rather than by the maintainer, and the note is generated, where Cortex writes a narrated note with a name and an epigraph. Its capability card stays, for projects that want it. |
| **Keep throwaway pre-releases** | Impossible once releases are immutable, and a test release that disappears proves less than a candidate that stays. |
| **Symfony's branch model in full** — a branch per minor version, no `main` | Maintenance branches for a project that maintains no older line. The integration branch already plays the role of Symfony's version branch while it stabilises. |
| **Keep the `paths` filters, and require only the workflows that always run** | A release that breaks the tests of the CLI or of the core could merge: its checks are red, and nothing stops it. That is the state from 2026-10-30 until phase 1. |
| **Require each matrix job by its name** | The names change with the matrix, and a matrix job skipped before its matrix expands reports under another name. |
| **Date a release by the day it is published** | The date is in `CHANGELOG.md`, which is in the spec archive of the merge commit: it is written before the merge, and the publication comes after. |
| **Check only the format of the date, and re-run the gate by hand before merging** | One forgotten click lets a stale date merge, and several maintainers forget more. The nightly re-run, or the merge queue, turns the same click into a rule. |
| **A tag ruleset restricting who creates version tags** | Publishing from the Releases page creates the tag as the maintainer, who would need a bypass. That contradicts "no bypass", and the gate already refuses a version whose tag exists. |

## 7. Follow-ups (out of scope for this ADR)

1. **The cycle in the maintainer's other projects**:
   - a few repositories first, the rest once the cycle is proven;
   - each runs `bin/setup-release.sh`, calls the actions pinned by the release that ships this ADR, and builds its own assets;
   - one issue per repository.
2. **Agents that know the cycle.**
   - A capability card under `agents/capabilities/release/` describes the cycle.
   - The `engineering/release-automation` workflow offers it beside release-please, so that a host project's agents can set it up.
3. **Maintenance lines.** A patch to an older line after a newer release (1.2.2 after 1.3.0) cannot go through `main`, which only moves forward. It would need a maintenance branch per line, as Symfony keeps `7.4` beside `8.2`. Not needed yet.

## 8. References

- [ADR-008](ADR-008-cortex-binary.md) — §3.1 (the release from the tag), §3.3 (the spec archives a binary knows) and §9 (the amendments on pre-releases)
- [CONTRIBUTING.md — Commit message convention](../../CONTRIBUTING.md#commit-message-convention) and [Versioning & releases](../../CONTRIBUTING.md#-versioning--releases)
- [docs/process/adr-implementation.md](../process/adr-implementation.md) — §2 (merge commits in a stack), §8 (gates), §9 (closing an ADR)
- [`.github/workflows/binary.yml`](../../.github/workflows/binary.yml) — the build and the publish job this ADR reshapes
- [`cli-tests.yml`](../../.github/workflows/cli-tests.yml), [`core-tests.yml`](../../.github/workflows/core-tests.yml) and [`runtime-tests.yml`](../../.github/workflows/runtime-tests.yml) — the `paths` filters phase 1 replaces
- [`cli/build.py`](../../cli/build.py) — `--fetch-known-specs`
- [`cli/cortex_cli/semver.py`](../../cli/cortex_cli/semver.py) — SemVer precedence, pre-releases included
- [`bin/setup-labels.sh`](../../bin/setup-labels.sh) — the shape `bin/setup-release.sh` follows
- [GitHub — Immutable releases](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases) and [the announcement](https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/)
- [GitHub — Troubleshooting required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks) — a workflow skipped by a `paths` filter leaves its required checks pending; a job skipped by a condition reports success
- [GitHub — Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) — available to public repositories owned by an organisation
- [GitHub — Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) — no workflow runs when a draft release is created
- [Semantic Versioning 2.0.0, §11](https://semver.org/#spec-item-11) — precedence
- [Symfony — The Release Process](https://symfony.com/doc/current/contributing/community/releases.html), and the tags `v7.3.0-BETA1`, `v7.3.0-RC1` and `v7.3.0` on its `7.3` branch
