# End-to-end testing — Best Practices

> Framework-agnostic. For the concrete test-runner mechanics of a given stack, load the matching
> `frameworks/` card (e.g. `frameworks/symfony.md` → *End-to-end & functional testing*).

An **end-to-end (E2E) test** drives a real slice of the system through its actual wiring — the same
entry point, the same dispatch, the same persistence a request would hit — and asserts on the real
artifacts it produces. It is the top of the pyramid: few, deliberate, and each one earns its keep.

## 🎯 What an E2E test is for here

Not "click the whole UI". An E2E test **proves a critical path is wired correctly across layers** — the
seams unit tests mock away are exactly the ones it exercises. Reach for one when the value is in the
integration itself: a pipeline, a dispatch chain, a document produced and archived, a conformity
guarantee that only holds if every stage agrees.

## 📐 Core principles

### 1. One investment, two uses — smoke and CI regression gate

A real E2E is expensive to build once and cheap to keep. Written well, the same test is both the
**smoke test** you run by hand to prove a new pipeline works, and the **CI regression gate** that fails
the day someone breaks it. Design it to serve both from the start: no manual setup, no external service,
runnable headless.

### 2. The fixture is the reusable asset

The hard part of an E2E is standing up a **coherent domain graph** — the entities, their relations, the
one field three stages downstream will read. Build it once, behind a **parameterised factory**, and every
later test composes from it instead of copy-pasting. A good fixture factory is worth more than the test
it first served; treat it as first-class, deliberate infrastructure — not scaffolding.

### 3. Isolation without teardown cost

Each test must be independent of every other and of run order. The cheap, reliable way: run each test in
a **transaction rolled back at the end** — no data survives, no teardown script drifts. For parallel
runners, give **each worker its own database** so they never contend. Isolation is a property you design
in, not a cleanup you bolt on.

### 4. Exercise the real dispatch, not a mocked seam

The point is the wiring, so run the **actual pipeline in-process**: a synchronous transport that runs the
whole handler chain inline, or the real handler invoked directly — not a test double standing in for the
thing under test. If you mock the dispatch, you've tested your mock.

### 5. Assert conformity, not presence

*"A row exists" / "a file was produced" is the weakest possible assertion* — a broken pipeline that emits
garbage passes it. Assert the artifact is **correct**: schema-valid against its contract, business-valid
against its rules, byte-for-byte where it matters. When a broken and a working path yield the same
*shape*, assert on the **mechanism** (the validated content, the generated query) rather than the shape.
This is the E2E face of *"a test can pass for the wrong reason"* (see the `qa-automation` role card).

### 6. Environment parity — the test env is a real environment

E2E tests fail in ways unit tests can't because they touch real config: encryption keys, connection
strings, feature flags. Two recurring traps:

- **A real environment variable overrides your dotfiles and your secrets vault.** An empty exported var
  silently wins over the value you carefully put in a test env file. Pin **deterministic, non-sensitive**
  test secrets **in the test runner itself** (the CI target / test command), where they beat the ambient
  environment — not only in a file the environment can shadow.
- **Wiring that only exists at runtime isn't checked by the type-checker.** A mapping, a service tag, a
  registered path can be absent and static analysis stays green; the E2E is often the *first* thing to
  execute that path. When an E2E surfaces such a gap, the fix belongs in the **runtime config**, and the
  E2E is what will keep it fixed.

## ✅ Checklist

```
- [ ] Runs headless, no manual setup, no external service — usable as smoke AND in CI
- [ ] Domain graph built via a parameterised factory, not copy-pasted per test
- [ ] Isolated: transactional rollback (or equivalent), independent of run order
- [ ] Parallel-safe: each worker owns its database / namespace
- [ ] Drives the real dispatch in-process (sync transport / direct handler), nothing mocked at the seam under test
- [ ] Asserts correctness (schema-/business-valid), not mere existence of the artifact
- [ ] Pairs every "absent" assertion with a positive control (own data present, and strictly smaller)
- [ ] Deterministic test secrets pinned in the runner, immune to a shadowing real env var
- [ ] A runtime-only gap it surfaced is fixed in config, with the E2E as the regression guard
```

## 🔗 Interactions

- **QA Automation** → owns the strategy; this card is the E2E rung of its pyramid.
- **Lead Backend / framework card** → the concrete runner mechanics (transport, transactional bundle,
  parallel runner, fixture facade) live in the `frameworks/` capability for the stack.
- **Security Engineer** → E2E is where auth/tenant-isolation paths are exercised for real.
