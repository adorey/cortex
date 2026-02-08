# Symfony — Best Practices

<!-- STACK REFERENCE
Fiche de best practices pour le framework Symfony.
À combiner avec stacks/languages/php.md pour les best practices PHP générales.
-->

> **Version de référence :** Symfony 7.x (LTS : 6.4) | **Dernière mise à jour :** 2026-02
> **Docs officielles :** [symfony.com/doc](https://symfony.com/doc/current/index.html) | [Best Practices](https://symfony.com/doc/current/best_practices.html)

---

## 🏛️ Principes fondamentaux

### 1. Structure Bundle-less

Symfony recommande depuis la v4 de **ne pas créer de bundles** pour le code applicatif.

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

Pour les gros projets, préférer une organisation par **domaine métier** :

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

### 2. Controllers minces

```php
// ✅ Controller mince — délègue au service
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

// ❌ Controller obèse — logique métier dedans
#[Route('/api/orders')]
class OrderController extends AbstractController
{
    #[Route('', methods: ['POST'])]
    public function create(Request $request): JsonResponse
    {
        $data = json_decode($request->getContent(), true);
        // 50 lignes de validation...
        // 30 lignes de logique métier...
        // 20 lignes de persistance...
        return $this->json($result);
    }
}
```

### 3. Injection de dépendances — autowiring

```php
// ✅ Constructor injection (préféré)
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
        $repo = $this->container->get(OrderRepository::class); // NON
    }
}
```

### 4. Attributs PHP 8 (plus de YAML/XML pour le routing)

```php
// ✅ Attributs natifs
#[Route('/api/users/{id}', methods: ['GET'])]
#[IsGranted('ROLE_USER')]
#[Cache(maxage: 3600)]
public function show(int $id): JsonResponse { /* ... */ }
```

### 5. Events pour le découplage

```php
// ✅ Événement métier
final readonly class OrderCreatedEvent
{
    public function __construct(
        public int $orderId,
        public string $userEmail,
    ) {}
}

// ✅ Listener déclaré par attribut
#[AsEventListener(event: OrderCreatedEvent::class)]
final class SendOrderConfirmationListener
{
    public function __invoke(OrderCreatedEvent $event): void
    {
        // Envoyer l'email de confirmation
    }
}
```

---

## 📐 Patterns recommandés

### DTOs avec MapRequestPayload

```php
// ✅ DTO avec validation intégrée
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

### Repository custom — QueryBuilder

```php
// ✅ Repository avec méthodes métier
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

### Voters pour les autorisations

```php
// ✅ Voter — logique d'autorisation centralisée
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

### Messenger pour l'asynchrone

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
        // Traitement asynchrone
    }
}
```

---

## 🚫 Anti-patterns Symfony

```php
// ❌ Logique métier dans les Entity
class Order
{
    public function sendConfirmationEmail(): void { /* NON */ }
}

// ❌ $container->get() dans le code applicatif
$service = $this->container->get('my.service');

// ❌ Requêtes DQL/SQL dans les controllers
$this->getDoctrine()->getManager()->createQuery('SELECT ...');

// ❌ Annotations legacy (utilisez les attributs PHP 8)
/** @Route("/api/users") */

// ❌ Serialization groups dans les entities (préférer les DTOs)
/** @Groups({"api"}) */
private string $password; // DANGER
```

---

## ✅ Checklist rapide

```
- [ ] Controllers < 20 lignes par action
- [ ] Logique métier dans les Services, pas les Controllers ni les Entities
- [ ] DTOs pour les entrées/sorties API (MapRequestPayload)
- [ ] Autowiring (constructor injection uniquement)
- [ ] Attributs PHP 8 pour routing, validation, sécurité
- [ ] Events/Messenger pour le découplage
- [ ] Voters pour les autorisations complexes
- [ ] Pas de container->get() dans le code applicatif
- [ ] Migrations versionnées (make:migration, jamais de SQL manuel)
- [ ] .env.local pour les secrets locaux, Vault en prod
```
