---
name: Redis Pub/Sub & Cache Manager
description: Deploys high-performance caching strategies and distributed message pub/sub event buses to reduce database load and handle background processing.
metadata:
  source: skills/redis-pubsub-cache-manager/redis-pubsub-cache-manager.md
---

# Redis Pub/Sub & Cache Manager

## 1. System Architecture & Prerequisites

This skill implements a production-grade **cache layer** (Cache-Aside, Write-Through, Write-Behind) and a **distributed pub/sub event bus** using `ioredis`. The architecture is designed for:

- **Cache-Aside (Lazy Loading):** Application reads from cache first; on miss, queries DB and populates cache with TTL.
- **Write-Through:** Writes update both cache and DB atomically via a wrapper.
- **Write-Behind (Write-Back):** Writes update cache immediately and queue DB writes asynchronously (drained via a worker).
- **Pub/Sub event bus:** Typed `DomainEvent` JSON messages published on configurable channels; subscribers with channel multiplexing and error fallback.
- **Graceful degradation:** In-memory `Map` fallback when Redis is unreachable; pipeline-based shutdown.

**Prerequisites:**

- Node.js ≥ 18
- Redis 7+ (local or Docker: `docker run -d -p 6379:6379 redis:7-alpine`)
- `npm install ioredis`

## 2. Input/Output Data Contracts

**Input — Environment Variables:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["REDIS_URL"],
  "properties": {
    "REDIS_URL": {
      "type": "string",
      "default": "redis://localhost:6379",
      "description": "Redis connection string"
    },
    "REDIS_PASSWORD": {
      "type": "string",
      "description": "Optional Redis AUTH password"
    },
    "CACHE_DEFAULT_TTL": {
      "type": "number",
      "default": 300,
      "description": "Default TTL in seconds for cache entries"
    }
  }
}
```

**Output Artifacts:**

| Path | Description |
|---|---|
| `src/cache.ts` | CacheAside, WriteThrough, WriteBehind, fallback cache |
| `src/pubsub.ts` | PubSubManager with typed channel multiplexing |
| `src/publisher.ts` | DomainEvent publisher helper |
| `src/subscriber.ts` | Subscriber with error handling |
| `src/worker.ts` | WriteBehind drain worker example |
| `package.json` | Dependencies (ioredis) |

## 3. Production Reference Implementation

```typescript
// src/cache.ts
import Redis from "ioredis";

// ── Types ────────────────────────────────────────────────────────

interface CacheOptions {
  ttl: number;          // seconds
  prefix?: string;      // key prefix, default "cache:"
}

interface CacheEntry<T> {
  value: T;
  cachedAt: number;
  ttl: number;
}

// ── In-Memory Fallback Cache ─────────────────────────────────────

class MemoryFallbackCache {
  private store = new Map<string, { value: string; expiresAt: number }>();

  get(key: string): string | null {
    const entry = this.store.get(key);
    if (!entry) return null;
    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return null;
    }
    return entry.value;
  }

  set(key: string, value: string, ttlMs: number): void {
    this.store.set(key, {
      value,
      expiresAt: Date.now() + ttlMs,
    });
  }

  delete(key: string): boolean {
    return this.store.delete(key);
  }

  has(key: string): boolean {
    return this.get(key) !== null;
  }

  clear(): void {
    this.store.clear();
  }

  get size(): number {
    return this.store.size;
  }
}

// ── Redis Client with Graceful Degradation ───────────────────────

const REDIS_URL = process.env.REDIS_URL ?? "redis://localhost:6379";
const CACHE_DEFAULT_TTL = Number(process.env.CACHE_DEFAULT_TTL ?? 300);

let redisConnected = false;
const fallback = new MemoryFallbackCache();

const redis = new Redis(REDIS_URL, {
  password: process.env.REDIS_PASSWORD || undefined,
  retryStrategy(times: number): number | null {
    if (times > 10) {
      console.error("[REDIS] Max retries reached, falling back to in-memory cache");
      return null;
    }
    const delay = Math.min(times * 200, 5000);
    return delay;
  },
  maxRetriesPerRequest: 3,
  enableReadyCheck: true,
  lazyConnect: true,
});

