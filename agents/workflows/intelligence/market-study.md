# Workflow: Market Study & Diversification

<!-- GENERIC WORKFLOW — cortex
     Can be overridden by {workspace}/agents/workflows/intelligence/market-study.md
     or {service}/agents/workflows/intelligence/market-study.md (replacement semantics).
     Related: tech-watch.md (which technology), innovation-funding.md (how to fund the result).
-->

## 🎯 Triggers

This workflow activates when the prompt contains formulations such as:
- "market study", "market deep-dive", "who are our competitors", "competitive landscape"
- "how do we diversify", "adjacent markets", "what else could we sell"
- "are we still positioned right", "what is the market doing"
- "should we enter X market", "build / buy / partner on X"

> Not this workflow: "which library/tool should we use" → `tech-watch.md`.

## 👥 Agents involved

| Step | Role | Responsibility |
|---|---|---|
| 1 | `roles/product/market-analyst.md` | Scoping: the question behind the question |
| 2 | `roles/data/data-analyst.md` | Internal evidence — what we actually are |
| 3 | `roles/product/market-analyst.md` | External mapping — market, drivers, competition |
| 4 | `roles/product/market-analyst.md` + `roles/engineering/architect.md` | Adjacency scoring (market × feasibility) |
| 5 | `roles/product/innovation-funding-advisor.md` | Which axes carry fundable uncertainty |
| 6 | `roles/security-compliance/compliance-officer.md` | Data-reuse and regulatory limits of the candidate axes |
| 7 | `roles/communication/tech-writer.md` | Decision document |

## 📋 Steps

### Step 1 — Scoping
**Agent:** `market-analyst`
**Objective:** Establish what decision this study must enable. A study that enables no decision is a blog post.

**Checklist:**
- [ ] Name the decision(s) waiting on this study, and who takes them
- [ ] Define the perimeter: geography, buyer type, time horizon
- [ ] State what is out of scope, explicitly
- [ ] List what is already known internally (prior studies, deal loss reports, RFP analyses)
- [ ] Agree the evidence grading convention (verified / measured / declarative / estimated)

---

### Step 2 — Internal evidence
**Agent:** `data-analyst`
**Objective:** Establish what the product *is*, in numbers, before describing what the market is.

**Checklist:**
- [ ] Extract production figures that characterise the footprint (volumes, customers, usage)
- [ ] Separate operated volume from imported/migrated volume — they are not the same claim
- [ ] Note the phrasing traps (what a figure does and does not license you to say)
- [ ] Mine existing internal corpora: RFP analyses, feature matrices, lost-deal notes, support themes
- [ ] Identify assets the market does not know we have

> Most diversification studies fail here: they describe an external market against an imagined version
> of the product.

---

### Step 3 — External mapping
**Agent:** `market-analyst`
**Objective:** Buyer, drivers, and the four rings of competition.

**Checklist:**
- [ ] Identify the buyer, the budget line, and the renewal/purchase cycle
- [ ] Estimate the addressable base — and label the estimate
- [ ] Build the driver calendar: regulation, obligations, deadlines, funding programmes
- [ ] Map ring 1 (direct) with age, footprint, positioning, strength, weakness
- [ ] Map ring 2 (adjacent) and ring 3 (substitutes — including free public platforms and in-house)
- [ ] Map ring 4 (consolidators/acquirers) and recent M&A in the sector
- [ ] Note which competitors have already made the move we are considering
- [ ] Write the symmetric position table: where we win / where we lose

---

### Step 4 — Adjacency scoring
**Agents:** `market-analyst` + `architect`
**Objective:** Convert candidate axes into a contestable grid.

**Checklist:**
- [ ] List candidate axes (from drivers, from lost deals, from unused assets — not from brainstorming alone)
- [ ] Score each: business proximity · platform reuse · addressable size · ease of entry · fundability
- [ ] For each axis, state: what we reuse, what we must build, who is already there
- [ ] Have the architect challenge the reuse score — it is the one most often inflated
- [ ] For each serious axis, pose build / partner / acquire explicitly with cost, delay, risk
- [ ] Write the exclusion list and the reason for each exclusion

---

### Step 5 — Fundability
**Agent:** `innovation-funding-advisor`
**Objective:** Identify which axes carry real technical uncertainty, and the matching instruments.

**Checklist:**
- [ ] Mark each axis with the uncertainty it would have to resolve (or "none")
- [ ] Distinguish the commercially urgent axis from the fundable one — they are rarely the same
- [ ] List instruments with jurisdiction, territorial condition, window and ceiling
- [ ] Flag any axis that is fundable *only* (not viable on own funds) — it is a project, not a product line

---

### Step 6 — Limits
**Agent:** `compliance-officer`
**Objective:** Establish what the candidate axes are not allowed to do.

**Checklist:**
- [ ] Data reuse: does an axis repurpose data collected for another purpose? Say so, in writing
- [ ] Regulatory barriers to entry on each axis (licences, certifications, accreditations)
- [ ] Contractual limits with existing customers and partners
- [ ] Group-level conflicts: is a sister entity already on this market?

---

### Step 7 — Decision document
**Agent:** `tech-writer`
**Objective:** Produce something a leadership team can decide from in one sitting.

**Checklist:**
- [ ] Executive summary: numbered findings, each one actionable
- [ ] Method, sources and limits stated up front, not buried
- [ ] Scoring grid published in full
- [ ] Recommendation table by time horizon, with an explicit "what we do not do"
- [ ] Risk table including dispersion and inaction
- [ ] Decisions requested, as answerable questions with named owners
- [ ] Full source list with links; internal sources cited by path

---

## ✅ Definition of done

- [ ] Every figure carries its evidence grade
- [ ] Every retained axis states what we reuse, what we build, who is there
- [ ] An exclusion list exists
- [ ] The decision list is answerable by a named person
- [ ] The document is archived where strategy documents live in this project

## ⚠️ Failure modes of this workflow

| Symptom | Cause | Fix |
|---|---|---|
| The study reads as a landscape poster | Step 1 skipped — no decision named | Go back and name the decision |
| Every axis looks attractive | No exclusion list | Force step 4's last item |
| Reuse percentages look high everywhere | Architect not involved in step 4 | Re-score with engineering |
| Findings contradict the sales team's experience | Step 2 skipped the internal corpora | Mine lost deals and RFPs first |
| Leadership cannot decide | Decisions phrased as themes, not questions | Rewrite step 7's last item |

## 🔗 Related workflows

- `tech-watch.md` — evaluating a technology, not a market
- `innovation-funding.md` — funding what this study selects
