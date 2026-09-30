# Workflow: Code review, and review feedback

<!-- GENERIC WORKFLOW — cortex
     Can be overridden by {project}/agents/workflows/engineering/code-review.md
-->

> **Blocking and major points are dealt with before the *Approve*. Everything else gets an answer, without another review round.**
> A written convention not followed, an acceptance criterion not covered, or a defect that prevents shipping is blocking.
> Feedback is never accepted, nor fixed, before it is checked: it must be shown to be sound, to actually apply, and to come from the pull request.

This workflow has two modes:

- **mode A**: reviewing someone's pull request;
- **mode B**: handling the feedback on ours.

The legend, the rules and the publication apply to **every reviewer, human or assisted**, and to every service of the project. Both sides apply the same grid: that is what makes a review converge. Modes A and B describe the assisted procedure; a reviewer without an agent applies its checks, without the roles.

A project that tracks review statuses — labels, an issue tracker's states — or adds checks of its own overrides this workflow, with `Semantic: replacement` (see [docs/extending-layers.md](../../../docs/extending-layers.md)).

## 🎯 Triggers

This workflow activates when the prompt contains formulations such as:

- **Mode A**: "review the PR", "review #1234", "new round on #1234", "look at X's pull requests, approve or give feedback".
- **Mode B**: "I got feedback on my PR", "look at the review comments", "fix and answer the threads".

## 👥 Agents involved

The steps name **roles**, not characters: the alias shown depends on the active theme, and there is none without a personality.

| Step | Role | Responsibility |
|---|---|---|
| A1, A4, B1, B7 | `roles/prompt-manager.md` | Scoping, write-up, answers, the human's go-ahead |
| A2, A3, B2 to B5 | **Domain expert** (below) | Reading the diff, checking the findings, fixing |
| A2 | `roles/security-compliance/security-engineer.md` | The security side of the diff |
| A3, B3, B5 | `roles/engineering/qa-automation.md` | Does the test prove what it says; the mutation check |
| B6 | **Counter-reviewer** | A fresh reviewer, without the context of the fix |

**The domain expert** is the one of the area the pull request touches. The `project-context.md` of the service — or of the project — gives its stack, its conventions and its tooling.

- `engineering/lead-backend` for a server-side application service;
- `engineering/lead-frontend` for an interface, web or mobile;
- `engineering/platform-engineer` for infrastructure;
- `engineering/dba` for a schema or a migration;
- `data/data-analyst` for data.

A pull request that touches several areas brings in each expert on their own hunks.

## 🏷️ Shared legend

The reviewer and the author classify with this legend, and with it alone. A class is justified by its criterion.

| Class | Criterion | Handling |
|---|---|---|
| 🔴 **Blocking** | A **written convention** not followed, and cited (rule 3); an **acceptance criterion** of the issue not covered, or an announced feature missing or contradicted; a **defect introduced that prevents shipping**: it blocks a use, even an edge case, or it corrupts or destroys data, opens a hole, breaks compliance | Fixed before the *Approve* |
| 🟠 **Major** | A **defect introduced and reachable that does not block the use but degrades it**: a misleading message, log or comment, needless retries, degraded performance on a real path; or a path introduced and reachable **with no test** | Fixed before the *Approve* |
| ⚪ **Minor** | Not a defect — a simplification, readability, non-critical performance, an unwritten preference — or a **latent** defect, which no real caller reaches today | The author answers "taken" or "not taken". A refusal needs no justification and reopens no thread |
| ❓ **Doubt** | A suspected 🔴 or 🟠 that could not be proven | The author answers with their proof. The answer clears the doubt, or confirms it as a 🔴 or a 🟠 |
| 🎫 **Out of scope** | Checked and useful, but older than the pull request, outside its scope, or outside the round's delta (rule 7) | A comment, with a proposed issue. It does not block, and it is not fixed in the pull request |

There is no other class. "Recommended" or "optional" is a ⚪. "To do before shipping" is a 🔴 or a 🟠, by its criterion. A "known defect" note is one of the 🎫's options.

## ⚖️ Non-negotiable rules

1. **A 🔴 or a 🟠 is proven in the code.** A defect must be:
   - **introduced by the pull request**: absent from the base, or present but made reachable or extended by it. Only the introduced part counts; the older part is a 🎫;
   - backed by a **concrete, reachable scenario**: a real caller, real states and transitions, in a configuration a user has or will have once the pull request is deployed, flags turned on included.

   For an acceptance criterion, cite it, with the code that contradicts it or the scenario that shows it missing. A justification written in answer to a review is no announcement of the pull request.