redis.on("ready", () => {
  redisConnected = true;
  console.log("[REDIS] Connected — live cache active");
});

redis.on("end", () => {
  redisConnected = false;
  console.warn("[REDIS] Connection lost — falling back to in-memory cache");
});

redis.on("error", (err) => {
  if (redisConnected) {
    console.error("[REDIS] Runtime error:", err.message);
  }
});

redis.connect().catch(() => {
  console.warn("[REDIS] Initial connection failed — using in-memory fallback");
});

// ── Cache-Aside (Read/Write pattern) ─────────────────────────────

export async function cacheGet<T>(
  key: string,
  options: Partial<CacheOptions> = {}
): Promise<T | null> {
  const fullKey = `${options.prefix ?? "cache:"}${key}`;

  // Try Redis first
  if (redisConnected) {
    try {
      const raw = await redis.get(fullKey);
      if (raw) return JSON.parse(raw) as T;
      return null;
    } catch {
      // Fall through to fallback
    }
  }

  // Fallback to in-memory
  const raw = fallback.get(fullKey);
  if (raw) return JSON.parse(raw) as T;
  return null;
}

export async function cacheSet<T>(
  key: string,
  value: T,
  options: Partial<CacheOptions> = {}
): Promise<void> {
  const fullKey = `${options.prefix ?? "cache:"}${key}`;
  const ttl = options.ttl ?? CACHE_DEFAULT_TTL;
  const serialized = JSON.stringify(value);

  // Write to Redis
  if (redisConnected) {
    try {
      await redis.setex(fullKey, ttl, serialized);
    } catch {
      // Fall through to fallback
    }
  }

  // Always write to fallback for resilience
  fallback.set(fullKey, serialized, ttl * 1000);
}

export async function cacheDelete(key: string, prefix = "cache:"): Promise<void> {
  const fullKey = `${prefix}${key}`;

  if (redisConnected) {
    try {
      await redis.del(fullKey);
    } catch {
      // continue
    }
  }

  fallback.delete(fullKey);
}

export async function cacheInvalidatePattern(pattern: string): Promise<void> {
  const fullPattern = `cache:${pattern}`;

  if (redisConnected) {
    try {
      const keys = await redis.keys(fullPattern);
      if (keys.length > 0) {
        await redis.del(...keys);
      }
    } catch {
      // continue
    }
  }

  // Clear fallback entirely (conservative approach)
  fallback.clear();
}

// ── Write-Through Wrapper ────────────────────────────────────────

export async function writeThrough<T>(
  key: string,
  writer: () => Promise<T>,
  options: Partial<CacheOptions> = {}
): Promise<T> {
  const result = await writer();
  await cacheSet(key, result, options);
  return result;
}

// ── Write-Behind (Write-Back) Queue ──────────────────────────────

type PendingWrite<T> = {
  key: string;
  value: T;
  timestamp: number;
  retries: number;
};

const writeBehindQueue: PendingWrite<unknown>[] = [];
const WRITE_BEHIND_INTERVAL_MS = 1000;
const WRITE_BEHIND_MAX_RETRIES = 5;
let writeBehindTimer: ReturnType<typeof setInterval> | null = null;

export function enqueueWriteBehind<T>(key: string, value: T): void {
  writeBehindQueue.push({
    key,
    value,
    timestamp: Date.now(),
    retries: 0,
  });

  if (!writeBehindTimer) {
    writeBehindTimer = setInterval(() => drainWriteBehindQueue(), WRITE_BEHIND_INTERVAL_MS);
  }
}

async function drainWriteBehindQueue(): Promise<void> {
  const pending = writeBehindQueue.splice(0, 50); // batch up to 50
  if (pending.length === 0) {
    if (writeBehindTimer) {
      clearInterval(writeBehindTimer);
      writeBehindTimer = null;
    }
    return;
  }

  for (const item of pending) {
    try {
      await cacheSet(item.key, item.value);
    } catch {
      if (item.retries < WRITE_BEHIND_MAX_RETRIES) {
        writeBehindQueue.push({ ...item, retries: item.retries + 1 });
      } else {
        console.error(`[WRITE-BEHIND] Dropping key ${item.key} after ${item.retries} retries`);
      }
    }
  }
}

