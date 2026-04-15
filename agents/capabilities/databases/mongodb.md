# MongoDB — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for MongoDB.
To combine with a role (e.g. roles/engineering/dba.md).
-->

> **Reference version:** MongoDB 7.x+ | **Last updated:** 2026-04
> **Official docs:** [mongodb.com/docs](https://www.mongodb.com/docs/manual/) | [University](https://learn.mongodb.com/)

---

## 🏛️ Fundamental principles

### 1. Schema design — data modeling

MongoDB is schema-flexible, **not schema-less**. Design intentionally.

- **Embed** when data is always accessed together (1:1, 1:few)
- **Reference** when data is accessed independently or shared (1:many, many:many)
- Document every design decision and its access pattern justification

```javascript
// ✅ Good — embedded subdocument (1:few, always accessed together)
{
    _id: ObjectId("..."),
    email: "user@example.com",
    profile: {
        firstName: "Ada",
        lastName: "Lovelace",
        avatarUrl: "/avatars/ada.jpg"
    },
    addresses: [
        { type: "home", city: "London", zip: "SW1A 1AA" },
        { type: "work", city: "Cambridge", zip: "CB2 1TN" }
    ],
    createdAt: ISODate("2026-01-15T10:00:00Z"),
    updatedAt: ISODate("2026-01-15T10:00:00Z")
}

// ✅ Good — reference (1:many, orders accessed independently)
// In "order" collection:
{
    _id: ObjectId("..."),
    userId: ObjectId("..."),  // reference to user
    status: "completed",
    totalAmount: NumberDecimal("99.95"),
    items: [
        { productId: ObjectId("..."), name: "Widget", qty: 2, price: NumberDecimal("49.95") }
    ],
    createdAt: ISODate("2026-01-20T14:30:00Z")
}
```

### 2. Naming conventions

```
Databases       : camelCase or snake_case        → myApp, my_app
Collections     : plural, camelCase              → users, orderItems
Fields          : camelCase                      → firstName, createdAt, userId
Indexes         : idx_{collection}_{fields}      → idx_users_email
                  or auto-generated names
Boolean fields  : is/has/can prefix              → isActive, hasVerified, canEdit
```

### 3. Data types — choose correctly

| Data | Type | ❌ Avoid |
|---|---|---|
| IDs | `ObjectId` (default) or `UUID` | String representations of IDs |
| Dates | `ISODate` / `Date` (UTC) | String dates (`"2026-01-15"`) |
| Money | `NumberDecimal` (Decimal128) | `Number` (double, imprecise) |
| Booleans | `Boolean` (native) | `0` / `1` integers or strings |
| Statuses | `String` (with validation) | Numeric codes |
| Counters | `NumberInt` / `NumberLong` | `Number` (default double) |
| Binary data | `GridFS` (files > 16MB) | `BinData` for large files |

### 4. Schema validation — enforce at DB level

```javascript
// ✅ JSON Schema validation on collection
db.createCollection("users", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["email", "createdAt"],
            properties: {
                email: {
                    bsonType: "string",
                    pattern: "^.+@.+\\..+$",
                    description: "Must be a valid email"
                },
                status: {
                    enum: ["active", "suspended", "deleted"],
                    description: "Must be a valid status"
                },
                createdAt: {
                    bsonType: "date"
                }
            }
        }
    },
    validationLevel: "strict",
    validationAction: "error"
});
```

---

## 📐 Recommended patterns

### Index strategy

```javascript
// ✅ Single field index
db.users.createIndex({ email: 1 }, { unique: true });

// ✅ Compound index — follows ESR rule (Equality, Sort, Range)
db.orders.createIndex({ userId: 1, createdAt: -1 });

// ✅ Partial index — only index what matters
db.orders.createIndex(
    { createdAt: -1 },
    { partialFilterExpression: { status: "pending" } }
);

// ✅ TTL index — automatic document expiration
db.sessions.createIndex(
    { createdAt: 1 },
    { expireAfterSeconds: 86400 }  // 24 hours
);

// ✅ Text index for full-text search
db.articles.createIndex({ title: "text", body: "text" });

// ✅ Wildcard index for flexible JSONB-like documents
db.products.createIndex({ "attributes.$**": 1 });

// ✅ Geospatial index
db.venues.createIndex({ location: "2dsphere" });
```

**Index rules:**
- Follow the **ESR rule**: Equality fields first, then Sort, then Range
- One compound index > multiple single-field indexes
- Use `explain("executionStats")` to verify index usage
- Partial indexes for filtered queries (huge space/perf savings)
- TTL indexes for auto-expiring data (sessions, tokens, logs)
- No more than 5-6 indexes per collection (impact on write throughput)
- Build indexes in background on production: `db.coll.createIndex({...}, { background: true })`

### Queries — best practices

```javascript
// ✅ Projection — only return needed fields
db.users.find(
    { status: "active" },
    { email: 1, profile: 1, _id: 0 }
);

// ✅ Cursor-based pagination (not skip for large volumes)
db.orders.find({ userId: userId, _id: { $lt: lastSeenId } })
    .sort({ _id: -1 })
    .limit(20);

// ❌ Skip-based pagination (slow on large volumes)
db.orders.find().sort({ _id: -1 }).skip(100000).limit(20);

// ✅ Aggregation pipeline for complex queries
db.orders.aggregate([
    { $match: { status: "completed", createdAt: { $gte: thirtyDaysAgo } } },
    { $group: {
        _id: "$userId",
        totalSpent: { $sum: "$totalAmount" },
        orderCount: { $count: {} }
    }},
    { $sort: { totalSpent: -1 } },
    { $limit: 10 }
]);

// ✅ $lookup for joins (use sparingly)
db.orders.aggregate([
    { $lookup: {
        from: "users",
        localField: "userId",
        foreignField: "_id",
        as: "user"
    }},
    { $unwind: "$user" }
]);

// ✅ Bulk operations for batch writes
db.products.bulkWrite([
    { updateOne: { filter: { sku: "A1" }, update: { $inc: { stock: -1 } } } },
    { updateOne: { filter: { sku: "B2" }, update: { $inc: { stock: -3 } } } }
]);
```

### Embedding vs. referencing — decision framework

```
EMBED when:
  ✅ Data is always read together (user + profile)
  ✅ 1:1 or 1:few relationship (addresses, phone numbers)
  ✅ Data doesn't change independently
  ✅ Subdocument count is bounded and small (< 100)

REFERENCE when:
  ✅ Data is accessed independently (orders from user)
  ✅ 1:many or many:many relationship
  ✅ Document would exceed 16MB
  ✅ Data is shared across collections
  ✅ Data changes frequently and independently

HYBRID (embed + duplicate key fields):
  ✅ Embed a summary, reference the full document
  ✅ Example: order embeds { userId, userName } but full user is in users collection
  ⚠️  Accept eventual inconsistency or write to both on update
```

### Migrations — change management

```
- Use a migration framework (migrate-mongo, mongock, etc.)
- Never manual scripts in production
- Migrations must be idempotent (safe to run twice)
- For schema changes on large collections:
  - Add new fields with defaults (cheap)
  - Backfill in batches (don't update millions at once)
  - Remove old fields after all code paths are updated
- Version your document schema:
  { schemaVersion: 2, ... }
```

### Transactions (multi-document)

```javascript
// ✅ Multi-document transaction (replica set required)
const session = client.startSession();
session.startTransaction();

try {
    await accounts.updateOne(
        { _id: fromId }, { $inc: { balance: -amount } }, { session }
    );
    await accounts.updateOne(
        { _id: toId }, { $inc: { balance: amount } }, { session }
    );
    await transfers.insertOne(
        { from: fromId, to: toId, amount, date: new Date() }, { session }
    );
    await session.commitTransaction();
} catch (error) {
    await session.abortTransaction();
    throw error;
} finally {
    session.endSession();
}
```

**Transaction rules:**
- Keep transactions short (< 60 seconds)
- Transactions require a replica set (even single-node)
- Prefer document-level atomicity (embed) over multi-document transactions when possible

---

## 🧰 MongoDB-specific features

### Change streams

```javascript
// ✅ Real-time event streaming (replica set required)
const changeStream = db.orders.watch([
    { $match: { "fullDocument.status": "completed" } }
]);

changeStream.on("change", (event) => {
    console.log("Order completed:", event.fullDocument._id);
});
```

### Time series collections

```javascript
// ✅ Optimised for time-series data (MongoDB 5.0+)
db.createCollection("metrics", {
    timeseries: {
        timeField: "timestamp",
        metaField: "sensorId",
        granularity: "minutes"
    },
    expireAfterSeconds: 2592000  // 30 days retention
});
```

### Atlas Search (if using Atlas)

```javascript
// ✅ Full-text search with scoring and facets
db.articles.aggregate([
    { $search: {
        index: "default",
        text: { query: "performance optimization", path: ["title", "body"] }
    }},
    { $limit: 10 },
    { $project: { title: 1, score: { $meta: "searchScore" } } }
]);
```

---

## 🚫 Anti-patterns

```javascript
// ❌ Unbounded arrays (grows forever, hits 16MB limit)
{ _id: 1, followers: [/* 500,000 user IDs */] }

// ❌ Deep nesting (> 3 levels, hard to query and index)
{ a: { b: { c: { d: { e: "too deep" } } } } }

// ❌ Massive documents (approaching 16MB)
// Split into referenced collections

// ❌ No schema validation
// "Schema-flexible" ≠ "no rules"

// ❌ Using $where or string-based evaluation
db.users.find({ $where: "this.age > 18" });  // slow, no index, injection risk

// ❌ Skip-based pagination on large collections
db.items.find().skip(1000000).limit(20);

// ❌ Over-using $lookup (N+1 at aggregation level)
// If you need many joins, reconsider your data model or use a relational DB

// ❌ Not using projections (returning entire documents)
db.users.find({});  // returns all fields, wastes bandwidth

// ❌ String dates instead of ISODate
{ createdAt: "2026-01-15" }  // can't use date operators, sorting is lexicographic

// ❌ Number (double) for money
{ price: 19.99 }  // use NumberDecimal("19.99")

// ❌ No indexes
// "It's fast in dev" — with 100 rows. With 10M, it's a full collection scan
```

---

## 🔒 Database security

```
- [ ] Authentication enabled (SCRAM-SHA-256 or x.509)
- [ ] Application user with minimal roles (no root / dbAdmin)
- [ ] Authorization: role-based access control (RBAC)
- [ ] Network: bind to specific IPs, no 0.0.0.0
- [ ] TLS/SSL between app and DB
- [ ] Encrypt sensitive fields at application level
- [ ] Enable audit logging (Enterprise / Atlas)
- [ ] Client-side field-level encryption (CSFLE) for PII
- [ ] Automated backups tested (mongodump / Atlas snapshots)
- [ ] No eval() or $where in queries
```

---

## 📊 Monitoring

```
Key metrics:
- Slow queries (profiler level 1, threshold: 100ms)
- Active connections vs maxPoolSize
- Document read/write ratios (opcounters)
- Cache hit ratio (WiredTiger cache)
- Replication lag (if replica set)
- Oplog window (time before oldest entry expires)
- Collection scan ratio (should be near 0)
- Disk I/O and storage size
- Index size vs. available RAM
```

---

## ✅ Quick checklist

```
- [ ] Schema design documented (embed vs. reference decisions justified)
- [ ] Schema validation rules on critical collections
- [ ] Naming conventions respected
- [ ] Appropriate data types (NumberDecimal for money, ISODate for dates)
- [ ] Compound indexes following ESR rule
- [ ] explain("executionStats") on critical queries
- [ ] Projections on all queries (no full document returns)
- [ ] Cursor-based pagination (not skip)
- [ ] Idempotent, versioned migrations
- [ ] Bounded arrays (no unbounded growth)
- [ ] Automated backups + restore test
- [ ] Authentication + RBAC enabled
```
