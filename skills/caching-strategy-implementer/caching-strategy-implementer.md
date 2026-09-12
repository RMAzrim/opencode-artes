---
id: caching-strategy-implementer
file_path: skills/caching-strategy-implementer/caching-strategy-implementer.md
name: Caching Strategy Implementer
category: backend
tags: [caching, redis, cache-aside, write-through, lru]
author: opencode-core
version: 1.0.0
description: Implement Cache-Aside, Write-Through, and TTL-based caching logic using Redis or in-memory LRU caches.
---

# Caching Strategy Implementer

## Prerequisites & Dependencies
- Redis 7+ strongly recommended, or an in-memory cache (Node `node-cache`, Python `functools.lru_cache`)
- Language runtime: Node.js 18+, Python 3.10+, or Go 1.21+
- Optional: `npm i ioredis` / `pip install redis` / `go-redis` for Redis client

## Execution Steps
1. Choose the caching strategy based on data access patterns: Cache-Aside for read-heavy, Write-Through for write-heavy, TTL/LRU for eviction policies
2. Set up the Redis (or LRU) client with connection pooling and default TTL (e.g., 300s for session data, 86400s for product catalogs)
3. Implement **Cache-Aside**: on read, check cache first; miss → fetch from DB → populate cache; on write → invalidate/update cache entry
4. Implement **Write-Through**: every write goes through cache, which synchronously writes through to the underlying DB
5. Configure eviction policies: `maxmemory-policy allkeys-lru` in Redis, or `maxsize` + `ttl` in Node/Python caches
6. Add cache warming for critical paths and monitor hit/miss ratios via Redis `INFO stats` or Prometheus metrics
7. Benchmark read/write latency with and without cache, iterate TTL/size values

```javascript
// Cache-Aside pattern with ioredis (Node.js)
const Redis = require('ioredis');
const redis = new Redis();

async function getUser(id) {
  const cacheKey = `user:${id}`;
  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached); // cache hit

  // cache miss → fetch from DB
  const user = await db.query('SELECT * FROM users WHERE id = $1', [id]);
  await redis.setex(cacheKey, 300, JSON.stringify(user)); // TTL 5min
  return user;
}

async function createUser(user) {
  const created = await db.query('INSERT INTO users ... RETURNING *');
  await redis.setex(`user:${created.id}`, 300, JSON.stringify(created)); // write-through style
  return created;
}
```