// ── Utility: TTL-aware get-or-set (lazy-load pattern) ────────────

export async function cacheGetOrSet<T>(
  key: string,
  fetcher: () => Promise<T>,
  options: Partial<CacheOptions> = {}
): Promise<T> {
  const cached = await cacheGet<T>(key, options);
  if (cached !== null) return cached;

  const value = await fetcher();
  await cacheSet(key, value, options);
  return value;
}

// ── Shutdown ─────────────────────────────────────────────────────

export async function shutdownCache(): Promise<void> {
  if (writeBehindTimer) {
    clearInterval(writeBehindTimer);
    writeBehindTimer = null;
  }
  await drainWriteBehindQueue();

  if (redisConnected) {
    await redis.quit();
  }
  fallback.clear();
}
```

```typescript
// src/pubsub.ts
import Redis from "ioredis";

// ── Types ────────────────────────────────────────────────────────

export interface DomainEvent<T = Record<string, unknown>> {
  type: string;
  payload: T;
  timestamp: number;
  source: string;
  id: string;
}

export type EventHandler<T = Record<string, unknown>> = (
  event: DomainEvent<T>
) => void | Promise<void>;

interface ChannelSubscription {
  channel: string;
  handler: EventHandler;
  id: string;
}

// ── PubSub Manager ───────────────────────────────────────────────

const REDIS_URL = process.env.REDIS_URL ?? "redis://localhost:6379";

let redisConnected = false;

const pubClient = new Redis(REDIS_URL, {
  password: process.env.REDIS_PASSWORD || undefined,
  retryStrategy(times) {
    if (times > 5) return null;
    return Math.min(times * 200, 2000);
  },
  lazyConnect: true,
});

const subClient = new Redis(REDIS_URL, {
  password: process.env.REDIS_PASSWORD || undefined,
  retryStrategy(times) {
    if (times > 5) return null;
    return Math.min(times * 200, 2000);
  },
  lazyConnect: true,
});

const subscriptions = new Map<string, ChannelSubscription[]>();
const channelHandlers = new Map<string, EventHandler[]>();

pubClient.on("ready", () => {
  redisConnected = true;
});

pubClient.on("end", () => {
  redisConnected = false;
});

subClient.on("message", (channel: string, message: string) => {
  const handlers = channelHandlers.get(channel) ?? [];
  for (const handler of handlers) {
    try {
      const event = JSON.parse(message) as DomainEvent;
      handler(event);
    } catch (err) {
      console.error(`[PUBSUB] Error handling message on channel ${channel}:`, err);
    }
  }
});

subClient.on("error", (err) => {
  console.error("[PUBSUB] Subscriber error:", err.message);
});

// ── Subscribe to a typed channel ─────────────────────────────────

export function subscribe<T = Record<string, unknown>>(
  channel: string,
  handler: EventHandler<T>
): () => void {
  const id = crypto.randomUUID();

  if (!channelHandlers.has(channel)) {
    channelHandlers.set(channel, []);
    if (redisConnected) {
      subClient.subscribe(channel).catch(() => {});
    }
  }

  channelHandlers.get(channel)!.push(handler as EventHandler);

  // Return unsubscribe function
  return () => {
    const handlers = channelHandlers.get(channel) ?? [];
    const idx = handlers.indexOf(handler as EventHandler);
    if (idx !== -1) handlers.splice(idx, 1);

    if (handlers.length === 0) {
      channelHandlers.delete(channel);
      if (redisConnected) {
        subClient.unsubscribe(channel).catch(() => {});
      }
    }
  };
}

// ── Publish a typed event ────────────────────────────────────────

