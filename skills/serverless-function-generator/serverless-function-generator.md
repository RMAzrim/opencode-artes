---
id: serverless-function-generator
name: serverless-function-generator
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: serverless-function-generator
file_path: skills/serverless-function-generator.md
name: Serverless Function Generator
category: cloud
tags: [serverless, lambda, cloudflare-workers, cors, error-handling]
author: opencode-core
version: 1.0.0
description: Scaffold lightweight serverless handlers for Cloudflare Workers or AWS Lambda with standard CORS and error handling.
---

# Serverless Function Generator

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm
- Cloudflare Wrangler (for Workers): `npm i -g wrangler` or AWS SAM/Serverless Framework (for Lambda)
- AWS CLI configured (for Lambda) or a Cloudflare account API token
- Optional: `npm i pino` for structured logging

## Execution Steps
1. Choose your target platform: Cloudflare Workers (JavaScript/TypeScript) or AWS Lambda (Node.js)
2. Scaffold the project: `wrangler init my-worker` (Workers) or `mkdir my-lambda && cd my-lambda`
3. Create the handler file: implement the core function with a consistent signature `(request) => Response`
4. Add standardized CORS headers: `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS`, `Access-Control-Allow-Headers: Content-Type, Authorization`
5. Implement error handling: wrap logic in `try/catch`, return structured JSON error responses with `statusCode` and `body`, and set appropriate HTTP status codes (400, 401, 404, 500)
6. Add health check endpoint: `GET /healthz` that returns `200 OK` with `{ status: "ok" }`
7. Deploy and test: `wrangler publish` (Workers) or `aws lambda create-function` (Lambda), then invoke and verify headers/body

```javascript
// Cloudflare Worker: scaffolded handler with CORS and error handling
export default {
  async fetch(request, env, ctx) {
    // CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 200,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        },
      });
    }

    try {
      const url = new URL(request.url);
      // Health check
      if (url.pathname === '/healthz') {
        return new Response(JSON.stringify({ status: 'ok' }), {
          headers: { 'Content-Type': 'application/json' },
          status: 200,
        });
      }

      // Example route handling
      if (request.method === 'GET' && url.pathname === '/api/time') {
        return new Response(JSON.stringify({ time: new Date().toISOString() }), {
          headers: { 'Content-Type': 'application/json' },
          status: 200,
        });
      }

      // 404 fallback
      return new Response('Not Found', { status: 404 });
    } catch (error) {
      // Structured error response
      return new Response(
        JSON.stringify({ error: 'Internal Server Error', message: error.message }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 500,
        }
      );
    }
  },
};
```

```bash
# Deploy Cloudflare Worker
wrangler publish

# Or deploy AWS Lambda with SAM
sam build
sam deploy --guided
```