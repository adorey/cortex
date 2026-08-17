# Workflow: Testing a frontend feature

<!-- GENERIC WORKFLOW — cortex
     Can be overridden by {project}/agents/workflows/engineering/frontend-testing.md
-->

## 🎯 Triggers

This workflow activates when the prompt contains formulations such as:
- "test the frontend", "cover this component/screen with tests", "component test", "front unit test"
- "E2E front", "Playwright", "browser test", "critical journey"
- "accessibility test", "a11y", "no coverage on the front", "frontend test pyramid / CI"

## 👥 Agents involved

| Step | Role | Responsibility |
|---|---|---|
| 1 | `roles/engineering/qa-automation.md` | Test strategy — place each check on the right rung |
| 2 | `roles/engineering/lead-frontend.md` | Component tests (states + a11y) |
| 3 | `roles/engineering/lead-frontend.md` | E2E critical journey (browser) |
| 4 | `roles/engineering/platform-engineer.md` + `qa-automation` | CI wiring (dedicated jobs) |
| 5 | `roles/engineering/qa-automation.md` | Verify the tests can fail for the right reason |

**Capabilities:** `testing/component-testing.md`, `testing/e2e-testing.md`, `frameworks/{project vue/react/…}.md`, `languages/typescript.md`.

## 📋 Steps

### Step 1 — Place each check on the pyramid
**Agent:** `qa-automation`
**Objective:** Decide, per feature, what belongs where — so E2E stays a handful of journeys, not a dumping ground.

**Checklist:**
- [ ] Pure logic (formatters, composables, store mutations) → **unit**
- [ ] A component's render + interaction + states → **component test**
- [ ] A user path across screens hitting the real app → **E2E** (only the critical few)
- [ ] Accessibility asserted at the component rung (axe), not deferred to E2E
- [ ] Regression: every fixed UI bug gets a test that fails before the fix

**Deliverable:** A one-paragraph test plan naming the specs to write and their rung.

### Step 2 — Component tests (states + a11y)
**Agent:** `lead-frontend` · **Load:** `testing/component-testing.md` + the project `frameworks/` card

**Checklist:**
- [ ] Mount in isolation; query by role/label (accessibility tree), interact via user events
- [ ] Cover empty / loading / error / success / edges (long text, 0-many, disabled)
- [ ] Mock the network at the boundary (MSW) — assert loading→success AND loading→error
- [ ] One `axe` assertion on the mounted component
- [ ] No assertion on CSS classes or component internals

**Deliverable:** Component specs, green, that fail if the component's behavior regresses.

### Step 3 — E2E critical journey (browser)
**Agent:** `lead-frontend` · **Load:** `testing/e2e-testing.md` (§Browser/UI E2E)

**Checklist:**
- [ ] The journey is genuinely critical (auth, the money path, the destructive action)
- [ ] Selectors by role/label; page object behind the spec; no selector soup
- [ ] Authenticate once via a `setup` project, reuse the storage state
- [ ] Deterministic waits (app-ready signals), trace + screenshot on retry
- [ ] Lives in the app repo's E2E dir, co-located with the screens

**Deliverable:** One green E2E journey + the reusable page-object/fixture foundation.

### Step 4 — Wire into CI
**Agent:** `platform-engineer` + `qa-automation`

**Checklist:**
- [ ] Unit + component tests gate every PR (fast, deterministic)
- [ ] Browser E2E in its **own** job (slower/flakier) — nightly or gating once stable, never silently disabled
- [ ] Coverage reported; `--passWithNoTests`-style green-on-empty removed
- [ ] The runner env is real (jsdom/happy-dom for components; built app for E2E)

**Deliverable:** CI runs the pyramid; the E2E job is visible and enable-able.

### Step 5 — Can it fail for the right reason?
**Agent:** `qa-automation` (see the role's *"A test can pass for the wrong reason"*)

**Checklist:**
- [ ] Each new test was seen to **fail** against the unfixed/naive code
- [ ] Negative assertions paired with a positive control
- [ ] Where a broken and a working render look identical, the test asserts on the mechanism

**Deliverable:** Confidence the suite is worth more than its green.

## 🔁 When to suggest creating an overlay

If the project's runner/mock/CI specifics recur (e.g. Jest vs Vitest, MSW vs a passthrough mock, a
particular E2E dir + auth setup), capture them in `{project}/agents/capabilities/testing/*` and
`{project}/agents/workflows/engineering/frontend-testing.md` rather than repeating them each time.