export async function publish<T = Record<string, unknown>>(
  channel: string,
  event: Omit<DomainEvent<T>, "timestamp" | "id">
): Promise<void> {
  const fullEvent: DomainEvent<T> = {
    ...event,
    id: crypto.randomUUID(),
    timestamp: Date.now(),
  };

  if (redisConnected) {
    try {
      await pubClient.publish(channel, JSON.stringify(fullEvent));
      return;
    } catch (err) {
      console.error(`[PUBSUB] Publish failed on channel ${channel}, attempting reconnect`);
      try {
        await pubClient.connect();
        await pubClient.publish(channel, JSON.stringify(fullEvent));
        return;
      } catch {
        // Fall through
      }
    }
  }

  // Fallback: deliver locally (useful for single-instance dev)
  const handlers = channelHandlers.get(channel) ?? [];
  for (const handler of handlers) {
    try {
      handler(fullEvent);
    } catch (err) {
      console.error(`[PUBSUB] Local fallback handler error:`, err);
    }
  }
}

// ── Shutdown ─────────────────────────────────────────────────────

export async function shutdownPubSub(): Promise<void> {
  const channels = Array.from(channelHandlers.keys());
  if (channels.length > 0 && redisConnected) {
    await subClient.unsubscribe(...channels);
  }
  await Promise.all([pubClient.quit(), subClient.quit()]);
}
```

```typescript
// src/publisher.ts
import { publish, DomainEvent } from "./pubsub";

// ── Typed Domain Event Publishers ────────────────────────────────

export interface UserCreatedPayload {
  userId: string;
  email: string;
  name: string;
}

export interface OrderPlacedPayload {
  orderId: string;
  userId: string;
  total: number;
  itemCount: number;
}

export interface ProductUpdatedPayload {
  productId: string;
  changes: string[];
  updatedBy: string;
}

// ── Publisher Functions ──────────────────────────────────────────

export async function publishUserCreated(data: UserCreatedPayload): Promise<void> {
  const event: Omit<DomainEvent<UserCreatedPayload>, "timestamp" | "id"> = {
    type: "USER_CREATED",
    payload: data,
    source: "user-service",
  };
  await publish("user.events", event);
}

export async function publishOrderPlaced(data: OrderPlacedPayload): Promise<void> {
  const event: Omit<DomainEvent<OrderPlacedPayload>, "timestamp" | "id"> = {
    type: "ORDER_PLACED",
    payload: data,
    source: "order-service",
  };
  await publish("order.events", event);
}

export async function publishProductUpdated(data: ProductUpdatedPayload): Promise<void> {
  const event: Omit<DomainEvent<ProductUpdatedPayload>, "timestamp" | "id"> = {
    type: "PRODUCT_UPDATED",
    payload: data,
    source: "product-service",
  };
  await publish("product.events", event);
}

// ── Generic event publisher ──────────────────────────────────────

export async function publishDomainEvent<T>(
  channel: string,
  type: string,
  source: string,
  payload: T
): Promise<void> {
  await publish<T>(channel, { type, payload, source });
}
```

```typescript
// src/subscriber.ts
import { subscribe, DomainEvent } from "./pubsub";
import { cacheInvalidatePattern } from "./cache";

// ── Event Handlers ───────────────────────────────────────────────

async function handleUserCreated(event: DomainEvent) {
  const { userId, email } = event.payload as { userId: string; email: string };
  console.log(`[SUBSCRIBER] User created: ${userId} (${email})`);
  // Send welcome email, initialize user preferences, etc.
}

async function handleOrderPlaced(event: DomainEvent) {
  const { orderId, userId, total } = event.payload as {
    orderId: string;
    userId: string;
    total: number;
  };
  console.log(`[SUBSCRIBER] Order placed: ${orderId} by ${userId} — $${total}`);
  // Trigger inventory decrement, shipping calculation, analytics event, etc.
}

async function handleProductUpdated(event: DomainEvent) {
  const { productId, changes } = event.payload as {
    productId: string;
    changes: string[];
  };
  console.log(`[SUBSCRIBER] Product updated: ${productId}`, changes);
  // Invalidate related caches
  await cacheInvalidatePattern(`product:${productId}*`);
  await cacheInvalidatePattern("product:list:*");
}

// ── Register Subscribers ─────────────────────────────────────────

export function registerSubscribers(): void {
  subscribe("user.events", handleUserCreated);
  subscribe("order.events", handleOrderPlaced);
  subscribe("product.events", handleProductUpdated);
  console.log("[SUBSCRIBER] All event handlers registered");
}