2. **A defect older than the pull request is not fixed in it**: it becomes a 🎫. Unless fixing it is the very purpose of the pull request: the criterion is then not covered, and that is a 🔴.
3. **A written convention not followed is blocking.** It is written in the project's `project-context.md`, or in the service's, and it is cited. An unwritten preference stays a ⚪; if it deserves to be a rule, propose it as a convention, outside the pull request.
4. **Human arbitration is for what development has not already settled**: creating an issue, a new feature or a wider scope, a design problem — a new mechanism among them (rule 5). What the issue, an ADR or the pull request's "Decisions" section settled is not arbitrated again. The rest is settled by proof: the reviewer sets the class, the author contests it with their proof, and a lasting disagreement is settled live.
5. **No new mechanism in answer to a review**, neither in the author's fix nor in the one the reviewer suggests. A mechanism is an added lock, cache, status, column, message or service. The fix is minimal and aimed at the defect: every added mechanism opens its own review surface, and that is what makes a pull request go round in circles. If the minimal fix needs one, it is a design problem: it is arbitrated **before** it is written.
6. **A decision made is not reopened**, unless a new fact is proven, which is itself to be arbitrated. The author records every decision made during the review in the pull request's description, in a "Decisions" section: the date, who decided, and what. That is where the next round reads it.
7. **A review converges.** A **round** is a published review. A **thread** is a subject: the same defect or the same mechanism, however many GitHub threads it comes back in. A reviewer who takes up a subject says so ("follow-up of thread X").
   - In round 1, the whole diff is read.
   - From round 2, a new point may only bear on the **delta of the previous round**: what changed since the last head reviewed. Any other new point is a 🎫. The delta is always read, a fix decided live included.
   - **The one exception is a 🔴 introduced by the pull request** and missed in earlier rounds: it is still raised, at any round. A reviewing mistake happens. It says so ("🔴 missed in round N") and is handled as any 🔴.
   - At a thread's **third round**, the author and the reviewer settle it live — a call, a review meeting. That thread has no written fourth round.
8. **An adversarial counter-review of the delta before every push of fixes** (step B6), and the answer says what it found.

## 📤 Publication

| Situation | Who | GitHub event |
|---|---|---|
| Ready for review, or fixes pushed after a *Request changes* or a *Comment* | Author | Review request |
| At least one 🔴 or 🟠 | Reviewer | *Request changes* |
| No 🔴 nor 🟠, but at least one ❓ | Reviewer | *Comment* |
| No 🔴, 🟠 nor ❓ | Reviewer | *Approve* |

The ⚪ and the 🎫 do not change the verdict, but each calls for an answer from the author before the merge. An *Approve* therefore means that no 🔴, 🟠 nor ❓ is left, and that every comment has its answer when the pull request merges.

---

## Mode A — Reviewing a pull request

### Step A1 — Scoping
**Agent:** `prompt-manager`
**Objective:** Know what is reviewed, against what, and at which round.

**Checklist:**
- [ ] Identify the **base**: the diff reviewed is `base...head`, nothing else. For a stacked pull request, the base is the branch below it, and "older" is meant against it.
- [ ] **Check that the base is current.** Test-merge the head into the branch it targets, with `git merge-tree --write-tree <target> <head>`. A pull request started before a release that changed its ground conflicts, or leans on files that are gone. Say whether it targets the branch the project's process wants.
- [ ] Read the **issue** the pull request delivers — its acceptance criteria — and the **pull request's description**. A criterion delivered by another pull request of the stack must be said so there; it does not count here.
- [ ] Read the "Decisions" section, the issue and the ADRs cited: what they settle is not reopened.
- [ ] Place the **round**: in round 1, the whole diff; later, the previous round's delta and the threads still open. After a rebase, read the delta with `git range-diff`.
- [ ] Record the **CI state**, or say that it cannot be checked. It is never assumed. Checks that ran the target's workflows as they were before the base moved prove nothing: they are run again.
- [ ] List what the description says was verified: each claim is replayed in step A3.
- [ ] Identify the areas touched, hence the experts and the conventions that apply, and the formats, states and paths concerned.

**Deliverable:** The scope reviewed, the criteria and claims to check, the conventions that apply, the experts brought in.

---

### Step A2 — Review
**Agent:** The domain expert, and `security-engineer` for the security side
**Objective:** Raise findings on the scope, and on it only.

**Checklist:**
- [ ] Read the hunks of the scope **and the callers of the changed code**: that is where regressions are born. The rest of the code is read to understand, not to open new subjects.
- [ ] Check each acceptance criterion and each announcement of the description against the code.
- [ ] Check the diff against the written conventions of the project and of the service.
- [ ] Anchor each finding at `file:line`: the line of the **new** file, in a hunk of the diff.

