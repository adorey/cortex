# PHP — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for the PHP language.
To combine with a role (e.g. roles/engineering/lead-backend.md) and a framework (e.g. capabilities/frameworks/symfony.md).
Contains NO framework-specific references — language only.
-->

> **Reference version:** PHP 8.2+ | **Last updated:** 2026-02
> **Official docs:** [php.net](https://www.php.net/docs.php) | **Standards:** [PHP-FIG](https://www.php-fig.org/)

---

## 🏛️ Fundamental principles

### 1. Strict typing — always

```php
<?php

declare(strict_types=1);
```

Every PHP file starts with `declare(strict_types=1)`. No exceptions. Not "just for this file". **Always.**

- Type all parameters, return values and properties
- Use union types (`string|int`) rather than `mixed`
- Use `mixed` only when genuinely necessary
- Prefer PHP 8.1+ enums over constants for finite values

```php
// ✅ Good
function calculateTotal(float $price, int $quantity): float
{
    return $price * $quantity;
}

// ❌ Bad
function calculateTotal($price, $quantity)
{
    return $price * $quantity;
}
```

### 2. PSR standards

| PSR | Subject | Status |
|---|---|---|
| PSR-1 | Basic Coding Standard | Mandatory |
| PSR-4 | Autoloading | Mandatory |
| PSR-12 | Extended Coding Standard (or PER-CS 2.0) | Mandatory |
| PSR-3 | Logger Interface | Recommended |
| PSR-7 | HTTP Message Interface | As needed |
| PSR-11 | Container Interface | Recommended |

### 3. Readonly by default

```php
// ✅ PHP 8.2+ — Readonly classes
final readonly class Money
{
    public function __construct(
        public int $amount,
        public string $currency,
    ) {}
}

// ✅ PHP 8.1+ — Readonly properties
final class User
{
    public function __construct(
        public readonly string $email,
        public readonly string $name,
    ) {}
}
```

**Rule:** If a property does not need to be modified after construction, it is `readonly`.

### 4. Enums rather than constants

```php
// ✅ Good — Enum (PHP 8.1+)
enum Status: string
{
    case Active = 'active';
    case Inactive = 'inactive';
    case Suspended = 'suspended';
}

// ❌ Bad — Scattered constants
class Status
{
    const ACTIVE = 'active';
    const INACTIVE = 'inactive';
    const SUSPENDED = 'suspended';
}
```

### 5. Named arguments for readability

```php
// ✅ Readable
$response = new JsonResponse(
    data: $result,
    status: Response::HTTP_CREATED,
    headers: ['X-Custom' => 'value'],
);

// ❌ Obscure
$response = new JsonResponse($result, 201, ['X-Custom' => 'value']);
```

---

## 📐 Recommended patterns

### Architecture

- **Dependency injection**: always inject via the constructor, never `new` in business code
- **Single Responsibility**: one class = one responsibility = one reason to change
- **Value Objects**: encapsulate business concepts (`Money`, `Email`, `DateRange`)
- **Final by default**: declare classes `final` unless explicit inheritance is needed
- **Composition over inheritance**: prefer injection to inheritance

```php
// ✅ Dependency injection
final class OrderService
{
    public function __construct(
        private readonly OrderRepository $orderRepository,
        private readonly PaymentGateway $paymentGateway,
        private readonly EventDispatcher $eventDispatcher,
    ) {}
}

// ❌ Manual instantiation
class OrderService
{
    public function process(): void
    {
        $repo = new OrderRepository();  // tight coupling
        $gateway = new StripeGateway();  // impossible to test
    }
}
```

### Error handling

```php
// ✅ Typed domain exceptions
final class InsufficientFundsException extends \DomainException
{
    public static function forAmount(Money $requested, Money $available): self
    {
        return new self(sprintf(
            'Insufficient funds: requested %s, available %s',
            $requested,
            $available,
        ));
    }
}

// ❌ Generic exceptions
throw new \Exception('Not enough money');
```

### Typed collections

```php
// ✅ Typed collection (PHP 8.2+)
/** @template T */
final readonly class Collection
{
    /** @param list<T> $items */
    public function __construct(
        private array $items,
    ) {}

    /** @return T|null */
    public function first(): mixed
    {
        return $this->items[0] ?? null;
    }
}
```

### Null safety

```php
// ✅ Nullsafe operator (PHP 8.0+)
$country = $user?->getAddress()?->getCountry()?->getCode();

// ✅ Match expression (PHP 8.0+)
$label = match($status) {
    Status::Active => 'Active',
    Status::Inactive => 'Inactive',
    Status::Suspended => 'Suspended',
};
```

---

## 🚫 Anti-patterns

### NEVER do this

```php
// ❌ Variable variables
$$varName = 'value';

// ❌ @ error suppression
$value = @file_get_contents($path);

// ❌ eval()
eval($userInput);  // critical security flaw

// ❌ extract()
extract($_POST);   // variable injection

// ❌ SQL concatenation
$query = "SELECT * FROM users WHERE id = " . $id;

// ❌ echo/die for debugging
echo "DEBUG: " . $variable;
die('something went wrong');

// ❌ static abuse
class UserService
{
    public static function find(int $id): User { /* ... */ }
}
// Impossible to test, impossible to mock
```

### Prefer

| ❌ Avoid | ✅ Prefer |
|---|---|
| `array` for everything | Value Objects, DTOs, typed collections |
| `static` methods | Dependency injection |
| `isset()` everywhere | Null coalescing `??`, nullsafe `?->` |
| long `switch` | `match` expression |
| Deep inheritance | Composition + interfaces |
| `new` in business code | Constructor injection |
| `@suppress` | Proper exception handling |

---

## 🔧 Recommended tooling

| Tool | Role |
|---|---|
| PHPStan / Psalm | Static analysis (max level) |
| PHP CS Fixer / PHP_CodeSniffer | PSR-12 / PER formatting |
| PHPUnit | Unit and integration tests |
| Rector | Automated refactoring, version upgrades |
| Composer | Dependency management |
| Xdebug / pcov | Coverage and debugging |

---

## ✅ Quick checklist

```
- [ ] declare(strict_types=1) at the top of every file
- [ ] All parameters/return values/properties typed
- [ ] Classes final by default
- [ ] Readonly properties/classes where possible
- [ ] Enums for finite values
- [ ] Dependency injection (no new in business code)
- [ ] Typed domain exceptions (no generic \Exception)
- [ ] No static except constants/factories
- [ ] PHPStan level 8+ (or max)
- [ ] PSR-12 / PER-CS respected
```