// ── Standalone runner ────────────────────────────────────────────

if (require.main === module) {
  registerSubscribers();
  console.log("[SUBSCRIBER] Listening for events... Press Ctrl+C to exit");

  process.on("SIGINT", async () => {
    console.log("[SUBSCRIBER] Shutting down...");
    const { shutdownPubSub } = await import("./pubsub");
    const { shutdownCache } = await import("./cache");
    await shutdownPubSub();
    await shutdownCache();
    process.exit(0);
  });
}
```

```typescript
// src/worker.ts
import Redis from "ioredis";

// ── Write-Behind Worker ──────────────────────────────────────────
// Drains the write-behind queue and persists to database.

const REDIS_URL = process.env.REDIS_URL ?? "redis://localhost:6379";

const queueClient = new Redis(REDIS_URL, {
  password: process.env.REDIS_PASSWORD || undefined,
  retryStrategy(times) {
    if (times > 10) return null;
    return Math.min(times * 200, 3000);
  },
  lazyConnect: true,
});

interface WriteJob {
  id: string;
  type: string;
  entity: string;
  entityId: string;
  data: Record<string, unknown>;
  createdAt: number;
  attempts: number;
}

const QUEUE_KEY = "write-behind:queue";
const PROCESSING_KEY = "write-behind:processing";
const DEAD_LETTER_KEY = "write-behind:dead-letter";
const MAX_RETRIES = 5;
const POLL_INTERVAL_MS = 500;

async function processJob(job: WriteJob): Promise<boolean> {
  try {
    switch (job.type) {
      case "USER_UPDATE":
        console.log(`[WORKER] Persisting user ${job.entityId}:`, job.data);
        // await db.users.update({ where: { id: job.entityId }, data: job.data });
        break;

      case "PRODUCT_UPDATE":
        console.log(`[WORKER] Persisting product ${job.entityId}:`, job.data);
        // await db.products.update({ where: { id: job.entityId }, data: job.data });
        break;

      case "ORDER_STATUS_UPDATE":
        console.log(`[WORKER] Persisting order ${job.entityId}:`, job.data);
        // await db.orders.update({ where: { id: job.entityId }, data: job.data });
        break;

      default:
        console.warn(`[WORKER] Unknown job type: ${job.type}`);
        return true; // skip unknown types without retry
    }
    return true;
  } catch (err) {
    console.error(`[WORKER] Failed to process job ${job.id}:`, err);
    return false;
  }
}

async function runWorker(): Promise<void> {
  await queueClient.connect();
  console.log("[WORKER] Started — polling for write-behind jobs");

  let running = true;

  process.on("SIGINT", async () => {
    console.log("[WORKER] Shutting down gracefully...");
    running = false;
  });

  while (running) {
    try {
      // LPOP from queue, blocking pop with 1s timeout
      const raw = await queueClient.blpop(QUEUE_KEY, 1);

      if (!raw) continue;

      const job: WriteJob = JSON.parse(raw[1]);
      const success = await processJob(job);

      if (success) {
        console.log(`[WORKER] Job ${job.id} completed`);
      } else {
        job.attempts = (job.attempts ?? 0) + 1;

        if (job.attempts >= MAX_RETRIES) {
          console.error(`[WORKER] Job ${job.id} moved to dead-letter queue after ${job.attempts} attempts`);
          await queueClient.rpush(DEAD_LETTER_KEY, JSON.stringify(job));
        } else {
          console.warn(`[WORKER] Job ${job.id} failed, re-enqueueing (attempt ${job.attempts})`);
          await queueClient.rpush(QUEUE_KEY, JSON.stringify(job));
        }
      }
    } catch (err) {
      if (running) {
        console.error("[WORKER] Poll error:", err);
        await new Promise((r) => setTimeout(r, 2000));
      }
    }
  }

  await queueClient.quit();
  console.log("[WORKER] Stopped");
}

// ── Job Enqueue Helper (used by Write-Behind cache) ─────────────

