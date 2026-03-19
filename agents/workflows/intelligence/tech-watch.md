# Workflow: Technology Watch

<!-- GENERIC WORKFLOW — cortex
     Can be overridden by {project}/agents/workflows/tech-watch.md
-->

## 🎯 Triggers

This workflow activates when the prompt contains formulations such as:
- "watch", "benchmark", "compare", "evaluate"
- "should we switch to", "which technology for", "alternatives to"
- "is [tool/lib/framework] right for our project"
- "what exists to do X"

## 👥 Agents involved

| Step | Role | Responsibility |
|---|---|---|
| 1 | `roles/engineering/architect.md` | Need scoping and evaluation criteria |
| 2 | `roles/data/data-analyst.md` | Data collection and structuring |
| 3 | `roles/engineering/architect.md` | Comparative analysis and recommendation |
| 4 | `roles/security-compliance/security-engineer.md` | Security evaluation of shortlisted options |
| 5 | `roles/communication/tech-writer.md` | Formalising the watch report |

## 📋 Steps

### Step 1 — Scoping
**Agent:** `architect`
**Objective:** Define precisely what we are looking for and why.

**Checklist:**
- [ ] Identify the problem or need behind the watch
- [ ] Define selection criteria (performance, maturity, licence, cost, learning curve…)
- [ ] Identify non-negotiable constraints (current stack compatibility, GDPR, support…)
- [ ] Define the scope: quick evaluation or in-depth study?
- [ ] List options already known or anticipated

---

### Step 2 — Data collection
**Agent:** `data-analyst`
**Objective:** Gather reliable, comparable data on each option.

**Checklist:**
- [ ] Collect key data for each option (version, project activity, adoption, benchmarks)
- [ ] Check the date of sources (tech information ages quickly)
- [ ] Identify similar use cases to the project (experience reports, case studies)
- [ ] Note known limitations and frequently reported issues
- [ ] Structure the data in a comparison table

---

### Step 3 — Analysis & Recommendation
**Agent:** `architect`
**Objective:** Produce an argued, contextual recommendation.

**Checklist:**
- [ ] Cross-reference data with the criteria defined in step 1
- [ ] Identify the 2–3 finalists
- [ ] Evaluate the migration / adoption cost for each option
- [ ] Formulate a primary recommendation + one alternative
- [ ] Justify choices with data, not just opinions

---

### Step 4 — Security
**Agent:** `security-engineer`
**Objective:** Ensure the shortlisted options do not introduce risks.

**Checklist:**
- [ ] Check the CVE history of each finalist option
- [ ] Evaluate the maintenance and security patch policy
- [ ] Identify data or access models introduced
- [ ] Verify compliance with the project's GDPR / compliance requirements

---

### Step 5 — Report
**Agent:** `tech-writer`
**Objective:** Produce a usable, archivable reference document.

**Checklist:**
- [ ] Write an executive summary (1 paragraph)
- [ ] Include the option comparison table
- [ ] Document the recommendation and its justifications
- [ ] List next steps if the recommendation is accepted
- [ ] Archive the document in the project docs

---

## ✅ Definition of done

- [ ] Watch report written and archived
- [ ] Recommendation validated by the relevant decision-maker
- [ ] Next steps identified (POC, adoption, drop)

## 🔗 Related workflows

- `feature-development.md` — if the watch leads to adopting a tool to integrate
