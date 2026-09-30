# Workflow: Innovation Funding

<!-- GENERIC WORKFLOW — cortex
     Jurisdiction-neutral by design: the instruments themselves live in a capability card
     (e.g. {workspace}/agents/capabilities/compliance/innovation-funding-{country}.md).
     Can be overridden by {workspace}/agents/workflows/intelligence/innovation-funding.md.
-->

## 🎯 Triggers

- "R&D tax credit", "innovation grant", "subsidy", "can we get funding for this"
- "are we eligible for X scheme", "what can we claim this year"
- "prepare the funding file", "the submission window closes on…"
- a diversification study concluding that an axis is not viable on own funds

## 👥 Agents involved

| Step | Role | Responsibility |
|---|---|---|
| 1 | `roles/product/innovation-funding-advisor.md` | Eligibility triage |
| 2 | `roles/engineering/architect.md` | State of the art and uncertainty at decision time |
| 3 | `roles/product/innovation-funding-advisor.md` | Instrument matching and combination modelling |
| 4 | `roles/data/data-analyst.md` | Evidence extraction from the tracker |
| 5 | `roles/communication/tech-writer.md` | Technical file |
| 6 | `roles/product/product-owner.md` | Arbitration and submission ownership |

## 📋 Steps

### Step 1 — Eligibility triage
**Agent:** `innovation-funding-advisor`
**Objective:** Two columns. Nothing else matters until they exist.

**Checklist:**
- [ ] Inventory the period's work from the tracker, not from memory
- [ ] Apply the uncertainty test to each item (see the role card)
- [ ] Write the ELIGIBLE column with the uncertainty in one sentence each
- [ ] Write the INELIGIBLE column with the reason (compliance / maintenance / integration / operations)
- [ ] Resist the temptation to widen. A narrow defensible file beats a broad indefensible one

---

### Step 2 — State of the art & uncertainty
**Agent:** `architect`
**Objective:** Reconstruct — or better, capture live — what was genuinely unknown.

**Checklist:**
- [ ] For each eligible item: what published solutions were reviewed, and why they did not apply
- [ ] What was not determinable in advance
- [ ] Which approaches were tried and failed — failures are evidence, not embarrassment
- [ ] Where this is recorded (decision records are the natural home)
- [ ] 🔁 **Process fix:** add a "state of the art & uncertainty" section to the decision-record template
      so the next file writes itself

---

### Step 3 — Instruments
**Agent:** `innovation-funding-advisor`
**Objective:** Match eligible work to schemes that actually apply to this company, here, this year.

**Checklist:**
- [ ] Load the jurisdiction capability card for the instruments themselves
- [ ] Verify rate, ceiling, expiry against a current source — never from memory
- [ ] Check territorial condition (many schemes require local establishment AND local spend)
- [ ] Check size/age conditions
- [ ] Model combination rules: grants typically reduce tax-credit bases
- [ ] Build the calendar of windows with the earliest hard deadline first

---

### Step 4 — Evidence
**Agent:** `data-analyst`
**Objective:** Check the claim against the records that actually exist.

**Checklist:**
- [ ] Extract time spent per eligible item from the tracker
- [ ] Verify granularity is defensible (who, when, on what)
- [ ] Identify gaps between the claim and the evidence — reduce the claim, not the standard
- [ ] Propose the tagging convention that makes next year's extraction automatic

---

### Step 5 — Technical file
**Agent:** `tech-writer`
**Objective:** A file that reads as true because it is.

**Checklist:**
- [ ] One section per eligible project: objective, state of the art, uncertainty, approach, results
- [ ] Include negative results
- [ ] Time and cost table traceable to the tracker
- [ ] Instruments claimed, with rates and computation
- [ ] Explicit statement of what was excluded and why (this paragraph is a defence asset)

---

### Step 6 — Arbitration & submission
**Agent:** `product-owner`
**Objective:** Decide and own.

**Checklist:**
- [ ] Choose the flagship project where a choice is required
- [ ] Name the owner and the deadline for each submission
- [ ] Decide whether external advisory support is needed
- [ ] Confirm the roadmap is not being distorted to fit a scheme

---

## ✅ Definition of done

- [ ] Eligible/ineligible split written and defensible item by item
- [ ] Every instrument cited with a verified current rate, ceiling and expiry
- [ ] Combination effects modelled net, not gross
- [ ] Evidence trail matched to records the team really keeps
- [ ] Submission calendar with named owners
- [ ] A process change adopted so next year's file is extracted, not reconstructed

## 🚩 Red flags

```
🚩 The claim covers most of the roadmap                     → triage was not applied
🚩 The state of the art was written after the work           → weak file, high audit risk
🚩 A scheme rate quoted without a dated source               → schemes change every year
🚩 Territorial condition unchecked                           → the most common disqualification
🚩 Roadmap reordered to fit a submission window              → the tail wagging the dog
🚩 An amount promised before eligibility is established      → never do this
```

## 🔗 Related workflows

- `market-study.md` — selecting what is worth funding in the first place
