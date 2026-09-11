---
id: rate-limiter-middleware
name: rate-limiter-middleware
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: rate-limiter-middleware
file_path: skills/rate-limiter-middleware.md
name: Rate Limiter Middleware
category: backend
tags: [rate-limiting, token-bucket, sliding-window, express, middleware]
author: opencode-core
version: 1.0.0
description: Build API rate-limiting middleware using Token Bucket or Sliding Window algorithms.
---

# Rate Limiter Middleware

## Prerequisites & Dependencies
- Node.js 18+ with Express (or FastAPI, Flask, Go Gin)
- `npm i express-rate-limit` (Token Bucket) or `npm i rate-limit-redis` (distributed Sliding Window)
- Understanding of API throughput requirements and SLA constraints

## Execution Steps
1. Determine the rate limit: e.g., 100 requests per 15 minutes per IP, or 10 requests per minute per API key
2. Choose the algorithm: 
   - **Token Bucket** (fixed window, allows burst up to bucket size)
   - **Sliding Window** (counts requests in a moving time window, more precise)
3. Install and configure the middleware with `max`, `windowMs`, `standardHeaders: true`, `legacyHeaders: false`
4. Apply the middleware globally or per-route: `app.use('/api', limiter)` or `router.get('/strict', limiter, handler)`
5. Add retry-after header on limit exceed and log exceeded events for SLA monitoring
6. Tune limits based on load testing (e.g., `k6`, `artillery`) and observed traffic patterns

```javascript
// Express Token Bucket rate limiter
const rateLimit = require('express-rate-limit');

const globalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  standardHeaders: true, // Return rate limit info in `RateLimit-*` headers
  legacyHeaders: false, // Disable the `X-RateLimit-*` headers
  message: 'Too many requests, please try again later.',
});

app.use('/api', globalLimiter);
app.get('/api/data', (req, res) => res.json({ data: 'hello' }));
```