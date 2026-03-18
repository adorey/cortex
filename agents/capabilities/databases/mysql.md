# MySQL — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for MySQL / MariaDB.
To combine with a role (e.g. roles/engineering/dba.md).
-->

> **Reference version:** MySQL 8.0+ / MariaDB 11.x | **Last updated:** 2026-02
> **Official docs:** [dev.mysql.com/doc](https://dev.mysql.com/doc/) | [mariadb.com/kb](https://mariadb.com/kb/)

---

## 🏛️ Fundamental principles

### 1. Schema design — normalisation first

- **3NF minimum** for transactional data
- Denormalise only for reads (materialised views, cache tables)
- Document every denormalisation and its reason

```sql
-- ✅ Good — normalised table with constraints
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

### 2. Naming conventions

```
Tables          : singular, snake_case           → order, access_card
Columns         : snake_case                     → created_at, user_id
Indexes         : idx_{table}_{columns}          → idx_order_user_id
Foreign Keys    : fk_{source_table}_{target_table} → fk_order_user
Unique          : uq_{table}_{columns}           → uq_user_email
```

### 3. Data types — choose correctly

| Data | Type | ❌ Avoid |
|---|---|---|
| IDs | `BIGINT UNSIGNED AUTO_INCREMENT` or `BINARY(16)` UUID | `INT` (overflow) |
| Dates | `DATETIME` (+ app timezone) | `TIMESTAMP` (2038 limit) |
| Money | `DECIMAL(10, 2)` | `FLOAT` / `DOUBLE` (imprecision) |
| Booleans | `TINYINT(1)` | `ENUM('0','1')` |
| Statuses | `VARCHAR(20)` | native `ENUM` (hard to migrate) |
| Short text | `VARCHAR(n)` with appropriate n | `TEXT` (if < 255 chars) |
| Long text | `TEXT` / `MEDIUMTEXT` | `VARCHAR(65535)` |
| JSON | `JSON` (native MySQL 8) | `TEXT` + manual serialisation |

### 4. UTF8MB4 — always

```sql
-- ✅ Support emojis and all Unicode characters
DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

**Never** use `utf8` in MySQL (it is `utf8mb3`, limited to 3 bytes).

### 5. InnoDB — always

```sql
ENGINE=InnoDB
```

No MyISAM. No MEMORY for persistent tables.

---

## 📐 Recommended patterns

### Index strategy

```sql
-- ✅ Composite index for frequent queries
-- Order: WHERE columns + ORDER BY + SELECT (covering index)
CREATE INDEX idx_order_user_status_created
ON `order` (`user_id`, `status`, `created_at` DESC);

-- ✅ This query uses the index 100%
SELECT id, total_amount, created_at
FROM `order`
WHERE user_id = 42
  AND status = 'completed'
ORDER BY created_at DESC
LIMIT 20;
```

**Index rules:**
- Most selective columns first (except for range queries)
- One index per frequent query pattern
- No more than 5-6 indexes per table (impact on writes)
- Verify with `EXPLAIN ANALYZE` that the index is used

### Queries — best practices

```sql
-- ✅ Prepared statements (always, no exceptions)
PREPARE stmt FROM 'SELECT * FROM user WHERE id = ?';

-- ✅ Cursor-based pagination (not OFFSET for large volumes)
SELECT * FROM `order`
WHERE id > :last_seen_id
ORDER BY id ASC
LIMIT 20;

-- ❌ OFFSET-based pagination (slow on large volumes)
SELECT * FROM `order`
ORDER BY id ASC
LIMIT 20 OFFSET 100000;  -- scans 100,000 rows for nothing

-- ✅ Explicit SELECT (no SELECT *)
SELECT id, user_id, status, total_amount FROM `order`;

-- ❌ SELECT * (unnecessary columns, no covering index)
SELECT * FROM `order`;
```

### Migrations — clean management

```
- Always version migrations (Doctrine, Flyway, Liquibase...)
- Never manual SQL in production
- Reversible migrations where possible (UP + DOWN)
- Test migrations on a production copy before deploying
- Non-blocking migrations for large tables (pt-online-schema-change)
```

### Transactions

```sql
-- ✅ Explicit transaction for related operations
START TRANSACTION;

UPDATE account SET balance = balance - 100 WHERE id = 1;
UPDATE account SET balance = balance + 100 WHERE id = 2;
INSERT INTO transfer (from_id, to_id, amount) VALUES (1, 2, 100);

COMMIT;

-- ✅ Appropriate isolation level
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

---

## 🚫 Anti-patterns

```sql
-- ❌ SQL concatenation (SQL injection)
"SELECT * FROM user WHERE name = '" + userName + "'"

-- ❌ SELECT * everywhere
SELECT * FROM order JOIN user JOIN product;

-- ❌ N+1 queries
-- PHP loop: for each order, SELECT user WHERE id = order.user_id

-- ❌ Individual index on every column
-- (better: a composite index tailored to real queries)

-- ❌ Storing files as BLOB
-- (use object storage: S3, MinIO)

-- ❌ No foreign keys "for performance"
-- (FKs protect data integrity)

-- ❌ Native MySQL ENUM
ALTER TABLE user ADD status ENUM('active', 'banned');
-- Cannot modify without ALTER TABLE = potential downtime
```

---

## 🔒 Database security

```
- [ ] Prepared statements mandatory (never concatenation)
- [ ] Application user with minimal rights (no GRANT ALL)
- [ ] No root for the application
- [ ] Passwords hashed at application level (bcrypt/argon2)
- [ ] Encrypt sensitive data (AES_ENCRYPT or app-level)
- [ ] SSL/TLS between app and DB
- [ ] Automated backups tested (restore test at least monthly)
- [ ] Audit log enabled for sensitive access
```

---

## 📊 Monitoring

```
Key metrics:
- Slow queries (slow_query_log, threshold: 1s)
- Active connections vs max_connections
- Buffer pool hit ratio (> 99%)
- Replication lag (if replica)
- Table locks / deadlocks
- Disk I/O and disk space
```

---

## ✅ Quick checklist

```
- [ ] InnoDB + utf8mb4_unicode_ci
- [ ] Naming conventions respected
- [ ] Appropriate data types (DECIMAL for money, BIGINT for IDs)
- [ ] Composite indexes aligned with frequent queries
- [ ] EXPLAIN ANALYZE on critical queries
- [ ] Prepared statements everywhere
- [ ] Versioned migrations (never manual SQL in production)
- [ ] Foreign keys for integrity
- [ ] Cursor-based pagination (not OFFSET)
- [ ] Automated backups + restore test
```
