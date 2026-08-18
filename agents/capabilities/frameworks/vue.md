# Vue — Best Practices

> Covers Vue 2 (2.7+) and Vue 3, and Nuxt on top. Version-specific tooling differs (see **Testing** and
> **Migration**); the principles don't. Load with `languages/typescript.md` and, for tests,
> `testing/component-testing.md` + `testing/e2e-testing.md`.

## 🏛️ Fundamental principles

### 1. Composition API as the default

Prefer `<script setup>` / the Composition API — it's available in **both** Vue 2.7+ and Vue 3, types far
better than the Options API, and is the forward-compatible surface. Reserve the Options API for legacy
files you're not touching. This choice is also the cheapest insurance for a Vue 2 → 3 migration (below).

### 2. Single-File Components, thin and typed

One component = one responsibility. **Typed props** (with defaults), **events up / props down** — a child
never mutates a prop, it `emit`s. Extract shared reactive logic into **composables** (`useX()`), not
mixins (mixins hide origins and collide; a Vue 2 relic).

### 3. State: store for shared, local for the rest

Component-local state stays in the component. Cross-view state goes to a **store — Pinia** (the standard
for Vue 3, and available for Vue 2; Vuex is legacy, keep only where it already lives). Keep stores small
and typed; don't push transient UI state into the global store.

### 4. Reactivity hygiene

`ref`/`reactive` at the boundaries, `computed` for derived values (never a method that recomputes on every
render), `watch`/`watchEffect` sparingly and with explicit sources. Don't destructure a `reactive` (it
loses reactivity) — use `toRefs`.

### 5. Fetching + boundaries

Validate data **at the boundary** (API responses, form input) — a typed interface is a claim, not a
guarantee (pair with runtime validation, e.g. Zod). Render loading/error/empty as first-class states, not
afterthoughts (the component test in §Testing asserts each one).

## 🧪 Testing

The framework-agnostic craft is in `testing/component-testing.md` + `testing/e2e-testing.md`; here's how it
lands in Vue.

### Component tests — mount, query by role, drive as a user

- **Runner**: **Vitest** on Vue 3 (fast, ESM, Vite-native). **Jest + `vue-jest`** on Vue 2 (Vitest needs
  Vite; a webpack/Nuxt-2 app usually stays on Jest until the migration). Same test *shape* either way.
- **Mount**: `@vue/test-utils` (`mount`), ideally behind **`@testing-library/vue`** so you query the
  accessibility tree (`getByRole`, `getByLabelText`) and interact via `@testing-library/user-event` —
  behavior, not internals.
- **Network**: mock at the boundary with **MSW** (intercepts `fetch`/XHR) — not by stubbing the store.
  Assert loading → success **and** loading → error.
- **A11y**: `axe` (e.g. `vitest-axe`/`jest-axe`) on the mounted component.
- **DOM env**: `jsdom` or `happy-dom` as the test environment.

```ts
// Vue 3 + Vitest + Testing Library — behavior, states, a11y
import { render, screen } from "@testing-library/vue"
import userEvent from "@testing-library/user-event"
import InvoiceRow from "@/components/InvoiceRow.vue"

test("emits `select` when the row is activated", async () => {
  const { emitted } = render(InvoiceRow, { props: { invoice: fixture } })
  await userEvent.click(screen.getByRole("button", { name: /select/i }))
  expect(emitted().select).toHaveLength(1)
})
```

### E2E — real browser

Playwright driving the built app; principles in `testing/e2e-testing.md` (role-based selectors, auth via
saved storage state, network determinism). Keep E2E for critical journeys; let component tests own the
per-component states.

## 🧭 Migration Vue 2 → Vue 3 (and Nuxt 2 → 3)

- **Write forward-compatible today**: Composition API + `<script setup>`, `emits` declarations, no filters,
  no `.sync` (use `v-model` args), no global event bus, no mixins. These are the pieces that *don't* port.
- **Nuxt bridge** is the stepping stone (Composition API + Nuxt 3 APIs on a Nuxt 2 app) — new code should
  use the bridge-provided composables so it survives the jump.
- **Tooling flips with the version**: Vue 2/webpack → Jest; Vue 3/Vite → Vitest. Written against Testing
  Library + MSW, the *tests* survive the runner swap; the config doesn't.

## 🚫 Anti-patterns

```
❌ Mixins for shared logic (use composables) · global event bus (use props/emit or a store)
❌ Mutating a prop in a child · destructuring a `reactive` (breaks reactivity)
❌ Method calls where a `computed` belongs · unbounded `watch` on whole objects
❌ Options-API-only patterns in new code (filters, `.sync`) — they don't port to Vue 3
❌ Business logic in components (extract to composables/services) · fat global store for local UI state
❌ Tests asserting on CSS classes / component internals instead of the accessibility tree
```

## ✅ Quick checklist

```
- [ ] Composition API / <script setup>, typed props with defaults, events up / props down
- [ ] Shared logic in composables (not mixins); cross-view state in a typed store (Pinia)
- [ ] computed for derived values; no reactive destructuring; watch sources explicit
- [ ] loading/error/empty rendered as first-class states
- [ ] Component tests: Vitest (v3) / Jest+vue-jest (v2), Testing Library + user-event, MSW at the boundary, axe
- [ ] E2E (Playwright) for critical journeys only — see testing/e2e-testing.md
- [ ] New code forward-compatible for Vue 3 (no filters/.sync/mixins/event bus)
```
