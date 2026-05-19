# Symfony — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for the Symfony framework.
To combine with capabilities/languages/php.md for general PHP best practices.
-->

> **Reference version:** Symfony 7.x (LTS: 6.4) | **Last updated:** 2026-02
> **Official docs:** [symfony.com/doc](https://symfony.com/doc/current/index.html) | [Best Practices](https://symfony.com/doc/current/best_practices.html)

---

## 🏛️ Fundamental principles

### 1. Bundle-less structure

Since v4, Symfony recommends **not creating bundles** for application code.

```
src/
├── Controller/
├── Entity/
├── Repository/
├── Service/
├── EventListener/
├── Command/
├── DTO/
├── ValueObject/
└── Kernel.php
```

For large projects, prefer organising by **business domain**:

```
src/
├── Order/
│   ├── Controller/
│   ├── Entity/
│   ├── Repository/
│   ├── Service/
│   └── Event/
├── User/
│   ├── Controller/
│   ├── Entity/
│   └── ...
└── Shared/
    ├── EventListener/
    └── Service/
```

### 2. Thin controllers

```php
// ✅ Thin controller — delegates to service
#[Route('/api/orders', name: 'order_')]
final class OrderController extends AbstractController
{
    #[Route('', methods: ['POST'])]
    public function create(
        #[MapRequestPayload] CreateOrderDTO $dto,
        OrderService $orderService,
    ): JsonResponse {
        $order = $orderService->create($dto);

        return $this->json($order, Response::HTTP_CREATED);
    }
}

// ❌ Fat controller — business logic inside
#[Route('/api/orders')]
class OrderController extends AbstractController
{
    #[Route('', methods: ['POST'])]
    public function create(Request $request): JsonResponse
    {
        $data = json_decode($request->getContent(), true);
        // 50 lines of validation...
        // 30 lines of business logic...
        // 20 lines of persistence...
        return $this->json($result);
    }
}
```

### 3. Dependency injection — autowiring

```php
// ✅ Constructor injection (preferred)
final class OrderService
{
    public function __construct(
        private readonly OrderRepository $orderRepository,
        private readonly EventDispatcherInterface $eventDispatcher,
        private readonly LoggerInterface $logger,
    ) {}
}

// ❌ Container injection (anti-pattern)
class OrderService
{
    public function __construct(private ContainerInterface $container) {}

    public function doSomething(): void
    {
        $repo = $this->container->get(OrderRepository::class); // NO
    }
}
```

### 4. PHP 8 attributes (no more YAML/XML for routing)

```php
// ✅ Native attributes
#[Route('/api/users/{id}', methods: ['GET'])]
#[IsGranted('ROLE_USER')]
#[Cache(maxage: 3600)]
public function show(int $id): JsonResponse { /* ... */ }
```

### 5. Events for decoupling

```php
// ✅ Domain event
final readonly class OrderCreatedEvent
{
    public function __construct(
        public int $orderId,
        public string $userEmail,
    ) {}
}

// ✅ Listener declared via attribute
#[AsEventListener(event: OrderCreatedEvent::class)]
final class SendOrderConfirmationListener
{
    public function __invoke(OrderCreatedEvent $event): void
    {
        // Send confirmation email
    }
}
```

---

## 📐 Recommended patterns

### DTOs with MapRequestPayload

```php
// ✅ DTO with built-in validation
final readonly class CreateOrderDTO
{
    public function __construct(
        #[Assert\NotBlank]
        #[Assert\Positive]
        public int $productId,

        #[Assert\NotBlank]
        #[Assert\Range(min: 1, max: 100)]
        public int $quantity,

        #[Assert\NotBlank]
        #[Assert\Email]
        public string $customerEmail,
    ) {}
}
```

### Custom repository — QueryBuilder

```php
// ✅ Repository with business methods
final class OrderRepository extends ServiceEntityRepository
{
    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, Order::class);
    }

    /** @return Order[] */
    public function findPendingByUser(int $userId): array
    {
        return $this->createQueryBuilder('o')
            ->andWhere('o.user = :userId')
            ->andWhere('o.status = :status')
            ->setParameter('userId', $userId)
            ->setParameter('status', OrderStatus::Pending)
            ->orderBy('o.createdAt', 'DESC')
            ->getQuery()
            ->getResult();
    }
}
```

### Voters for authorisation

```php
// ✅ Voter — centralised authorisation logic
final class OrderVoter extends Voter
{
    protected function supports(string $attribute, mixed $subject): bool
    {
        return $subject instanceof Order
            && in_array($attribute, ['VIEW', 'EDIT', 'DELETE']);
    }

    protected function voteOnAttribute(string $attribute, mixed $subject, TokenInterface $token): bool
    {
        $user = $token->getUser();

        return match($attribute) {
            'VIEW' => true,
            'EDIT', 'DELETE' => $subject->getOwner() === $user,
            default => false,
        };
    }
}
```

### Messenger for async processing

```php
// ✅ Message + Handler
final readonly class SendNotification
{
    public function __construct(
        public int $userId,
        public string $message,
    ) {}
}

#[AsMessageHandler]
final class SendNotificationHandler
{
    public function __invoke(SendNotification $message): void
    {
        // Async processing
    }
}
```

---

## 🚀 Doctrine & batch-ingestion performance

Lessons that scale (framework-agnostic in spirit, Doctrine-flavoured here):

### Never put heavy or external work inside the Doctrine flush cycle

Doctrine **entity/lifecycle listeners** (`prePersist`, `postPersist`, `postFlush`)
and `#[AsDoctrineListener]` run **inside `flush()`**. Doing any of the following
there turns a bulk operation into a latency/availability bomb:

- a **nested `flush()`** per entity (quadratic UoW + transaction nesting);
- a **broker dispatch / HTTP call** per entity (an outage there makes `flush()`
  throw → the whole import dies);
- **N resolver queries** per entity.

✅ Defer it: dispatch an **async message after commit** (collect ids during the
loop, dispatch once the transaction is committed — *not* from the listener).
A bare `Messenger` async transport send from a listener still hits the broker
synchronously and re-introduces the dependency.

### Kill the lazy-proxy N+1

```php
// ❌ find() per row → hydration + query each time
// (bulk order import resolving each line's product by SKU)
$product = $repo->findOneBy(['sku' => $sku]);

// ✅ resolve the whole batch in ONE query, then a non-hydrating reference
$idBySku = $repo->fetchIdsBySkus($skus);   // 1 query
$orderItem->setProduct($em->getReference(Product::class, $idBySku[$sku]));
```

`getReference()` returns a **lazy proxy with no query** — the FK is written from
the id at flush. ⚠️ But any **non-identifier access** to that proxy (often by a
*listener*) re-triggers the lazy load → the N+1 silently comes back, just moved.
Audit what dereferences the proxy downstream; move that work async if it only
needs the id.

⚠️ **`getReference()` needs the id in the entity's PHP identifier type**, not
the raw DB form. `find()` is lenient (it round-trips through the DBAL type), so
code that works with `find($rawBinaryUuid)` can throw *"Cannot assign string to
property …::$id of type Uuid"* the moment you swap to `getReference()`. Resolve
the batch as the typed id (`SELECT BIN_TO_UUID(id)` → `Uuid::fromString(...)`).

### Kill the lazy-*collection* hydration bomb

The proxy N+1 has a nastier sibling: a method on the **inverse** side that
touches the lazy `Collection`.

```php
// ❌ in a bulk loop: $customer->addOrder($order) → addOrder() does
//    if (!$this->orders->contains($order)) …  → contains() INITIALIZES the
//    whole collection: SELECT * FROM `order` WHERE customer_id = ? (every past order)
$customer->addOrder($order);

// ✅ set the OWNING side only — the FK lives there, no collection touched
$order->setCustomer($customer);
```

`contains()` / `count()` / iteration on an uninitialized `PersistentCollection`
**hydrates every row** of that association — per parent, inside the loop, and
`cascade:persist` then re-walks the bloated collection on every `flush()`. In
bulk ingestion, never go through `add*()` convenience methods; set the owning
side. In practice this is often the *dominant* cost — larger than the
single-entity proxy N+1, because it scales with the parent's whole history.

### Bulk loop hygiene

- `em->clear()` (or detach) **after each flush batch** — an unbounded
  UnitOfWork makes every subsequent `flush()` re-compute changesets over all
  managed entities (≈ quadratic).
- **Parse / transform once**: never do a pre-pass that re-parses the same input
  the main loop parses again — collect once, reuse.
- For very high volume, **native batched `INSERT`** beats the ORM by 10-50×
  (no hydration, no UoW); reserve the ORM path for low-volume/interactive.
- A **non-atomic claim** (`SELECT … LIMIT` then a separate `UPDATE state`)
  cannot be parallelised safely and strands rows on failure — use
  `FOR UPDATE SKIP LOCKED` / an atomic claiming `UPDATE`, with a TTL reclaim.

## 🚫 Symfony anti-patterns

```php
// ❌ Business logic in Entities
class Order
{
    public function sendConfirmationEmail(): void { /* NO */ }
}

// ❌ $container->get() in application code
$service = $this->container->get('my.service');

// ❌ DQL/SQL queries in controllers
$this->getDoctrine()->getManager()->createQuery('SELECT ...');

// ❌ Legacy annotations (use PHP 8 attributes)
/** @Route("/api/users") */

// ❌ Serialization groups on entities (prefer DTOs)
/** @Groups({"api"}) */
private string $password; // DANGER
```

---

## ✅ Quick checklist

```
- [ ] Controllers < 20 lines per action
- [ ] Business logic in Services, not Controllers or Entities
- [ ] DTOs for API inputs/outputs (MapRequestPayload)
- [ ] Autowiring (constructor injection only)
- [ ] PHP 8 attributes for routing, validation, security
- [ ] Events/Messenger for decoupling
- [ ] Voters for complex authorisation
- [ ] No container->get() in application code
- [ ] Versioned migrations (make:migration, never manual SQL)
- [ ] .env.local for local secrets, Vault in production
- [ ] No heavy/external work (nested flush, broker dispatch, N queries) inside Doctrine listeners — defer async post-commit
- [ ] Batch loops: getReference() over find(), em->clear() per batch, parse once, atomic claim (SKIP LOCKED)
- [ ] Bulk loops: set the owning side, never `parent->addChild()` (collection `contains()` hydrates the whole association)
- [ ] `getReference()` fed the typed identifier (not the raw DB form `find()` tolerates)
- [ ] Perf profiling done on a base rebased on prod/master (stale base ⇒ false bottlenecks)
```