**Deliverable:** The list of findings, anchored.

---

### Step A3 — Checking each finding
**Agent:** The domain expert, with `qa-automation` for the tests
**Objective:** Keep only what is proven.

**Checklist:**
- [ ] **Soundness.** The finding is true in the code. Read the method **whole**, its callers and its tests.
- [ ] **Effect.** The scenario is reachable: which caller, which states, which transition. Does it block the use, degrade it, or is it latent?
- [ ] **Origin.** Is the defect introduced, made reachable, extended, or older? Check with `git show <base>:<file>` and `git log -S`.
- [ ] **Fix.** The one proposed is minimal and adds no mechanism.
- [ ] **The description's claims.** Each verification the pull request says it ran is run again. For content an agent reads — a role, a theme, a workflow — that includes a real conversation that loads it.
- [ ] A 🔴 or a 🟠 that cannot be proven becomes a ❓. Any other finding not proven is dropped.

**Deliverable:** Each finding classified in the legend, with its proof.

---

### Step A4 — Write-up
**Agent:** `prompt-manager`
**Objective:** Publish a review that can be handled in one round.

**Checklist:**
- [ ] Write the review with the template below, verdict first. Its event follows the "Publication" table.
- [ ] **Submit it to the human reviewer before it is published**, with the 🎫 to arbitrate set apart. Nothing leaves without their go-ahead.
- [ ] Publish it, with its comments anchored in the diff.

Template of the published review:

```markdown
> Assisted review — <reviewer>, with <roles brought in>. Head reviewed `<sha>`, base `<branch>`, round <n>.

**Verdict:** Approve | Request changes | Comment — <n> 🔴, <n> 🟠, <n> ❓, <n> ⚪, <n> 🎫

### What holds
What was checked and calls for nothing, commit by commit. These points are closed.

### 🔴 Blocking
Anchor — the convention cited, the criterion, or the scenario and its effect — the proof that the pull request introduces it — the minimal fix.

### 🟠 Major
Anchor — the scenario and its effect, or the path with no test — the minimal fix.

### ❓ Doubts
Anchor — what is suspected — what would clear it.

### ⚪ Minor

### 🎫 Out of scope
Only those the reviewer validated, with the proposed issue. They do not block.
```

**Deliverable:** The review published, with its event.

---

## Mode B — Handling the feedback on our pull request

### Step B1 — Inventory
**Agent:** `prompt-manager`
**Objective:** Know what is handled, and what is already closed.

**Checklist:**
- [ ] List every point: its thread, its anchor, its class according to the reviewer, and the round it was raised in. A point outside the legend is classified again with the legend.
- [ ] Spot the new points outside the previous round's delta: they are 🎫 (rule 7), except a 🔴 introduced by the pull request, which is handled.
- [ ] Record the **closing criteria** the reviewer set themselves. Such a criterion may make their own points more lenient than the legend, never stricter.
- [ ] Read the "Decisions" section, the issue and the ADRs cited. A point already settled is closed by pointing there.
- [ ] Spot the threads at their third round: they are settled live (rule 7), not in writing.

**Deliverable:** The inventory of points, each with its class and its status.

---

### Step B2 — Soundness: is the finding true?
**Agent:** The domain expert

**Checklist:**
- [ ] Check it in the code, reading the method **whole**, with its callers. The proof is written as `file:line`.
- [ ] Verdict: **sound**, **partly sound** or **unsound**. An "unsound" verdict comes with its proof: the code, the configuration, the git history.

**Deliverable:** A soundness verdict per point, with its proof.

---

### Step B3 — Effect: does the feedback really apply?
**Agent:** The domain expert, `qa-automation`

**Checklist:**
- [ ] Is the scenario reachable? Walk the callers, the states, the transitions and the formats.
- [ ] Assess the class again, up or down, and say why. A disagreement on the class is proven; if it lasts, it is settled live.
- [ ] Does the suggested fix really fix the defect, without opening another or adding a mechanism?

**Deliverable:** Each point's class, confirmed or assessed again with its reason.

---

### Step B4 — Origin: does the defect come from the pull request?
**Agent:** The domain expert

**Checklist:**
- [ ] Compare with the base: `git show <base>:<file>`, `git log -S`, and the behaviour before the pull request. A suggestion of an earlier round, even the reviewer's own, is checked like the rest.
- [ ] **Introduced**, made reachable or extended, sound and effective: the introduced part is fixed in the pull request.
- [ ] **Older**, or outside the scope: no fix in the pull request, but a 🎫, which the author carries, even when the reviewer proposed it.

**Deliverable:** For each point, a fix in the pull request or a proposed issue.

