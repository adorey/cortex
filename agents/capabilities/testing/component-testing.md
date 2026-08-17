# Component testing — Best Practices

> Framework-agnostic. For the concrete runner + mount API of a given stack, load the matching
> `frameworks/` card (e.g. `frameworks/vue.md`) and the project's `languages/typescript.md`.

A **component test** mounts a single UI component in isolation, drives it the way a user would, and
asserts on what the user perceives. It is the middle rung of the pyramid: many more than E2E, far cheaper
and faster, and — unlike a unit test — it renders real DOM and real interaction. It answers one question:
*does this component render correctly and react correctly to input, across all its states?*

## 🎯 What a component test is for

Not "assert the component called `this.save()`". Mount it, act like a user (type, click, tab), and assert
on the **rendered output** and **emitted effects**. Push pure logic *down* to unit tests and full journeys
*up* to E2E; the component test owns the rung in between — the props → render → interaction → output loop
of one component.

## 📐 Core principles

### 1. Test behavior, not implementation

Query the **accessibility tree** (by role, label, text) — the way a user and a screen reader find things —
not internal CSS classes, `data-*` hooks, component instances, or private state. Interact via **user
events** (click, type, keyboard), not by calling methods or setting state directly. Assert on what the
user sees or what the component emits. A test coupled to markup or internals breaks on every refactor and
proves nothing about behavior.

### 2. Cover the states, not just the happy path

A component is its set of states. Test **empty, loading, error, success, and the edges** (very long text,
missing optional data, zero/many items, disabled/readonly). The happy-path-only test is the one that ships
the broken error state. One state = one focused test.

### 3. Mock at the boundary, keep the component real

Stub the **outermost edge** — the network (HTTP), the clock, randomness, storage — and let everything
inside the component run for real. Prefer a **network-level mock** (intercept requests) over hand-injected
fakes: it exercises the real data-fetching path and survives refactors. Don't mock the component's own
children unless they're genuinely heavy/external — over-mocking tests the mocks, not the component.

### 4. Isolation and determinism

Each test **mounts fresh** and shares nothing with its neighbors. Freeze time (fake timers), seed any
randomness, and forbid real network — a component test that depends on a live backend or on run order is
an E2E in disguise and will flake. Reset the DOM and any global store between tests.

### 5. Accessibility is an assertion, not an afterthought

Querying by role already forces the component to be accessible (no role → no query → failing test). Go one
step further: run an **a11y assertion** (axe or equivalent) on the mounted component so contrast, labels,
and ARIA regress loudly. A11y tested at the component rung is cheap; tested only in E2E it's slow and late.

### 6. Assert the mechanism when the output looks identical

When a working and a broken component render the *same* DOM (e.g. a disabled submit that looks enabled),
assert on the **mechanism** — the emitted event, the disabled attribute, the request that did or didn't
fire — not on the visual shape. This is the component-rung form of *"a test can pass for the wrong reason"*
(see the `qa-automation` role card).

## ✅ Checklist

```
- [ ] Mounted in isolation; network/clock/randomness stubbed at the boundary
- [ ] Queried by role/label/text (accessibility tree), not CSS/data-hooks/internals
- [ ] Interacted via user events, not by calling methods or setting state
- [ ] States covered: empty, loading, error, success, edges (long text, 0/many, disabled)
- [ ] An a11y assertion (axe) on the mounted component
- [ ] Each test mounts fresh, deterministic, independent of run order
- [ ] Asserts on the mechanism where a broken and a working render look identical
- [ ] Heavy/external children mocked; the component's own logic left real
```

## 🔗 Interactions

- **QA Automation** → owns the pyramid; this card is its middle rung, between unit and `e2e-testing`.
- **Lead Frontend / framework card** → the concrete mount/query/user-event API and the network-mock tool
  live in the stack's `frameworks/` capability.
- **Security Engineer** → component tests are where input-validation and escaping/XSS-at-render are exercised.
