# Workflow: Developing a new feature

<!-- GENERIC WORKFLOW — cortex
     Can be overridden by {project}/agents/workflows/feature-development.md
-->

## 🎯 Triggers

This workflow activates when the prompt contains formulations such as:
- "new feature", "new functionality", "new page", "new module"
- "develop", "implement", "create" + application component
- "functional need", "user story", "dev ticket"

## 👥 Agents involved

| Step | Role | Responsibility |
|---|---|---|
| 1 | `roles/engineering/architect.md` | Technical design & breakdown |
| 2 | `roles/engineering/lead-backend.md` and/or `roles/engineering/lead-frontend.md` | Implementation |
| 3 | `roles/engineering/qa-automation.md` | Test strategy |
| 4 | `roles/security-compliance/security-engineer.md` | Security review |
| 5 | `roles/communication/tech-writer.md` | Documentation |

## 📋 Steps

### Step 1 — Scoping & Design
**Agent:** `architect`
**Objective:** Understand the need, propose a technical solution consistent with the existing system.

**Checklist:**
- [ ] Understand the functional need (what, for whom, why)
- [ ] Identify the impact on the existing architecture
- [ ] Propose the breakdown into components/modules
- [ ] Identify external dependencies (APIs, third-party services, DB)
- [ ] Define interface contracts (API, events, DTOs)
- [ ] Roughly estimate complexity
- [ ] Validate the approach with the Product Owner if necessary

**Deliverable:** Validated technical proposal before any implementation.

---

### Step 2 — Implementation
**Agent:** `lead-backend` and/or `lead-frontend` depending on scope
**Objective:** Produce code according to the project stack standards.

**Checklist:**
- [ ] Follow the conventions defined in `capabilities/` and `project-context.md`
- [ ] Implement business logic
- [ ] Handle error cases and edge cases
- [ ] Write unit tests in parallel
- [ ] Follow SOLID / clean code principles
- [ ] Commit with clear, atomic messages
- [ ] Open a PR with a complete description

---

### Step 3 — Tests & QA
**Agent:** `qa-automation`
**Objective:** Define and validate the test strategy.

**Checklist:**
- [ ] Define test cases (nominal, boundaries, errors)
- [ ] Verify unit test coverage
- [ ] Plan the necessary integration tests
- [ ] Test regressions on affected modules
- [ ] Validate behaviour under degraded conditions

---

### Step 4 — Security review
**Agent:** `security-engineer`
**Objective:** Ensure no new attack surface is introduced.

**Checklist:**
- [ ] Verify input validation and sanitisation
- [ ] Check authorisations (authentication / authorisation)
- [ ] Verify absence of plaintext secrets (code, logs, API responses)
- [ ] Identify relevant OWASP risks for the feature
- [ ] Check added dependencies (known vulnerabilities)

---

### Step 5 — Documentation
**Agent:** `tech-writer`
**Objective:** Ensure the feature is documented and maintainable.

**Checklist:**
- [ ] Document exposed endpoints or interfaces
- [ ] Update the README or existing docs if necessary
- [ ] Document technical decisions (ADR if applicable)
- [ ] Verify that code comments are sufficient
- [ ] Update the changelog if the project has one

---

## ✅ Definition of done

- [ ] Code merged to the main branch
- [ ] Tests passing in CI
- [ ] Security review signed off
- [ ] Documentation up to date
- [ ] Product Owner has validated functionally

## 🔗 Related workflows

- `code-review.md` — can be triggered at step 2 (PR)
- `tech-watch.md` — if an unknown technology is introduced
