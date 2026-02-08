# PHP — Best Practices

<!-- STACK REFERENCE
Fiche de best practices pour le langage PHP.
À combiner avec un rôle (ex: roles/lead-backend.md) et un framework (ex: stacks/frameworks/symfony.md).
Ne contient AUCUNE référence à un framework spécifique — uniquement le langage.
-->

> **Version de référence :** PHP 8.2+ | **Dernière mise à jour :** 2026-02
> **Docs officielles :** [php.net](https://www.php.net/docs.php) | **Standards :** [PHP-FIG](https://www.php-fig.org/)

---

## 🏛️ Principes fondamentaux

### 1. Typage strict — toujours

```php
<?php

declare(strict_types=1);
```

Chaque fichier PHP commence par `declare(strict_types=1)`. Pas d'exception. Pas de "juste pour ce fichier". **Toujours.**

- Typer tous les paramètres, retours et propriétés
- Utiliser les union types (`string|int`) plutôt que `mixed`
- Utiliser `mixed` uniquement quand c'est réellement nécessaire
- Préférer les enums PHP 8.1+ aux constantes pour les valeurs finies

```php
// ✅ Bien
function calculateTotal(float $price, int $quantity): float
{
    return $price * $quantity;
}

// ❌ Mal
function calculateTotal($price, $quantity)
{
    return $price * $quantity;
}
```

### 2. Standards PSR

| PSR | Sujet | Statut |
|---|---|---|
| PSR-1 | Basic Coding Standard | Obligatoire |
| PSR-4 | Autoloading | Obligatoire |
| PSR-12 | Extended Coding Standard (ou PER-CS 2.0) | Obligatoire |
| PSR-3 | Logger Interface | Recommandé |
| PSR-7 | HTTP Message Interface | Selon besoin |
| PSR-11 | Container Interface | Recommandé |

### 3. Readonly par défaut

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

**Règle :** Si une propriété n'a pas besoin d'être modifiée après construction, elle est `readonly`.

### 4. Enums plutôt que constantes

```php
// ✅ Bien — Enum (PHP 8.1+)
enum Status: string
{
    case Active = 'active';
    case Inactive = 'inactive';
    case Suspended = 'suspended';
}

// ❌ Mal — Constantes en vrac
class Status
{
    const ACTIVE = 'active';
    const INACTIVE = 'inactive';
    const SUSPENDED = 'suspended';
}
```

### 5. Named arguments pour la lisibilité

```php
// ✅ Lisible
$response = new JsonResponse(
    data: $result,
    status: Response::HTTP_CREATED,
    headers: ['X-Custom' => 'value'],
);

// ❌ Obscur
$response = new JsonResponse($result, 201, ['X-Custom' => 'value']);
```

---

## 📐 Patterns recommandés

### Architecture

- **Injection de dépendances** : toujours injecter via le constructeur, jamais `new` dans le code métier
- **Single Responsibility** : une classe = une responsabilité = une raison de changer
- **Value Objects** : encapsuler les concepts métier (`Money`, `Email`, `DateRange`)
- **Final par défaut** : déclarer les classes `final` sauf besoin explicite d'héritage
- **Composition over inheritance** : préférer l'injection à l'héritage

```php
// ✅ Injection de dépendances
final class OrderService
{
    public function __construct(
        private readonly OrderRepository $orderRepository,
        private readonly PaymentGateway $paymentGateway,
        private readonly EventDispatcher $eventDispatcher,
    ) {}
}

// ❌ Instanciation manuelle
class OrderService
{
    public function process(): void
    {
        $repo = new OrderRepository();  // couplage fort
        $gateway = new StripeGateway();  // impossible à tester
    }
}
```

### Gestion d'erreurs

```php
// ✅ Exceptions métier typées
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

// ❌ Exceptions génériques
throw new \Exception('Not enough money');
```

### Collections typées

```php
// ✅ Collection typée (PHP 8.2+)
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
    Status::Active => 'Actif',
    Status::Inactive => 'Inactif',
    Status::Suspended => 'Suspendu',
};
```

---

## 🚫 Anti-patterns

### Ne JAMAIS faire

```php
// ❌ Variables dynamiques
$$varName = 'value';

// ❌ @ error suppression
$value = @file_get_contents($path);

// ❌ eval()
eval($userInput);  // faille de sécurité critique

// ❌ extract()
extract($_POST);   // injection de variables

// ❌ Concaténation SQL
$query = "SELECT * FROM users WHERE id = " . $id;

// ❌ echo/die pour le debug
echo "DEBUG: " . $variable;
die('something went wrong');

// ❌ static abuse
class UserService
{
    public static function find(int $id): User { /* ... */ }
}
// Impossible à tester, impossible à mocker
```

### Préférer

| ❌ Ne pas | ✅ Préférer |
|---|---|
| `array` pour tout | Value Objects, DTOs, Collections typées |
| `static` methods | Injection de dépendances |
| `isset()` partout | Null coalescing `??`, nullsafe `?->` |
| `switch` long | `match` expression |
| Héritage profond | Composition + interfaces |
| `new` dans le code métier | Constructor injection |
| `@suppress` | Gestion d'exceptions propre |

---

## 🔧 Outillage recommandé

| Outil | Rôle |
|---|---|
| PHPStan / Psalm | Analyse statique (level max) |
| PHP CS Fixer / PHP_CodeSniffer | Formatage PSR-12 / PER |
| PHPUnit | Tests unitaires et intégration |
| Rector | Refactoring automatisé, montée de version |
| Composer | Gestion des dépendances |
| Xdebug / pcov | Coverage et debugging |

---

## ✅ Checklist rapide

```
- [ ] declare(strict_types=1) en haut de chaque fichier
- [ ] Tous les paramètres/retours/propriétés typés
- [ ] Classes final par défaut
- [ ] Readonly properties/classes quand possible
- [ ] Enums pour les valeurs finies
- [ ] Injection de dépendances (pas de new dans le métier)
- [ ] Exceptions métier typées (pas de \Exception générique)
- [ ] Pas de static sauf constantes/factories
- [ ] PHPStan level 8+ (ou max)
- [ ] PSR-12 / PER-CS respecté
```