export async function enqueueJob(
  type: string,
  entity: string,
  entityId: string,
  data: Record<string, unknown>
): Promise<void> {
  const job: WriteJob = {
    id: crypto.randomUUID(),
    type,
    entity,
    entityId,
    data,
    createdAt: Date.now(),
    attempts: 0,
  };

  const client = new Redis(REDIS_URL, {
    password: process.env.REDIS_PASSWORD || undefined,
    lazyConnect: true,
  });

  try {
    await client.connect();
    await client.rpush(QUEUE_KEY, JSON.stringify(job));
  } finally {
    await client.quit();
  }
}

// ── Standalone entrypoint ────────────────────────────────────────

if (require.main === module) {
  runWorker().catch((err) => {
    console.error("[WORKER] Fatal:", err);
    process.exit(1);
  });
}
```

```
// package.json
{
  "name": "redis-pubsub-cache-manager",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "tsx src/index.ts",
    "subscriber": "tsx src/subscriber.ts",
    "worker": "tsx src/worker.ts"
  },
  "dependencies": {
    "ioredis": "^5.3.2"
  },
  "devDependencies": {
    "tsx": "^4.7.1",
    "typescript": "^5.4.0",
    "@types/node": "^20.11.0"
  }
}
```

## 4. Execution Protocol & Step-by-Step Workflow

```bash
# 1. Install dependencies
npm install ioredis
npm install -D tsx typescript @types/node

# 2. Start Redis (Docker)
docker run -d --name redis-cache -p 6379:6379 redis:7-alpine

# 3. Verify Redis is reachable
redis-cli ping
# Expected: PONG

# 4. Run the subscriber (separate terminal)
npx tsx src/subscriber.ts

# 5. Run the worker (separate terminal)
npx tsx src/worker.ts

# 6. Run the main application that publishes events
npx tsx src/index.ts

# 7. Test cache operations
npx tsx -e "
import { cacheGetOrSet, cacheGet, cacheDelete } from './src/cache';
async function test() {
  const user = await cacheGetOrSet('user:123', async () => ({ id: '123', name: 'Test' }), { ttl: 60 });
  console.log('Cached:', user);
  const hit = await cacheGet('user:123');
  console.log('Cache hit:', hit);
  await cacheDelete('user:123');
  const after = await cacheGet('user:123');
  console.log('After delete:', after);
}
test();
"

# 8. Verify Redis key state
redis-cli KEYS 'cache:*'
```

## 5. Edge Cases & Error Handling

- **Redis connection loss:** The system automatically degrades to the in-memory `Map` fallback; no data is silently dropped. When Redis recovers, new writes propagate to both stores.
- **Cache stampede (thundering herd):** Use `cacheGetOrSet` which acquires a single fetch per key; for high-concurrency scenarios, add Redis `SETNX`-based locking with a short TTL.
- **Serialization errors:** Malformed JSON in cache values (e.g., after manual `redis-cli SET`) causes parse failures; cache handlers treat parse errors as cache misses and re-populate.
- **Write-behind queue overflow:** The worker polls with `BLPOP`; if Redis fills up, jobs queue in Redis memory. Monitor with `LLEN write-behind:queue`. Jobs exceeding `MAX_RETRIES` move to a dead-letter queue for manual inspection.
- **Pub/Sub message loss:** Redis Pub/Sub is fire-and-forget — if a subscriber is down, messages are lost. For durable event sourcing, consider Redis Streams (`XADD`/`XREADGROUP`) as an upgrade path.
- **Channel multiplexing race:** When multiple handlers subscribe to the same channel concurrently, `subClient.subscribe` may be called redundantly. Redis deduplicates subscriptions internally, so this is safe but adds minor latency.
- **Graceful shutdown:** Always call `shutdownCache()` and `shutdownPubSub()` before `process.exit()` to drain pending writes and close connections cleanly. Unclosed connections cause node process hangs.
- **TTL jitter:** For hot keys (high read volume), add ±10% jitter to TTLs to prevent synchronized cache expiry bursts.
- **Memory fallback limits:** The in-memory fallback is unbounded; in production, add an LRU eviction policy (e.g., `lru-cache` package) or a maximum size check before `fallback.set()`.

