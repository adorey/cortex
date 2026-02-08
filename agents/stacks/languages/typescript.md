# TypeScript — Best Practices

<!-- STACK REFERENCE
Fiche de best practices pour le langage TypeScript.
À combiner avec un rôle (ex: roles/lead-frontend.md) et un framework (ex: stacks/frameworks/nuxt.md).
Ne contient AUCUNE référence à un framework spécifique — uniquement le langage.
-->

> **Version de référence :** TypeScript 5.x | **Dernière mise à jour :** 2026-02
> **Docs officielles :** [typescriptlang.org](https://www.typescriptlang.org/docs/)

---

## 🏛️ Principes fondamentaux

### 1. Strict mode — non négociable

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

`strict: true` active : `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `noImplicitAny`, `noImplicitThis`, `alwaysStrict`.

### 2. Types — jamais `any`

```typescript
// ✅ Bien — types explicites
function calculateTotal(price: number, quantity: number): number {
  return price * quantity;
}

// ✅ Bien — types utilitaires
type PartialUser = Pick<User, 'id' | 'name'>;
type ReadonlyConfig = Readonly<Config>;

// ❌ Mal
function calculateTotal(price: any, quantity: any): any {
  return price * quantity;
}
```

**Règle :** `any` est interdit sauf dans les rares cas de compatibilité avec des libs non typées. Utiliser `unknown` si le type est inconnu.

### 3. `unknown` plutôt que `any`

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

// ❌ any = aucune vérification
function processInput(input: any): string {
  return input.toUpperCase(); // boom à runtime si ce n'est pas un string
}
```

### 4. Interfaces pour les contrats, types pour les compositions

```typescript
// ✅ Interface — contrat extensible
interface Repository<T> {
  findById(id: string): Promise<T | null>;
  save(entity: T): Promise<void>;
  delete(id: string): Promise<void>;
}

// ✅ Type — composition et unions
type Result<T> = { success: true; data: T } | { success: false; error: string };
type UserId = string & { readonly __brand: unique symbol };
```

### 5. Const assertions et satisfies

```typescript
// ✅ const assertion — types littéraux
const ROLES = ['admin', 'editor', 'viewer'] as const;
type Role = (typeof ROLES)[number]; // 'admin' | 'editor' | 'viewer'

// ✅ satisfies — typage + inférence
const config = {
  api: 'https://api.example.com',
  timeout: 5000,
  retries: 3,
} satisfies Record<string, string | number>;
// config.timeout est inféré comme number (pas string | number)
```

---

## 📐 Patterns recommandés

### Discriminated Unions

```typescript
// ✅ Pattern discriminant — exhaustif et type-safe
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
      render(response.data); // TS sait que data existe
      break;
    case 'error':
      showError(response.error); // TS sait que error existe
      break;
  }
}
```

### Branded Types

```typescript
// ✅ Types nominaux — pas de confusion entre IDs
type UserId = string & { readonly __brand: 'UserId' };
type OrderId = string & { readonly __brand: 'OrderId' };

function createUserId(id: string): UserId {
  return id as UserId;
}

function getUser(id: UserId): Promise<User> { /* ... */ }
// getUser(orderId) → erreur de compilation ✅
```

### Zod pour la validation runtime

```typescript
// ✅ Schéma de validation + inférence de type
import { z } from 'zod';

const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string().min(2).max(100),
  role: z.enum(['admin', 'editor', 'viewer']),
});

type User = z.infer<typeof UserSchema>;

// Parse en runtime — type-safe
const user = UserSchema.parse(unknownData);
```

### Error handling

```typescript
// ✅ Result type — pas d'exceptions pour le contrôle de flux
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

### Ne JAMAIS faire

```typescript
// ❌ any
const data: any = fetchData();

// ❌ Type assertion non vérifiée
const user = data as User; // dangereux sans validation

// ❌ Non-null assertion abuse
const name = user!.name!.first!; // cache des bugs

// ❌ Enum numérique (préférer les string unions ou const objects)
enum Direction { Up, Down, Left, Right }

// ❌ namespace (legacy)
namespace MyApp { /* ... */ }

// ❌ Exporter des types mutables
export let config = { /* ... */ }; // utilisez export const
```

### Préférer

| ❌ Ne pas | ✅ Préférer |
|---|---|
| `any` | `unknown` + type guards |
| `as Type` non vérifié | `satisfies` ou validation Zod |
| `!` non-null assertion | Optional chaining `?.` + nullish coalescing `??` |
| `enum` numérique | `as const` + type union |
| `namespace` | Modules ES |
| `var` | `const` (et `let` si mutation nécessaire) |
| `Function` type | Signature explicite `(arg: T) => R` |

---

## 🔧 Outillage recommandé

| Outil | Rôle |
|---|---|
| ESLint + typescript-eslint | Linting |
| Prettier | Formatage |
| Vitest / Jest | Tests |
| Zod | Validation runtime |
| tsx / ts-node | Exécution directe |
| tsc --noEmit | Vérification de types en CI |

---

## ✅ Checklist rapide

```
- [ ] strict: true dans tsconfig.json
- [ ] Zéro `any` (ou justifié + eslint-disable)
- [ ] unknown pour les données externes
- [ ] Interfaces pour les contrats, types pour les compositions
- [ ] Discriminated unions pour les états
- [ ] as const pour les valeurs littérales
- [ ] Validation runtime (Zod) aux frontières (API, forms)
- [ ] Pas de non-null assertion (!) sauf cas prouvé
- [ ] ESLint + Prettier configurés
- [ ] tsc --noEmit dans la CI
```
