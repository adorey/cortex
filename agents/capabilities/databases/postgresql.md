# PostgreSQL — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for PostgreSQL.
To combine with a role (e.g. roles/engineering/dba.md).
-->

> **Reference version:** PostgreSQL 16+ | **Last updated:** 2026-04
> **Official docs:** [postgresql.org/docs](https://www.postgresql.org/docs/current/) | [Wiki](https://wiki.postgresql.org/)

---

## 🏛️ Fundamental principles

### 1. Schema design — normalisation first

- **3NF minimum** for transactional data
- Denormalise only for reads (materialised views, JSONB columns for flexibility)
- Document every denormalisation and its reason

```sql
-- ✅ Good — normalised table with constraints
CREATE TABLE "order" (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_amount NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_order_user FOREIGN KEY (user_id) REFERENCES "user" (id)
);

CREATE INDEX idx_order_user_id ON "order" (user_id);
CREATE INDEX idx_order_status ON "order" (status);
```

### 2. Naming conventions

```
Tables          : singular, snake_case           → order, access_card
Columns         : snake_case                     → created_at, user_id
Indexes         : idx_{table}_{columns}          → idx_order_user_id
Foreign Keys    : fk_{source_table}_{target_table} → fk_order_user
Unique          : uq_{table}_{columns}           → uq_user_email
Sequences       : {table}_{column}_seq           → order_id_seq
Schemas         : snake_case                     → public, billing, audit
Check constr.   : chk_{table}_{rule}             → chk_order_positive_amount
```

### 3. Data types — choose correctly

| Data | Type | ❌ Avoid |
|---|---|---|
| IDs | `BIGINT GENERATED ALWAYS AS IDENTITY` or `UUID` | `SERIAL` (legacy) |
| Dates | `TIMESTAMPTZ` (always with timezone) | `TIMESTAMP` without TZ |
| Money | `NUMERIC(10, 2)` | `MONEY` type / `FLOAT` / `DOUBLE PRECISION` |
| Booleans | `BOOLEAN` (native) | `INTEGER` 0/1 |
| Statuses | `VARCHAR(20)` or custom `CREATE TYPE` | long `TEXT` for enums |
| Short text | `VARCHAR(n)` with appropriate n | `CHAR(n)` (right-padded) |
| Long text | `TEXT` (no length limit in PG) | `VARCHAR` without n |
| JSON | `JSONB` (binary, indexable) | `JSON` (text, not indexable) |
| Arrays | `INTEGER[]`, `TEXT[]` (native arrays) | JSON for simple lists |
| IP addresses | `INET` / `CIDR` (native) | `VARCHAR` |
| Ranges | `INT4RANGE`, `TSTZRANGE` (native) | two separate columns |

### 4. UTF-8 encoding — always

```sql
-- ✅ Set at database creation
CREATE DATABASE myapp
    ENCODING 'UTF8'
    LC_COLLATE 'en_US.UTF-8'
    LC_CTYPE 'en_US.UTF-8';
```

### 5. Use schemas for organisation

```sql
-- ✅ Organise by business domain
CREATE SCHEMA billing;
CREATE SCHEMA audit;
CREATE SCHEMA staging;

-- Set search path per role
ALTER ROLE app_user SET search_path TO public, billing;
```

---

## 📐 Recommended patterns

### Index strategy

```sql
-- ✅ B-tree (default) — equality and range queries
CREATE INDEX idx_order_user_status ON "order" (user_id, status);

-- ✅ Partial index — only index what matters
CREATE INDEX idx_order_pending ON "order" (created_at)
    WHERE status = 'pending';

-- ✅ GIN index for JSONB
CREATE INDEX idx_user_metadata ON "user" USING GIN (metadata);

-- ✅ GIN index for full-text search
CREATE INDEX idx_article_search ON article USING GIN (to_tsvector('english', title || ' ' || body));

-- ✅ Covering index (INCLUDE) — avoids table lookups
CREATE INDEX idx_order_user_covering ON "order" (user_id)
    INCLUDE (status, total_amount);

-- ✅ BRIN index for naturally ordered data (timestamps, sequences)
CREATE INDEX idx_log_created ON audit_log USING BRIN (created_at);

-- ✅ GiST index for geometric / range data
CREATE INDEX idx_event_period ON event USING GIST (active_period);
```

**Index rules:**
- Partial indexes for filtered queries (enormous space/perf gain)
- INCLUDE columns for covering indexes (PG 11+)
- BRIN for append-only tables (logs, events) — tiny, fast
- GIN for JSONB, arrays, full-text search
- GiST for ranges, geometric, PostGIS
- Verify with `EXPLAIN (ANALYZE, BUFFERS)` that the index is used
- `CONCURRENTLY` for production index creation: `CREATE INDEX CONCURRENTLY ...`

### Queries — best practices

```sql
-- ✅ Prepared statements (always, no exceptions)
PREPARE get_user AS SELECT id, email FROM "user" WHERE id = $1;
EXECUTE get_user(42);

-- ✅ Cursor-based pagination (not OFFSET for large volumes)
SELECT * FROM "order"
WHERE (created_at, id) < ($1, $2)
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- ❌ OFFSET-based pagination (slow on large volumes)
SELECT * FROM "order"
ORDER BY id ASC
LIMIT 20 OFFSET 100000;  -- scans 100,000 rows for nothing

-- ✅ CTEs for readability (PG 12+ optimises them)
WITH recent_orders AS (
    SELECT * FROM "order"
    WHERE created_at > NOW() - INTERVAL '30 days'
)
SELECT user_id, COUNT(*), SUM(total_amount)
FROM recent_orders
GROUP BY user_id;

-- ✅ Window functions for analytics
SELECT id, user_id, total_amount,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
FROM "order";

-- ✅ UPSERT (INSERT ... ON CONFLICT)
INSERT INTO settings (key, value)
VALUES ('theme', 'dark')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
```

### JSONB — when and how

```sql
-- ✅ Good use: flexible metadata, user preferences, config
ALTER TABLE "user" ADD COLUMN metadata JSONB DEFAULT '{}';

-- ✅ Query JSONB efficiently
SELECT * FROM "user" WHERE metadata @> '{"newsletter": true}';
SELECT * FROM "user" WHERE metadata->>'lang' = 'fr';

-- ❌ Bad use: storing structured relational data as JSONB
-- If you query a JSONB field in WHERE/JOIN regularly, normalise it
```

### Migrations — clean management

```
- Always version migrations (Doctrine, Flyway, Alembic, Knex...)
- Never manual SQL in production
- Reversible migrations where possible (UP + DOWN)
- Test migrations on a production copy before deploying
- Non-blocking migrations:
  - CREATE INDEX CONCURRENTLY (no table lock)
  - ADD COLUMN with DEFAULT is instant in PG 11+
  - For NOT NULL on existing column: add constraint as NOT VALID, then VALIDATE
```

### Transactions & isolation

```sql
-- ✅ Explicit transaction for related operations
BEGIN;

UPDATE account SET balance = balance - 100 WHERE id = 1;
UPDATE account SET balance = balance + 100 WHERE id = 2;
INSERT INTO transfer (from_id, to_id, amount) VALUES (1, 2, 100);

COMMIT;

-- ✅ Advisory locks for application-level coordination
SELECT pg_advisory_lock(hashtext('import_users'));
-- ... exclusive operation ...
SELECT pg_advisory_unlock(hashtext('import_users'));
```

**Isolation levels:**
```
READ COMMITTED   : default, good for most cases
REPEATABLE READ  : for consistent reports
SERIALIZABLE     : for financial operations (watch for serialization failures)
```

---

## 🧰 PostgreSQL-specific features

### Partitioning

```sql
-- ✅ Range partitioning for time-series data
CREATE TABLE measurement (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    recorded_at TIMESTAMPTZ NOT NULL,
    value NUMERIC NOT NULL
) PARTITION BY RANGE (recorded_at);

CREATE TABLE measurement_2026_q1 PARTITION OF measurement
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
```

### Materialized views

```sql
-- ✅ Pre-computed aggregations for dashboards
CREATE MATERIALIZED VIEW mv_daily_revenue AS
SELECT DATE(created_at) AS day, SUM(total_amount) AS revenue
FROM "order"
WHERE status = 'completed'
GROUP BY DATE(created_at);

-- Refresh (CONCURRENTLY requires a unique index)
CREATE UNIQUE INDEX ON mv_daily_revenue (day);
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_revenue;
```

### Listen / Notify

```sql
-- ✅ Real-time notifications (lightweight pub/sub)
LISTEN order_created;
NOTIFY order_created, '{"order_id": 42}';
```

### Row-Level Security (RLS)

```sql
-- ✅ Multi-tenant data isolation at DB level
ALTER TABLE "order" ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON "order"
    USING (tenant_id = current_setting('app.current_tenant')::BIGINT);
```

---

## 🚫 Anti-patterns

```sql
-- ❌ SQL concatenation (SQL injection)
"SELECT * FROM user WHERE name = '" || userName || "'"

-- ❌ SELECT * everywhere
SELECT * FROM "order" JOIN "user" JOIN product;

-- ❌ N+1 queries
-- Loop: for each order, SELECT user WHERE id = order.user_id

-- ❌ SERIAL instead of IDENTITY
CREATE TABLE t (id SERIAL);  -- legacy, prefer GENERATED ALWAYS AS IDENTITY

-- ❌ TIMESTAMP without timezone
created_at TIMESTAMP;  -- use TIMESTAMPTZ always

-- ❌ FLOAT for money
price DOUBLE PRECISION;  -- use NUMERIC(10, 2)

-- ❌ OFFSET for large-volume pagination
SELECT * FROM big_table LIMIT 20 OFFSET 500000;

-- ❌ CREATE INDEX without CONCURRENTLY in production
CREATE INDEX idx_huge ON big_table (col);  -- locks the table

-- ❌ Storing files as BYTEA
-- Use object storage (S3, MinIO) + store the path/URL

-- ❌ No foreign keys "for performance"
-- FKs protect data integrity, use them

-- ❌ JSONB for everything
-- Structured, frequently-queried data belongs in normalised columns
```

---

## 🔒 Database security

```
- [ ] Prepared statements mandatory (never concatenation)
- [ ] Application user with minimal privileges (no SUPERUSER)
- [ ] No postgres superuser for the application
- [ ] Passwords hashed at application level (bcrypt/argon2)
- [ ] Encrypt sensitive data (pgcrypto or app-level)
- [ ] SSL/TLS between app and DB (sslmode=verify-full)
- [ ] Row-Level Security for multi-tenant isolation
- [ ] pg_hba.conf locked to known hosts/networks
- [ ] Automated backups tested (pg_dump / pg_basebackup + restore test monthly)
- [ ] Audit logging (pgaudit extension)
```

---

## 📊 Monitoring

```
Key metrics:
- Slow queries (pg_stat_statements, threshold: 100ms)
- Active connections vs max_connections
- Cache hit ratio (> 99%): SELECT sum(heap_blks_hit) / sum(heap_blks_hit + heap_blks_read) FROM pg_statio_user_tables
- Replication lag (if replica)
- Dead tuples / autovacuum activity
- Transaction wraparound (age of oldest xid)
- Table bloat (pgstattuple)
- Disk I/O and WAL generation rate
- Lock waits and deadlocks (pg_stat_activity)
```

---

## ✅ Quick checklist

```
- [ ] UTF-8 encoding + TIMESTAMPTZ everywhere
- [ ] Naming conventions respected
- [ ] Appropriate data types (NUMERIC for money, BIGINT IDENTITY for IDs, JSONB not JSON)
- [ ] Indexes aligned with frequent queries (partial, covering, GIN, BRIN)
- [ ] EXPLAIN (ANALYZE, BUFFERS) on critical queries
- [ ] Prepared statements everywhere
- [ ] Versioned migrations (never manual SQL in production)
- [ ] CREATE INDEX CONCURRENTLY for production
- [ ] Foreign keys for integrity
- [ ] Cursor-based pagination (not OFFSET)
- [ ] Automated backups + restore test
- [ ] pg_stat_statements enabled
```
