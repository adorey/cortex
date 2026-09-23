# Workflow: Implementing a phase of an accepted ADR

<!-- GENERIC WORKFLOW — cortex
     Can be overridden by {project}/agents/workflows/adr-implementation.md
     A project that wants its own stack rules in the checklists (a framework's migration
     tool, a static analyser, a latency budget) overrides this file — workflows use
     replacement, not additive overlays.
-->

## 🎯 Triggers

This workflow activates when the prompt contains formulations such as:
- "implement ADR-00X", "start ADR-00X", "phase N of ADR-00X"
- "next phase", "carry on with the ADR", "close phase N"
- any request to write code whose scope is already described by an accepted ADR carrying
  numbered phases

It does **not** activate for writing or amending an ADR (that is a design conversation), nor
for a change small enough to land in one pull request — use `feature-development` for that.

## 📋 Preconditions

- The ADR is **Accepted**, and its phase list is the authoritative scope.
- The ADR release branch exists and is pushed (`release/adr-NNN-slug`).
- The phase has a parent issue with sub-issues, a milestone and labels (`adr:NNN`, `phase:N`,
  `type:*`), attached to the ADR's epic.
- One phase is in flight at a time. Two open phases on the same stack means restacking twice
  for every review comment.

The branch, issue, label and gate **mechanics** this workflow assumes are described once, in
the project's delivery process — for Cortex itself,
[docs/process/adr-implementation.md](../../../docs/process/adr-implementation.md). They are not
restated here.

## 👥 Agents involved

| Step | Role | Responsibility |
|---|---|---|
| 1 | `roles/prompt-manager.md` | Phase intake, breakdown into sub-issues, dispatch |
| 2 | `roles/engineering/architect.md` | Open design points, boundaries, seams |
| 3 | `roles/engineering/lead-backend.md` / `roles/engineering/lead-frontend.md` | Implementation, calling in other roles as needed |
| 4 | `roles/engineering/qa-automation.md` | Unit, functional and regression coverage |
| 5 | `roles/engineering/performance-engineer.md` | Performance audit, measured |
| 6 | `roles/security-compliance/security-engineer.md` | Security audit and active probing |
| 7 | `roles/communication/tech-writer.md` | Documentation and ADR amendment |
| 8 | `roles/prompt-manager.md` | Pull request, then hand over to the maintainer |

Roles called in **on demand** by the leads at step 3, never by default:
`roles/engineering/dba.md` (schema, indexes, migrations),
`roles/engineering/platform-engineer.md` (container, CI, environment),
`roles/security-compliance/compliance-officer.md` (personal data exposed),
`roles/product/product-owner.md` (a trade-off that changes what a user sees).

---

## 📋 Steps

### Step 1 — Phase intake and dispatch
**Agent:** `prompt-manager`
**Objective:** Turn one phase of the ADR into independently testable sub-issues, then hand them
to the right lead.

**Checklist:**
- [ ] Re-read the phase in the ADR — the record is the scope, not the memory of it
- [ ] Verify the previous phase has merged, or is code-complete, before branching
- [ ] Create the phase branch from the tip of the previous branch in the stack
- [ ] Break the phase into sub-issues, each with an acceptance criterion that can fail
- [ ] Label every sub-issue (`adr:NNN`, `phase:N`, `type:*`, `gate:blocking` when relevant)
- [ ] Name the lead who owns each sub-issue, and say why that lead
- [ ] Flag anything in the phase whose design the ADR does **not** settle — it goes to step 2
      before any code

**Deliverable:** A phase branch, a labelled sub-issue per task, and an explicit dispatch.

---

### Step 2 — Technical breakdown
**Agent:** `architect`
**Objective:** Resolve what the ADR left open, and set the boundaries the implementation must
not cross.

**Checklist:**
- [ ] Confirm the phase respects the boundaries and seams the ADR declared
- [ ] Decide the open design points, with the alternatives and why they lost
- [ ] Identify what this phase makes harder for the phases above it in the stack
- [ ] Confirm no new runtime dependency, or justify it against writing it
- [ ] If a decision contradicts the ADR, **stop**: an ADR amendment comes first

**Deliverable:** Design points closed, boundaries stated. Skipped only when the ADR already
specifies the phase down to the interface level.

---

### Step 3 — Implementation
**Agent:** `lead-backend` and/or `lead-frontend`
**Objective:** Produce the phase to the standards of `project-context.md` and the capabilities
loaded for the stack.

**Checklist:**
- [ ] Follow the conventions of `project-context.md` and the loaded capabilities — the stack's
      own rules live there, not in this workflow
- [ ] Unit tests written alongside the code, not after it
- [ ] Any schema or data migration is read by hand and can be reversed
- [ ] Call in the roles the design needs (schema → `dba`, personal data → `compliance-officer`,
      container or CI → `platform-engineer`) and record what they answered
