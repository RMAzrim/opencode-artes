---
id: async-concurrency-handler
file_path: skills/async-concurrency-handler/async-concurrency-handler.md
name: Async Concurrency Handler
category: core-coding
tags: [async, concurrency, promises, worker-threads, goroutines]
author: opencode-core
version: 1.0.0
description: Implement async/await workflows, promise pools, worker threads, or goroutines while preventing race conditions.
---

# Async Concurrency Handler

## Prerequisites & Dependencies
- Node.js 18+ (with Builtin Worker Threads) or Go 1.21+
- `p-limit` or `async-mutex` for promise pooling (Node), `sync.Mutex` for Go
- Familiarity with event loop, promises, or goroutine patterns

## Execution Steps
1. Identify bottlenecks or uncontrolled parallelism in existing async code
2. Choose a concurrency control strategy: fixed-size promise pool, token bucket, or goroutine worker pool
3. Implement the pattern with proper synchronization (mutexes, semaphores, or `p-limit` options)
4. Write unit tests that stress-test the concurrency boundary and detect race conditions (using `pytest-asyncio`/`go test -race`)
5. Profile latency and throughput, adjust pool size or timeout values for optimal performance

```javascript
// Promise pool with p-limit (Node.js)
const pLimit = require('p-limit');

async function processItems(items, concurrency = 5) {
  const limit = pLimit(concurrency);
  const promises = items.map(item => limit(() => heavyCompute(item)));
  const results = await Promise.all(promises);
  return results;
}

async function heavyCompute(x) {
  await new Promise(r => setTimeout(r, 50)); // simulate async work
  return x * 2;
}

// Usage: processItems([1,2,3,4,5], 2) -> runs max 2 at a time
```