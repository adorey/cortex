# TypeScript — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for the TypeScript language.
To combine with a role (e.g. roles/engineering/lead-frontend.md) and a framework (e.g. capabilities/frameworks/nuxt.md).
Contains NO framework-specific references — language only.
-->

> **Reference version:** TypeScript 5.x | **Last updated:** 2026-02
> **Official docs:** [typescriptlang.org](https://www.typescriptlang.org/docs/)

---

## 🏛️ Fundamental principles

### 1. Strict mode — non-negotiable

```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true
  }
}
```

`strict: true` enables: `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `noImplicitAny`, `noImplicitThis`, `alwaysStrict`.

### 2. Types — never `any`

```typescript
// ✅ Good — explicit types
function calculateTotal(price: number, quantity: number): number {
  return price * quantity;
}

// ✅ Good — utility types
type PartialUser = Pick<User, 'id' | 'name'>;
type ReadonlyConfig = Readonly<Config>;

// ❌ Bad
function calculateTotal(price: any, quantity: any): any {
  return price * quantity;
}
```

**Rule:** `any` is forbidden except in rare compatibility cases with untyped libraries. Use `unknown` when the type is not known.

### 3. `unknown` rather than `any`

```typescript
// ✅ unknown + type guard
function processInput(input: unknown): string {
  if (typeof input === 'string') {
    return input.toUpperCase();
  }
  if (input instanceof Error) {
    return input.message;
  }
  return String(input);
}

// ❌ any = no checking
function processInput(input: any): string {
  return input.toUpperCase(); // runtime crash if not a string
}
```

### 4. Interfaces for contracts, types for compositions

```typescript
// ✅ Interface — extensible contract
interface Repository<T> {
  findById(id: string): Promise<T | null>;
  save(entity: T): Promise<void>;
  delete(id: string): Promise<void>;
}

// ✅ Type — composition and unions
type Result<T> = { success: true; data: T } | { success: false; error: string };
type UserId = string & { readonly __brand: unique symbol };
```

### 5. Const assertions and satisfies

```typescript
// ✅ const assertion — literal types
const ROLES = ['admin', 'editor', 'viewer'] as const;
type Role = (typeof ROLES)[number]; // 'admin' | 'editor' | 'viewer'

// ✅ satisfies — typing + inference
const config = {
  api: 'https://api.example.com',
  timeout: 5000,
  retries: 3,
} satisfies Record<string, string | number>;
// config.timeout is inferred as number (not string | number)
```

---

## 📐 Recommended patterns

### Discriminated Unions

```typescript
// ✅ Discriminant pattern — exhaustive and type-safe
type ApiResponse<T> =
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string };

function handleResponse<T>(response: ApiResponse<T>): void {
  switch (response.status) {
    case 'loading':
      showSpinner();
      break;
    case 'success':
      render(response.data); // TS knows data exists
      break;
    case 'error':
      showError(response.error); // TS knows error exists
      break;
  }
}
```

### Branded Types

```typescript
// ✅ Nominal types — no confusion between IDs
type UserId = string & { readonly __brand: 'UserId' };
type OrderId = string & { readonly __brand: 'OrderId' };

function createUserId(id: string): UserId {
  return id as UserId;
}

function getUser(id: UserId): Promise<User> { /* ... */ }
// getUser(orderId) → compilation error ✅
```

### Zod for runtime validation

```typescript
// ✅ Validation schema + type inference
import { z } from 'zod';

const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string().min(2).max(100),
  role: z.enum(['admin', 'editor', 'viewer']),
});

type User = z.infer<typeof UserSchema>;

// Parse at runtime — type-safe
const user = UserSchema.parse(unknownData);
```

### Error handling

```typescript
// ✅ Result type — no exceptions for control flow
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };

function divide(a: number, b: number): Result<number, string> {
  if (b === 0) return { ok: false, error: 'Division by zero' };
  return { ok: true, value: a / b };
}
```

---

## 🚫 Anti-patterns

### NEVER do this

```typescript
// ❌ any
const data: any = fetchData();

// ❌ Unchecked type assertion
const user = data as User; // dangerous without validation

// ❌ Non-null assertion abuse
const name = user!.name!.first!; // hides bugs

// ❌ Numeric enum (prefer string unions or const objects)
enum Direction { Up, Down, Left, Right }

// ❌ namespace (legacy)
namespace MyApp { /* ... */ }

// ❌ Exporting mutable types
export let config = { /* ... */ }; // use export const
```

### Prefer

| ❌ Avoid | ✅ Prefer |
|---|---|
| `any` | `unknown` + type guards |
| Unchecked `as Type` | `satisfies` or Zod validation |
| `!` non-null assertion | Optional chaining `?.` + nullish coalescing `??` |
| Numeric `enum` | `as const` + type union |
| `namespace` | ES modules |
| `var` | `const` (and `let` if mutation is needed) |
| `Function` type | Explicit signature `(arg: T) => R` |

---

## 🔧 Recommended tooling

| Tool | Role |
|---|---|
| ESLint + typescript-eslint | Linting |
| Prettier | Formatting |
| Vitest / Jest | Tests |
| Zod | Runtime validation |
| tsx / ts-node | Direct execution |
| tsc --noEmit | Type checking in CI |

---

## ✅ Quick checklist

```
- [ ] strict: true in tsconfig.json
- [ ] Zero `any` (or justified + eslint-disable)
- [ ] unknown for external data
- [ ] Interfaces for contracts, types for compositions
- [ ] Discriminated unions for states
- [ ] as const for literal values
- [ ] Runtime validation (Zod) at boundaries (API, forms)
- [ ] No non-null assertion (!) unless proven
- [ ] ESLint + Prettier configured
- [ ] tsc --noEmit in CI
```