- [ ] The project's static checks pass, and no baseline or ignore list grows
- [ ] One commit per coherent step, `#<issue>` before the subject, no body, no trailer
- [ ] Leave the sub-issues **open**, and know why they will not close themselves: GitHub closes
      a linked issue only when a pull request merges into the **default branch**, and every pull
      request of a stack targets the branch below it. The closing happens at release time.

**Deliverable:** Code-complete phase branch, CI green.

---

### Step 4 — QA
**Agent:** `qa-automation`
**Objective:** Prove the phase behaves as specified, and that nothing above or below it broke.

**Checklist:**
- [ ] Every acceptance criterion of the phase issue has a test that asserts it
- [ ] **Run the new test against the unfixed code first** — a test that cannot fail proves
      nothing
- [ ] Nominal, boundary and error cases; degraded mode when an integration is misconfigured
- [ ] Every entry point the phase touches is covered, not only the first one written
- [ ] Regression: the existing suite passes unchanged, or every change to it is justified in the
      pull request
- [ ] Fixtures stay neutral (`example.com`, `acme`) — no real name, email or figure

**Deliverable:** Green suite, and a written statement of what is **not** covered.

---

### Step 5 — Performance audit
**Agent:** `performance-engineer`
**Objective:** Establish the cost of the phase with figures, before it is built upon.

**Checklist:**
- [ ] Timing and resource use on the paths the phase touched
- [ ] No hidden repetition introduced — a call, a query or a file read that now runs once per
      item instead of once
- [ ] Cache behaviour verified: hit rate, and that a new cache key did not silently multiply the
      entry count
- [ ] Measure against a base rebased on the release branch — a stale base invents bottlenecks
- [ ] Compare against the performance constraints declared in `project-context.md`
- [ ] A regression is either fixed in this phase or opened as a `type:perf` issue with its
      figure — never carried silently

**Deliverable:** Before/after figures on the touched paths, or an explicit "not applicable" with
the reason.

---

### Step 6 — Security audit and active probing
**Agent:** `security-engineer`
**Objective:** Attack what the phase just exposed. Reviewing the diff is not enough.

**Checklist:**
- [ ] Review against the OWASP Top 10, weighted to what the phase added
- [ ] **Probe it live**: call every new or moved entry point anonymously, with a wrong role, with
      an expired or revoked credential, and with another user's identifier
- [ ] Authorisation is enforced where the data is read, not only where it is displayed
- [ ] No secret reaches a page, a log, an API response or a cache key
- [ ] Error semantics leak nothing: `401` versus `403`, and no proof that a resource exists
- [ ] Rate limits and payload ceilings actually trigger, verified by request
- [ ] Dependency audit clean; any new dependency justified and pinned

**Deliverable:** A signed-off finding list — each item fixed in this phase, or an issue labelled
`type:security` with its severity. A `gate:blocking` finding blocks the phase.

---

### Step 7 — Documentation
**Agent:** `tech-writer`
**Objective:** Make the phase usable and operable by someone who did not write it.

**Checklist:**
- [ ] New or changed interfaces documented, with their error semantics
- [ ] New configuration documented where operators look for it
- [ ] ADR amended (append-only) if a decision moved during implementation
- [ ] Deprecations stated with what replaces them and when they disappear
- [ ] The project's language rule respected — a checker is the gate, not the reviewer

**Deliverable:** Documentation merged in the same pull request as the code it describes.

---

### Step 8 — Pull request and handover
**Agent:** `prompt-manager`
**Objective:** Open a reviewable pull request and hand the decision back to the maintainer.

**Checklist:**
- [ ] Target the **parent branch** of the stack, never `main` directly
- [ ] Description: what the phase does, the acceptance criteria met, the sign-offs from steps 4
      to 6, what was deliberately left out
- [ ] `Closes #NN` for every sub-issue — commits carry no body, so the closing keywords live
      here. They will not fire until something merges into the default branch: they must be
      repeated in the final pull request, or closed by hand at release time
- [ ] Test-merge the whole stack locally and state that it is conflict-free
- [ ] Say explicitly when a diff is balanced (a rename, a move, a translation): a review that
      compares addition and deletion counts cannot see those
- [ ] **Do not merge.** Reviewing and merging belong to the maintainer, for every pull request
      of the stack including the last one

**Deliverable:** An open pull request, and a one-paragraph summary of what to look at first.

---

## ✅ Definition of "done" (per phase)

- [ ] Every sub-issue done, phase issue done
- [ ] CI green on the phase branch
- [ ] QA, performance and security signed off — a step that found a defect saw it fixed and
      re-verified, not deferred to a later phase
- [ ] Documentation merged with the code
- [ ] Pull request open against its parent branch, stack test-merged
- [ ] The next phase can branch from this tip without a restack

## 🔗 Related workflows

- `feature-development.md` — for a change that is not driven by a phased ADR
- `tech-watch.md` — when a phase needs a technology nobody on the team has used
