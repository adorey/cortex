# OpenSearch — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for OpenSearch (AWS Managed or self-hosted).
To combine with a role (e.g. roles/architect.md, roles/lead-backend.md).
-->

> **Reference version:** OpenSearch 2.11+ | **Last updated:** 2026-04
> **Official docs:** [opensearch.org/docs](https://opensearch.org/docs/) | **AWS reference:** [docs.aws.amazon.com/opensearch-service](https://docs.aws.amazon.com/opensearch-service/)

---

## 🏛️ Fundamental principles

### 1. Index design — sharding & replication strategy

- **Shards**: 1 shard per 20–50 GB of data (not 5 shards for 10 GB)
- **Replicas**: 1 minimum for resilience in production (0 in dev)
- **Naming**: `{domain}_{type}_{version|date}` — e.g. `orders_v1`, `logs_2026-04`
- **Rollover**: Automated index rotation for time-series data (ISM policies)

```json
// ✅ Good — properly scaled index
PUT /products_v1
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index.refresh_interval": "5s"
  },
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "category_id": { "type": "keyword" },
      "location": { "type": "geo_point" },
      "name": { "type": "text", "analyzer": "standard" },
      "status": { "type": "keyword" },
      "price": { "type": "scaled_float", "scaling_factor": 100 },
      "created_at": { "type": "date" },
      "updated_at": { "type": "date" }
    }
  }
}
```

### 2. Mapping — explicit, never dynamic

- **Keyword vs Text**: `keyword` for exact match / aggregations (status, IDs), `text` for full-text search (names, descriptions)
- **Multi-field**: Use `.keyword` sub-field on `text` fields that also need exact match
- **Geo-spatial**: Use `geo_point` for lat/lon queries
- **Date**: Always ISO 8601
- **Numbers**: Use `scaled_float` for prices, `integer`/`long` for counts

```json
{
  "properties": {
    "name": {
      "type": "text",
      "analyzer": "standard",
      "fields": {
        "keyword": { "type": "keyword", "ignore_above": 256 }
      }
    },
    "email": { "type": "keyword", "ignore_above": 256 },
    "tags": { "type": "keyword" },
    "coordinates": { "type": "geo_point" }
  }
}
```

**Never** rely on dynamic mapping in production — it guesses wrong types and cannot be changed without reindex.

### 3. Query performance — filter vs query context

- **Filter context** (`filter`): no scoring → cached → fast. Use for exact matches, ranges, terms.
- **Query context** (`must`, `should`): scoring → not cached. Use only when relevance ranking matters.

```json
// ✅ Efficient — filters are cached, scoring only where needed
{
  "query": {
    "bool": {
      "filter": [
        { "term": { "status": "active" } },
        { "term": { "category_id": "electronics" } },
        { "range": { "created_at": { "gte": "2026-01-01" } } }
      ],
      "must": {
        "multi_match": {
          "query": "wireless headphones",
          "fields": ["name^2", "description"]
        }
      }
    }
  }
}

// ❌ Wasteful — scoring where not needed
{
  "query": {
    "bool": {
      "must": [
        { "term": { "status": "active" } },
        { "term": { "category_id": "electronics" } }
      ]
    }
  }
}
```

### 4. Bulk indexing — always

- Use `_bulk` API (never individual document requests in a loop)
- Disable refresh during large batch imports (`refresh_interval: -1`), restore after
- Optimal bulk size: 5–15 MB per request

```json
// ✅ Bulk indexing
POST _bulk
{ "index": { "_index": "users_v1", "_id": "user_123" } }
{ "name": "Alice Dupont", "email": "alice@example.com", "role": "admin" }
{ "index": { "_index": "users_v1", "_id": "user_124" } }
{ "name": "Bob Martin", "email": "bob@example.com", "role": "user" }
```

### 5. Aliases — mandatory for zero-downtime operations

```json
// ✅ Swap index version seamlessly
POST /_aliases
{
  "actions": [
    { "add":    { "index": "products_v2", "alias": "products" } },
    { "remove": { "index": "products_v1", "alias": "products" } }
  ]
}
```

Application code always queries the **alias**, never the versioned index name.

---

## 📐 Recommended patterns

### Pattern 1: Multi-index search

```json
// ✅ Search across multiple related indices
GET /products,articles,faq/_search
{
  "query": {
    "multi_match": {
      "query": "wireless charging",
      "fields": ["name^2", "description", "title"],
      "type": "best_fields"
    }
  },
  "aggs": {
    "by_index": {
      "terms": { "field": "_index" }
    }
  },
  "size": 20
}
```

### Pattern 2: Geospatial — find nearby results

```json
// ✅ Results within 5 km, sorted by distance
{
  "query": {
    "bool": {
      "filter": [
        {
          "geo_distance": {
            "distance": "5km",
            "location": { "lat": 48.8566, "lon": 2.3522 }
          }
        },
        { "term": { "status": "active" } }
      ]
    }
  },
  "sort": [
    {
      "_geo_distance": {
        "location": { "lat": 48.8566, "lon": 2.3522 },
        "order": "asc",
        "unit": "km"
      }
    }
  ]
}
```

### Pattern 3: Aggregations for dashboards

```json
// ✅ Statistics by category with nested metrics
{
  "size": 0,
  "aggs": {
    "by_category": {
      "terms": { "field": "category_id", "size": 50 },
      "aggs": {
        "by_status": {
          "terms": { "field": "status" }
        },
        "avg_price": {
          "avg": { "field": "price" }
        }
      }
    }
  }
}
```

### Pattern 4: Autocomplete / search-as-you-type

```json
// ✅ Mapping with search_as_you_type
{
  "properties": {
    "name": {
      "type": "search_as_you_type",
      "max_shingle_size": 3
    }
  }
}

// ✅ Query
{
  "query": {
    "multi_match": {
      "query": "wire head",
      "type": "bool_prefix",
      "fields": ["name", "name._2gram", "name._3gram"]
    }
  }
}
```

### Pattern 5: Cursor-based pagination with `search_after`

```json
// ✅ First page
GET /orders/_search
{
  "size": 20,
  "sort": [
    { "created_at": "desc" },
    { "id": "asc" }
  ]
}

// ✅ Next page — use sort values from last hit
GET /orders/_search
{
  "size": 20,
  "sort": [
    { "created_at": "desc" },
    { "id": "asc" }
  ],
  "search_after": ["2026-04-25T10:30:00Z", "order_9876"]
}

// ❌ Never use from+size for deep pagination (> 10,000 hits)
```

### Pattern 6: ISM policy for time-series data

```json
// ✅ Index State Management — auto-rollover + lifecycle
PUT /_plugins/_ism/policies/logs_lifecycle
{
  "policy": {
    "description": "Rotate log indices monthly, delete after 12 months",
    "default_state": "hot",
    "states": [
      {
        "name": "hot",
        "actions": [{ "rollover": { "min_index_age": "30d" } }],
        "transitions": [{ "state_name": "warm", "conditions": { "min_index_age": "30d" } }]
      },
      {
        "name": "warm",
        "actions": [{ "replica_count": { "number_of_replicas": 0 } }],
        "transitions": [{ "state_name": "delete", "conditions": { "min_index_age": "365d" } }]
      },
      {
        "name": "delete",
        "actions": [{ "delete": {} }]
      }
    ],
    "ism_template": [{ "index_patterns": ["logs_*"] }]
  }
}
```

### Pattern 7: Analyzers — language-aware indexing

```json
// ✅ Custom analyzer for French content
PUT /articles_v1
{
  "settings": {
    "analysis": {
      "analyzer": {
        "french_custom": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "french_elision", "french_stop", "french_stemmer"]
        }
      },
      "filter": {
        "french_elision": { "type": "elision", "articles_case": true, "articles": ["l", "m", "t", "qu", "n", "s", "j", "d", "c"] },
        "french_stop": { "type": "stop", "stopwords": "_french_" },
        "french_stemmer": { "type": "stemmer", "language": "light_french" }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": { "type": "text", "analyzer": "french_custom" },
      "body":  { "type": "text", "analyzer": "french_custom" }
    }
  }
}
```

---

## 🚫 Anti-patterns

```
❌ Dynamic mapping in production
   → Guessed types cannot be changed without full reindex

❌ Leading wildcard queries
   { "wildcard": { "name": "*phone*" } }  → Full index scan
   ✅ Use text analyzers + multi_match instead

❌ Unbounded aggregations
   { "terms": { "field": "category_id", "size": 100000 } }  → OOM
   ✅ Always limit (size: 50–100) or use composite aggregation

❌ from+size deep pagination
   { "from": 50000, "size": 20 }  → Max 10,000 hits, very slow
   ✅ Use search_after or scroll API

❌ Individual document indexing in a loop
   ✅ Use _bulk API

❌ Querying versioned index names directly
   GET /products_v3/_search
   ✅ Use aliases: GET /products/_search

❌ Storing binary files / large BLOBs
   ✅ Store in object storage (S3, MinIO), index only metadata + URL

❌ No refresh_interval tuning during bulk import
   ✅ Set to -1 during import, restore to 5s after

❌ Nested queries without nested mapping
   ✅ Must declare "type": "nested" in mapping first

❌ Using text fields for aggregations
   ✅ Use keyword or .keyword sub-field

❌ Ignoring shard distribution / hotspots
   ✅ Monitor with _cat/shards and rebalance
```

---

## 🔒 Security checklist

```
- [ ] Access restricted by IAM policy or network rules
- [ ] TLS 1.2+ enforced for all connections
- [ ] Encryption at rest enabled
- [ ] VPC / private network endpoint (not public-facing)
- [ ] Fine-grained access control (FGAC) enabled
- [ ] Audit logging enabled
- [ ] Index-level permissions enforced per application role
- [ ] Credentials managed via secrets manager (never hardcoded)
- [ ] Connection pooling configured to avoid exhaustion
- [ ] Query rate limiting / circuit breaker configured
```

---

## 📊 Monitoring & debugging

### Key metrics

```
- Search latency: P50, P95, P99
- Indexing rate (docs/sec)
- Shard count & distribution (_cat/shards)
- JVM heap usage (< 75% sustained)
- Thread pool rejections (search, bulk, write)
- Slow query log (threshold: 500ms search, 5s index)
- Cluster health (green / yellow / red)
- Disk watermarks (high: 85%, flood: 95%)
```

### Slow query debugging

```json
// ✅ Enable profiling on a query
{
  "profile": true,
  "query": {
    "multi_match": {
      "query": "search term",
      "fields": ["name^2", "description"]
    }
  }
}
// Response includes timing per phase: rewrite, query, fetch
```

### Common issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Cluster YELLOW | Missing replicas | Check node count ≥ replica_count + 1 |
| Cluster RED | Unassigned primary shards | Check disk space, node health |
| Slow searches | Too many shards / no filters | Reduce shard count, use filter context |
| High memory | Large aggregations / fielddata | Limit aggs size, use `keyword` not `text` for aggs |
| Bulk rejections | Thread pool saturated | Reduce bulk size, add backoff/retry |
| Mapping explosion | Dynamic mapping + varied data | Set `dynamic: strict`, define mappings explicitly |

---

## ✅ Quick checklist

```
- [ ] Explicit mappings defined (keyword vs text vs geo_point)
- [ ] Language analyzer configured for text fields when relevant
- [ ] Sharding aligned with data volume (1 shard / 20–50 GB)
- [ ] Replicas: 1+ in prod, 0 in dev
- [ ] Aliases used (never query versioned index names)
- [ ] Bulk API for all batch operations
- [ ] Filter context for exact matches (cached)
- [ ] search_after for pagination (not from+size)
- [ ] ISM policies for time-series indices
- [ ] Aggregations sized appropriately (max 50–100 buckets)
- [ ] Monitoring configured (latency, heap, shards, slow log)
- [ ] Security hardened (TLS, encryption, access control)
- [ ] Credentials via secrets manager
```
