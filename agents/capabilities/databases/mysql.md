# MySQL — Best Practices

<!-- CAPABILITY REFERENCE
Fiche de best practices pour MySQL / MariaDB.
À combiner avec un rôle (ex: roles/dba.md).
-->

> **Version de référence :** MySQL 8.0+ / MariaDB 11.x | **Dernière mise à jour :** 2026-02
> **Docs officielles :** [dev.mysql.com/doc](https://dev.mysql.com/doc/) | [mariadb.com/kb](https://mariadb.com/kb/)

---

## 🏛️ Principes fondamentaux

### 1. Schema design — normalisation d'abord

- **3NF minimum** pour les données transactionnelles
- Dénormaliser uniquement pour la lecture (vues matérialisées, tables de cache)
- Documenter chaque dénormalisation et sa raison

```sql
-- ✅ Bien — table normalisée avec contraintes
CREATE TABLE `order` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
    `total_amount` DECIMAL(10, 2) NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_order_user_id` (`user_id`),
    INDEX `idx_order_status` (`status`),
    CONSTRAINT `fk_order_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 2. Conventions de nommage

```
Tables          : singulier, snake_case          → order, access_card
Colonnes        : snake_case                     → created_at, user_id
Index           : idx_{table}_{colonnes}         → idx_order_user_id
Foreign Keys    : fk_{table_source}_{table_cible}→ fk_order_user
Unique          : uq_{table}_{colonnes}          → uq_user_email
```

### 3. Types de données — choisir correctement

| Donnée | Type | ❌ Ne pas |
|---|---|---|
| IDs | `BIGINT UNSIGNED AUTO_INCREMENT` ou `BINARY(16)` UUID | `INT` (overflow) |
| Dates | `DATETIME` (+ timezone app) | `TIMESTAMP` (limite 2038) |
| Argent | `DECIMAL(10, 2)` | `FLOAT` / `DOUBLE` (imprécision) |
| Booléens | `TINYINT(1)` | `ENUM('0','1')` |
| Statuts | `VARCHAR(20)` | `ENUM` natif (migration difficile) |
| Texte court | `VARCHAR(n)` avec n adapté | `TEXT` (si < 255 chars) |
| Texte long | `TEXT` / `MEDIUMTEXT` | `VARCHAR(65535)` |
| JSON | `JSON` (natif MySQL 8) | `TEXT` + sérialisation manuelle |

### 4. UTF8MB4 — toujours

```sql
-- ✅ Supporter les emojis et tous les caractères Unicode
DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

**Jamais** `utf8` dans MySQL (c'est `utf8mb3`, limité à 3 bytes).

### 5. InnoDB — toujours

```sql
ENGINE=InnoDB
```

Pas de MyISAM. Pas de MEMORY pour les tables persistantes.

---

## 📐 Patterns recommandés

### Index — stratégie

```sql
-- ✅ Index composite pour les requêtes fréquentes
-- Ordre : colonnes du WHERE + ORDER BY + SELECT (covering index)
CREATE INDEX idx_order_user_status_created
ON `order` (`user_id`, `status`, `created_at` DESC);

-- ✅ Cette requête utilise l'index à 100%
SELECT id, total_amount, created_at
FROM `order`
WHERE user_id = 42
  AND status = 'completed'
ORDER BY created_at DESC
LIMIT 20;
```

**Règles d'index :**
- Colonnes les plus sélectives en premier (sauf pour range queries)
- Un index par pattern de requête fréquent
- Pas plus de 5-6 index par table (impact sur les écritures)
- Vérifier avec `EXPLAIN ANALYZE` que l'index est utilisé

### Requêtes — bonnes pratiques

```sql
-- ✅ Prepared statements (toujours, sans exception)
PREPARE stmt FROM 'SELECT * FROM user WHERE id = ?';

-- ✅ Pagination par curseur (pas OFFSET pour les gros volumes)
SELECT * FROM `order`
WHERE id > :last_seen_id
ORDER BY id ASC
LIMIT 20;

-- ❌ Pagination par OFFSET (lent sur les gros volumes)
SELECT * FROM `order`
ORDER BY id ASC
LIMIT 20 OFFSET 100000;  -- scanne 100 000 lignes pour rien

-- ✅ SELECT explicite (pas de SELECT *)
SELECT id, user_id, status, total_amount FROM `order`;

-- ❌ SELECT * (colonnes inutiles, pas de covering index)
SELECT * FROM `order`;
```

### Migrations — gestion propre

```
- Toujours versionner les migrations (Doctrine, Flyway, Liquibase...)
- Jamais de SQL manuel en production
- Migrations réversibles quand possible (UP + DOWN)
- Tester les migrations sur une copie de la prod avant deploy
- Migrations non-bloquantes pour les grosses tables (pt-online-schema-change)
```

### Transactions

```sql
-- ✅ Transaction explicite pour les opérations liées
START TRANSACTION;

UPDATE account SET balance = balance - 100 WHERE id = 1;
UPDATE account SET balance = balance + 100 WHERE id = 2;
INSERT INTO transfer (from_id, to_id, amount) VALUES (1, 2, 100);

COMMIT;

-- ✅ Isolation level adapté
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

---

## 🚫 Anti-patterns

```sql
-- ❌ Concaténation SQL (injection SQL)
"SELECT * FROM user WHERE name = '" + userName + "'"

-- ❌ SELECT * partout
SELECT * FROM order JOIN user JOIN product;

-- ❌ N+1 queries
-- Boucle PHP : pour chaque order, SELECT user WHERE id = order.user_id

-- ❌ Index sur chaque colonne individuellement
-- (mieux : un index composite adapté aux requêtes réelles)

-- ❌ Stocker des fichiers en BLOB
-- (utiliser un stockage objet : S3, MinIO)

-- ❌ Pas de foreign keys "pour la performance"
-- (les FK protègent l'intégrité des données)

-- ❌ ENUM natif MySQL
ALTER TABLE user ADD status ENUM('active', 'banned');
-- Impossible de modifier sans ALTER TABLE = downtime potentiel
```

---

## 🔒 Sécurité BDD

```
- [ ] Prepared statements obligatoires (jamais de concaténation)
- [ ] Utilisateur applicatif avec droits minimaux (pas de GRANT ALL)
- [ ] Pas de root pour l'application
- [ ] Mots de passe hashés côté applicatif (bcrypt/argon2)
- [ ] Chiffrement des données sensibles (AES_ENCRYPT ou app-level)
- [ ] SSL/TLS entre app et BDD
- [ ] Backups automatiques testés (restore test mensuel minimum)
- [ ] Audit log activé pour les accès sensibles
```

---

## 📊 Monitoring

```
Métriques essentielles :
- Slow queries (slow_query_log, seuil : 1s)
- Connections actives vs max_connections
- Buffer pool hit ratio (> 99%)
- Replication lag (si replica)
- Table locks / deadlocks
- Disk I/O et espace disque
```

---

## ✅ Checklist rapide

```
- [ ] InnoDB + utf8mb4_unicode_ci
- [ ] Conventions de nommage respectées
- [ ] Types de données adaptés (DECIMAL pour l'argent, BIGINT pour les IDs)
- [ ] Index composites alignés sur les requêtes fréquentes
- [ ] EXPLAIN ANALYZE sur les requêtes critiques
- [ ] Prepared statements partout
- [ ] Migrations versionnées (jamais de SQL manuel en prod)
- [ ] Foreign keys pour l'intégrité
- [ ] Pagination par curseur (pas OFFSET)
- [ ] Backups automatiques + test de restore
```
