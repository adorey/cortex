# Delivering an ADR — branches, issues and gates

This is how Cortex turns an **accepted ADR that carries numbered phases** into merged work.
It exists because the roadmap ahead is a chain of decision records, several of which are too
large for one pull request: a single feature branch for that much work is unreviewable, and
a pile of unrelated pull requests loses the thread of the decision.

A small ADR, or one that lands in a single change, does not need any of this: use a normal
`feat/*` branch and a single pull request, as [CONTRIBUTING.md](../../CONTRIBUTING.md#-branch--pr-workflow)
describes.

> The role-by-role pipeline — who does what, and the checklist each step must satisfy — is
> the generic workflow [agents/workflows/engineering/adr-implementation.md](../../agents/workflows/engineering/adr-implementation.md).
> This document owns the **mechanics**: branches, issues, labels, commits, gates. The two are
> complementary and neither repeats the other.

The model was proven on an earlier project over two multi-phase ADRs and more than a hundred
issues. The traps called out below are the ones that cost real time there.

---

## 1. Branch model

| Branch | Cut from | Lifetime | Pull request |
|---|---|---|---|
| `main` | — | permanent | target of the **final** pull request only |
| `release/adr-NNN-slug` | `main` | one ADR | pushed immediately, **no pull request until every phase has landed** |
| `docs/adr-NNN-slug` | the ADR release branch | one ADR | the ADR text itself — the **first** pull request of the stack |
| `adr-NNN/phase-N-slug` | the previous branch of the stack | one phase | targets its parent branch |
| `release/X.Y.Z` | the branch it ships | one release | changelog and release note — stacked **last** |

Two branch shapes start with `release/` and they are not the same thing:

- `release/adr-NNN-slug` carries **content** — the integration branch of one decision record,
  alive as long as the ADR takes.
- `release/X.Y.Z` carries **no content** — `changelog/X.Y.Z.md` and the `CHANGELOG.md` section.
  It is stacked last so the note describes what is actually there, and because every pull request
  that touches `CHANGELOG.md` edits the same anchor under `## [Unreleased]`: stacked last, it
  merges clean.

The ADR text goes first because the phases quote it. A reviewer reads the decision before the
code that implements it, in the same stack.

## 2. Stacking the phases

Each phase branches off the **tip of the previous branch in the stack**, never off the release
branch once a phase exists — otherwise phase 3 cannot see what phase 1 introduced.

```text
main
 └── release/adr-007-cortex-core                  (pushed, no pull request yet)
      └── docs/adr-007-cortex-core                PR -> release/adr-007-cortex-core
           └── adr-007/phase-1-core-library       PR -> docs/adr-007-cortex-core
                └── adr-007/phase-2-resolver      PR -> adr-007/phase-1-core-library
                     └── ...
```

GitHub retargets a child pull request automatically when its parent merges, so the stack
collapses one level at a time without manual edits.

**Rules that keep a stack survivable:**

- **Merge a pull request inside a stack with a merge commit.** Squashing rewrites the parent's
  commits, so every branch above it loses its base and has to be rebuilt by hand. GitHub's
  *Rebase and merge* does the same — it always creates new commits — so it is only safe if every
  branch above is then restacked by hand. A merge commit keeps the commits the next branch is built
  on. Squashing is fine again for the last pull request of a stack, and for any standalone pull
  request.
- **Delete the branch once its pull request is merged.** That deletion is what makes GitHub
  retarget the child pull request onto the merged one's base; with automatic deletion off, the
  stack does not collapse until someone clicks *Delete branch*.
- **Restack with `git rebase --update-refs`** when a lower branch is amended: run it on the top
  branch and every branch pointer below it moves with it. Then `git push --force-with-lease`,
  never a bare `--force`.
- **Test-merge the whole stack locally before claiming it is conflict-free.** A stack that is
  green branch by branch can still conflict on the way down.
- **One phase in flight at a time.** Two open phases on the same stack means restacking twice
  for every review comment.
- **A phase does not wait for its own review to unblock the next one.** Start phase N+1 on the
  tip as soon as phase N is code-complete; review comments land as new commits and the restack
  carries them up.

## 3. Issue model — four levels

| Level | Object | Carries | Created |
|---|---|---|---|
| Roadmap | **epic issue**, template *ADR epic*, label `adr-epic` | the decision, what it excludes, its dependencies — dated in the Project | as soon as the ADR is on the roadmap |
| ADR | **milestone** `ADR-NNN — <title>` | the whole record and its progress bar | when the ADR is drafted |
| Phase | **parent issue**, template *ADR phase*, sub-issue of the epic | the phase scope quoted from the ADR, its acceptance criteria, its branch | when the ADR is accepted |
| Task | **sub-issue**, template *ADR task* | one testable outcome, one criterion that can fail | with its phase |

**Why an epic above the milestone.** A milestone is not an item of a GitHub Project, so it
cannot become a bar on a roadmap. The epic is what puts an ADR on the plan months before it is
written, and it is what the phases hang from once they exist: progress then rolls up task →
phase → epic.

**Decompose late.** Only the epics exist for the whole roadmap. The phases of an ADR do not
exist until the ADR is written, so their issues are created then — creating them earlier
produces issues that rot.

Tasks are **native GitHub sub-issues**, not a Markdown checklist in the phase issue. A checklist
item cannot be assigned, labelled, referenced by a commit or closed by a pull request; a
sub-issue can, which is what makes the board readable as a changelog afterwards.

`gh` has no sub-issue command. Create the issues normally, then attach each child with the
GraphQL mutation — both node ids first, then one call per child:

```bash
nid() { gh api graphql -f query="query{repository(owner:\"adorey\",name:\"cortex\"){issue(number:$1){id}}}" \
        --jq '.data.repository.issue.id'; }

gh api graphql -H "GraphQL-Features: sub_issues" \
  -f query='mutation($p:ID!,$c:ID!){addSubIssue(input:{issueId:$p,subIssueId:$c}){subIssue{number}}}' \
  -f p="$(nid 12)" -f c="$(nid 13)"
```

## 4. The roadmap Project

The epics live in the GitHub Project **Cortex roadmap**, linked to this repository. It adds
what issues cannot carry on their own:

| Field | Meaning |
|---|---|
| `Status` | where the item stands — the Project's built-in field |
| `Wave` | the roadmap wave: V0 Foundation → V5 Scale & offer, or Transverse |
| `Start` / `Target` | the dates that draw the bar in the **Roadmap** view |

The wave is a Project field and **not a label** on purpose: it moves every time the roadmap is
re-planned, and a label copy of it would silently drift. Labels carry what does not move.

The Roadmap view is the Gantt chart. The Table view, grouped by `Wave`, is the planning view.

## 5. Labels and the definition of ready

Created and kept idempotent by [bin/setup-labels.sh](../../bin/setup-labels.sh) — run it again
after adding a line, it updates instead of failing.

| Label | Meaning |
|---|---|
| `adr-epic` / `adr-phase` / `adr-task` | the issue's level, see §3 |
| `adr:007` | belongs to that decision record — one label per ADR entering implementation |
| `phase:1` … `phase:8` | phase within the ADR, matching the ADR's own numbering |
| `type:spec` | the Markdown cascade — roles, capabilities, personalities, workflows |
| `type:core` | cortex-core, the CLI, packaging and distribution |
| `type:runtime` | the engine — API, agentic loop, stores, security gate |
| `type:test` | tests, fixtures, validators, test tooling |
| `type:security` | security hardening or a security finding |
| `type:perf` | optimisation or a performance finding |
| `type:docs` | documentation, ADR amendment, release note |
| `type:infra` | Docker, CI, deployment, configuration |
| `gate:blocking` | must land before the ADR's own release gate — never deferred |
| `status:blocked` | waiting on something outside the issue; the comment says what |

`type:spec`, `type:core` and `type:runtime` mirror the ADR-002 firewall — the runtime consumes
the spec, the spec never depends on the runtime. A task that needs two of them is usually two
tasks, and the board makes that visible.

The phase number comes from the **ADR**, not from the execution order. If an ADR runs its
phases 1 → 3 → 2, `phase:3` is worked before `phase:2` and the labels stay aligned with the
record.

**Definition of ready.** An issue is not ready to be picked up until it has: a milestone, an
`adr:` label, a `phase:` label, a `type:` label, and **an acceptance criterion that can fail**.
"Add a resolver" is not a criterion; "`bin/validate-overlays.sh --strict` exits 0 on a host
project scaffolded without a `cortex/` directory" is.

**Pull requests carry labels too** — the same ones as the issues they deliver. Every pull request
has at least one `type:*`; ADR work adds its `adr:NNN`, its `phase:N` and, when the phase gates the
release, `gate:blocking`. A release pull request carries `type:docs`. The board then filters pull
requests the way it filters issues — and a pull request whose labels differ from its issues' is
usually delivering something the issues do not describe.

## 6. Commits and closing keywords

Commits follow the [convention in CONTRIBUTING.md](../../CONTRIBUTING.md#commit-message-convention)
— gitmoji, Conventional Commits, one line, no body, no trailer. ADR work adds the task number
immediately before the subject:

```text
<gitmoji> <type>(<scope>): #<issue> <subject>
```

```text
✨ feat(core): #42 resolve the cascade from a configurable base root
♻️ refactor(runtime): #43 consume cortex-core instead of the local resolver
✅ test(core): #44 cover a base root outside the project tree
📝 docs(adr): #48 amend ADR-007 with the phase order
```

The number goes first because the issue's timeline then reads as a changelog of that task, in
order, without opening a single diff.

Commits carry no body, so **closing keywords live in the pull request description**
(`Closes #42, #43`), never in a commit message.

⚠️ **They will not close anything on their own in this model.** GitHub closes a linked issue
only when the pull request merges into the **default branch**. Every pull request of a stack
targets the branch below it, never `main` — so the keywords record the link and produce the
sidebar entry, and close nothing. On the project this process comes from, sixty-four issues
stayed open through a release because the keywords were in the stacked pull requests only.

Two ways out, and one of them is mandatory:

- repeat the **whole** `Closes #…` list in the final pull request (`release/adr-NNN-slug` →
  `main`), which is the one merge that lands on the default branch; or
- close the issues by hand at release time, from the lists the phase pull requests declared.

## 7. Pipeline per phase

Every phase goes through the same eight steps. The checklists belong to
[the workflow](../../agents/workflows/engineering/adr-implementation.md); the sequence is:

1. **Dispatch** — the phase issue is broken into sub-issues and handed to the leads.
2. **Technical breakdown** — the open design points are closed before any code.
3. **Implementation** — the leads implement, pulling in other roles as the design requires.
4. **QA** — a test that cannot fail proves nothing.
5. **Performance audit** — measured, not asserted.
6. **Security audit** — review, plus active probing of what the phase exposed.
7. **Documentation** — merged with the code it describes.
8. **Pull request** — opened once steps 4 to 7 have signed off, targeting the parent branch.

A step that finds a defect sends the phase back to step 3; it does not open a follow-up issue on
a later phase, because the stack would carry the defect upward.

**Merging is never delegated.** The maintainer reviews and merges every pull request of the
stack, including the last one into `main`.

## 8. Gates

- **Phase gate.** All sub-issues done, CI green on the phase branch, QA + performance + security
  signed off, documentation updated. Only then does the pull request open.
- **ADR gate.** An ADR may declare a subset of its phases as mandatory before a release. Nothing
  that depends on the gate starts until those phases have merged into the release branch. Their
  tasks carry `gate:blocking`.

## 9. Closing an ADR

1. Final pull request: `release/adr-NNN-slug` → `main`, describing the whole decision and
   carrying the **full** `Closes #…` list (§6).
2. The ADR status becomes `Implemented`, with an amendment entry recording what changed during
   implementation. An ADR is appended to, never rewritten.
3. `release/X.Y.Z` — `changelog/X.Y.Z.md` and the `CHANGELOG.md` section — stacked last, so the
   note describes only what its branch contains.
4. Every issue delivered is closed — by the final pull request's keywords, or by hand against
   the lists.
5. Phase branches are deleted; the milestone closes on its own once every issue is closed; the
   epic closes with it.
6. An issue delivered only in part stays **open**, with a comment saying what shipped and which
   criterion remains.
