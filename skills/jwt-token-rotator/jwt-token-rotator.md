---
id: jwt-token-rotator
file_path: skills/jwt-token-rotator/jwt-token-rotator.md
name: JWT Token Rotator
category: backend
tags: [jwt, authentication, token-rotation, security]
author: opencode-core
version: 1.0.0
description: Implement secure short-lived access token renewal and refresh token rotation with revocation blacklisting.
---

# JWT Token Rotator

## Prerequisites & Dependencies
- Node.js 18+ with `npm i jsonwebtoken` and `npm i redis` for blacklist storage
- Understanding of OAuth 2.0 / OpenID Connect flow
- Secure secret management: environment variables, HashiCorp Vault, or AWS Secrets Manager

## Execution Steps
1. Issue a short-lived Access Token (e.g., 15min) and a long-lived Refresh Token (e.g., 30 days) upon login
2. Store each issued Refresh Token's `jti` (JWT ID) in Redis with a TTL matching the token lifetime
3. On every protected route request, validate the Access Token; if `expired`, use the Refresh Token to obtain a new Access Token
4. During rotation: delete the old Refresh Token `jti` from Redis (revocation), issue a new Access Token + new Refresh Token pair
5. Reject refresh requests if the `jti` is already blacklisted or missing (single-use refresh)
6. Implement a background cleanup job to prune stale blacklist entries and enforce maximum refresh token age

```javascript
// JWT rotation with Redis blacklist (Node.js/Express)
const jwt = require('jsonwebtoken');
const Redis = require('ioredis');
const redis = new Redis();

const ACCESS_TOKEN_TTL = 15 * 60;       // 15 minutes
const REFRESH_TOKEN_TTL = 30 * 24 * 60; // 30 days

// Issue tokens
function issueTokens(userId) {
  const access = jwt.sign({ sub: userId, type: 'access' }, process.env.ACCESS_SECRET, { expiresIn: ACCESS_TOKEN_TTL });
  const refresh = jwt.sign({ sub: userId, type: 'refresh', jti: crypto.randomUUID() }, process.env.REFRESH_SECRET, { expiresIn: REFRESH_TOKEN_TTL });
  // Store refresh jti for revocation
  redis.set(refresh.jti, 'revoked', 'EX', REFRESH_TOKEN_TTL);
  return { access, refresh };
}

// Refresh endpoint
app.post('/refresh', async (req, res) => {
  const { refreshToken } = req.body;
  try {
    const payload = jwt.verify(refreshToken, process.env.REFRESH_SECRET) as any;
    // Check revocation
    const isRevoked = await redis.exists(payload.jti);
    if (isRevoked) return res.status(401).json({ error: 'Refresh token revoked' });

    // Issue new tokens + rotate
    const newTokens = issueTokens(payload.sub);
    res.json(newTokens);
  } catch (err) {
    res.status(401).json({ error: 'Invalid refresh token' });
  }
});
```