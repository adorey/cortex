# Workflow: Support triage (N2 → N3)

<!-- GENERIC WORKFLOW — cortex
     Can be overridden by {project}/agents/workflows/support-triage.md
-->

## 🎯 Triggers

This workflow activates when the prompt contains formulations such as:
- "client request", "support ticket", "customer reported", "incident", "bug report"
- "investigate", "diagnose", "analyse the issue", "why does X fail"
- an issue-tracker event (new ticket / new client reply) routed to support

## 🚦 Orchestration rule

The `support-engineer` analyses; it never dispatches. **Every cross-role need flows through the
`prompt-manager`**, who validates and routes it. No role talks to another directly.

## 👥 Agents involved

| Step | Role | Responsibility |
|---|---|---|
| 1 | `roles/prompt-manager.md` | Intake & normalise the client request |
| 2 | `roles/engineering/support-engineer.md` | Read-only pre-analysis & triage decision |
| 3 | `roles/prompt-manager.md` | Route the support-engineer's structured request |
| 4 | N3 specialist(s) (e.g. `roles/engineering/lead-backend.md`, `roles/security-compliance/security-engineer.md`, `roles/engineering/dba.md`, `roles/engineering/performance-engineer.md`) | Refine a specific point of the analysis |
| 5 | `roles/communication/tech-writer.md` | Draft the client-facing response |
| 6 | `roles/prompt-manager.md` + engineering team | (Phase 2, human-gated) Author the fix on a branch & push for review |

## 📋 Steps

### Step 1 — Intake
**Agent:** `prompt-manager`
**Objective:** Receive the client request, normalise it, and hand a clear brief to the support-engineer.

**Checklist:**
- [ ] Capture the raw client request verbatim
- [ ] Identify the affected subsystem / actor from `project-overview.md`
- [ ] Hand off to the support-engineer with a clear brief

---

### Step 2 — Pre-analysis (read-only)
**Agent:** `support-engineer`
**Objective:** Produce the most complete evidence-backed analysis possible, without acting externally.

**Checklist:**
- [ ] Read `project-overview.md` and `project-context.md`
- [ ] Target the potential symptoms; reproduce/characterise the problem
- [ ] Form ranked hypotheses, each with evidence references and a falsification test
- [ ] Assess severity, blast radius, affected actors, confidence
- [ ] Investigate READ-ONLY only (code, docs, issue tracker, anonymised DB)

**Deliverable:** the structured analysis (Problem · Symptoms · Hypotheses · Reproduction · Severity/Impact · Verdict · Request).

---

### Step 3 — Triage & structured request
**Agent:** `support-engineer` → `prompt-manager`
**Objective:** Decide and route — resolve, escalate, request a fix, or ask the client.

**Checklist:**
- [ ] Apply the triage matrix → explicit, justified verdict
- [ ] Emit ONE structured request addressed to the `prompt-manager`
- [ ] Escalation requests name the specialist **role** and the precise question
- [ ] The `prompt-manager` validates/reframes the request before routing it

---

### Step 4 — N3 refinement *(only if escalated)*
**Agent:** the relevant specialist role(s), dispatched by the `prompt-manager`
**Objective:** Answer the specific question the support-engineer raised.

**Checklist:**
- [ ] The `prompt-manager` dispatches to the named specialist role(s)
- [ ] The specialist answers the precise question (not the whole ticket)
- [ ] Results return to the `support-engineer`, who consolidates them into the analysis

---

### Step 5 — Client response drafting
**Agent:** `tech-writer` (requested via the `prompt-manager`)
**Objective:** Turn the consolidated analysis into a clear client-facing response.

**Checklist:**
- [ ] The support-engineer requests the response (it does not write it)
- [ ] The `tech-writer` drafts the reply at the right altitude for the client
- [ ] Internal evidence/refs are not leaked into the client-facing text

---

### Step 6 — Fix *(Phase 2 — only if a fix is required, human-gated)*
**Agent:** `prompt-manager` + engineering team
**Objective:** Correct the defect, on a branch, pushed for human review.

**Checklist:**
- [ ] The support-engineer delegated phase 2 to the `prompt-manager` (it does not pilot it)
- [ ] The `prompt-manager` pilots the engineering team to author the fix
- [ ] The fix lands on a dedicated branch and is pushed for **human review** (never auto-merged)
- [ ] No write/push happens without human validation

---

## ✅ Definition of done

- [ ] A complete, evidence-backed analysis exists for the ticket
- [ ] An explicit triage verdict was recorded
- [ ] If escalated: the specialist's answer is consolidated into the analysis
- [ ] The client response was drafted by the tech-writer (not the support-engineer)
- [ ] If a fix was needed: a branch is pushed for human review (phase 2, gated)
- [ ] The exchange is archived

## 🔗 Related workflows

- `code-review.md` — triggered in phase 2 on the fix PR
- `feature-development.md` — if the resolution turns out to require a new capability