---

### Step B5 — Fix
**Agent:** The domain expert, `qa-automation`

**Checklist:**
- [ ] Fix the 🔴 and 🟠 that are sound, effective and introduced. The ⚪ stay free.
- [ ] **A minimal fix**, with no new mechanism. If one is needed, it is arbitrated before it is written (rule 5).
- [ ] A test that fails without the fix, **checked by mutation**: take the fix out, and the test breaks. If the defect cannot be tested — configuration, documentation — say so.
- [ ] Run the tooling the `project-context.md` declares: tests, linters, static analysis with no new error against the base.
- [ ] Short commits, and no push yet.

**Deliverable:** The fixing commits, each with its test.

---

### Step B6 — Adversarial counter-review of the delta
**Agent:** The counter-reviewer, who does not have the context of the fix: a sub-agent, a new session, another tool, or another developer

**Checklist:**
- [ ] Review **only this round's delta**, with this workflow's grid, as the reviewer will: the legend, rules 1 to 3 and the checks of step A3.
- [ ] Look first for a new failure path, a reachable state forgotten, a false justification, or a test that does not test what it says.
- [ ] What it finds is fixed **before** the push, then back to B5. Stop when it finds no more 🔴 nor 🟠.

**Deliverable:** What the counter-review found, and the fixes made.

---

### Step B7 — Answer
**Agent:** `prompt-manager`
**Objective:** That the reviewer can close every thread without reading the whole pull request again.

**Checklist:**
- [ ] **One consolidated summary**: a table point → reviewer's class → soundness → effect → origin → action (a commit and its test, or a reasoned refusal).
- [ ] **An answer on every comment**, with those four points. For a ⚪, "taken" or "not taken" is enough.
- [ ] What the adversarial counter-review found and fixed.
- [ ] The 🎫 with their status: "proposed, awaiting arbitration", or their number once created.
- [ ] The description's "Decisions" section, updated.
- [ ] **All of it submitted to the human author before the push and the publication.** Then the push and the answers, and the "Publication" table: after a *Request changes* or a *Comment*, request the review again; after an *Approve*, merge once every comment has its answer.

**Deliverable:** The answers published.

---

## 🎫 Template — an issue proposed for arbitration

An issue is created only after a human validates it. The proposal must be enough to decide without opening the code again:

- **Title**: the defect, not the solution.
- **Link**: the pull request and the review thread it comes from.
- **Finding**: what happens, with the proof (`file:line`).
- **Origin**: older since which issue or commit, or outside the pull request's scope, and why.
- **Scenario and impact**: who is affected, when, how often, how badly, and what is lost if nothing is done.
- **Options**: for each, the cost, the risk, and what it closes or leaves open. "Document it as a known defect" is one of them.
- **Recommendation**, and **the decision expected**, as a closed question.

## ✅ Definition of "done"

- [ ] **Mode A**: the review is published with its verdict and its event. Each finding is classified and anchored, and the 🎫 are arbitrated or awaiting arbitration.
- [ ] **Mode B**: every comment has its answer, or is taken live. The summary is published, and the 🎫 are proposed.

## 🚫 Anti-patterns

- ❌ Accepting feedback without checking it in the code, or calling it unsound without proof.
- ❌ Fixing in the pull request a defect older than it.
- ❌ Answering feedback with a new mechanism, or suggesting one, without arbitration.
- ❌ Classifying as 🔴 or 🟠 a defect with no reachable scenario, or a defect older than the pull request.
- ❌ Classifying as ⚪ a defect introduced and reachable.
- ❌ Approving with a 🔴, a 🟠 or a ❓ still open — above all an acceptance criterion not covered.
- ❌ Basing a convention 🔴 on a rule that is not written.
- ❌ Using a class outside the legend, or an event outside the "Publication" table.
- ❌ Raising, from round 2, a point outside the previous round's delta other than as a 🎫 — except a 🔴 introduced by the pull request.
- ❌ Carrying on in writing a thread at its third round.
- ❌ Pushing fixes without an adversarial counter-review of the delta.
- ❌ Answering "fixed" with no commit nor test, or leaving a comment unanswered.
- ❌ Creating an issue without human arbitration, or proposing one without the context to decide.
- ❌ Reopening a decision already made without a new fact.
- ❌ Trusting checks that ran before the base moved, or a claim of the description that was not replayed.

## 🔗 Related workflows

- `feature-development.md` — this workflow takes over at its step 2, when the pull request opens.
- `adr-implementation.md` — the pull request of each phase is reviewed with it, once handed over (step 8).
- The security review of `security-engineer` stays due before every merge the process asks it for: the security side of step A2 does not replace it.
