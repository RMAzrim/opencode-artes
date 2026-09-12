---
id: auth-session-oauth2-scaffolder
file_path: skills/auth-session-oauth2-scaffolder/auth-session-oauth2-scaffolder.md
name: Auth Session & OAuth2 Scaffolder
category: backend
tags: [authentication, oauth2, jwt, argon2]
author: opencode-core
version: 1.0.0
description: Implements comprehensive user authentication systems supporting secure cookie sessions, JWT refresh token rotation, password hashing, and third-party OAuth2 social logins.
---

# Auth Session & OAuth2 Scaffolder

## 1. System Architecture & Prerequisites

- Node.js >= 18 LTS (runtime), npm >= 9, TypeScript >= 5.5, `ts-node-dev@^2.0.0` for watch mode.
- Core deps: `express@^4.19.2`, `argon2@^0.41.1` (Argon2id), `jsonwebtoken@^9.0.2`, `cookie-parser@^1.4.6`, `redis@^4.7.0`, `pg@^8.12.0`, `nodemailer@^6.9.14`, `passport@^0.7.0`, `passport-google-oauth20@^2.0.0`, `passport-github2@^0.1.12`, `zod@^3.23.8`, `helmet@^7.1.0`, `cors@^2.8.5`, `dotenv@^16.4.5`.
- Infrastructure: PostgreSQL >= 14 (schema auto-created by `initDb()`), Redis >= 6 (refresh-token blacklist + optional revocation state).
- `argon2` ships prebuilt binaries via node-pre-gyp; if a native build is forced, a C++ toolchain (Visual Studio Build Tools) is required on Windows or `build-essential` on Linux.
- The JWT access secret and refresh secret are hard-required (min 32 chars) by the config loader; the server refuses to boot without them.

## 2. Input/Output Data Contracts

### Request payloads (JSON)

- `POST /register` → `{"email": string(email), "password": string(8..72), "displayName": string(1..64)}` → 201 `{success, data:{user, requiresEmailVerification}}`.
- `POST /login` → `{"email": string(email), "password": string}` → 200 `{success, data:{user}}` + sets `access_token`/`refresh_token` cookies.
- `POST /refresh` (no body) → reads `refresh_token` cookie → rotates token, sets new cookies → 200.
- `POST /logout` (no body) → revokes refresh token + clears cookies → 200.
- `POST /forgot-password` → `{"email"}` → always 200 (no user enumeration).
- `POST /reset-password` → `{"token": string, "password": string(8..72)}` → 200, signs the user in.
- `POST /verify-email` → `{"token"}` → 200.
- `GET /me` (Bearer or cookie) → `{success, data:{userId, email, displayName, emailVerified}}`.

### Cookie contract

- `access_token`: HTTP-only, `SameSite=Strict`, `Secure` in prod, path `/`, TTL 15m.
- `refresh_token`: HTTP-only, `SameSite=Strict`, `Secure` in prod, path `/api/auth` (scoped so it is only sent to auth endpoints), TTL 7d.
- OAuth2: `GET /api/auth/google`, `GET /api/auth/github` initiate flows; `/api/auth/google/callback`, `/api/auth/github/callback` receive redirects, create/link accounts, and issue the same cookie pair.

### Output artifact paths

- `skills/auth-session-oauth2-scaffolder/package.json`, `tsconfig.json`, `.env.example`
- `src/config.ts`, `src/db.ts`, `src/redis.ts`, `src/mailer.ts`, `src/errors.ts`, `src/types.ts`
- `src/auth.service.ts`, `src/auth.middleware.ts`, `src/auth.routes.ts`, `src/oauth.routes.ts`, `src/server.ts`

## 3. Production Reference Implementation

```text
# .env.example
NODE_ENV=development
PORT=4000
DATABASE_URL=postgres://postgres:postgres@localhost:5432/authdb
REDIS_URL=redis://127.0.0.1:6379
CORS_ORIGIN=http://localhost:3000
JWT_ACCESS_SECRET=change-me-at-least-32-chars-long-access
JWT_REFRESH_SECRET=change-me-at-least-32-chars-long-refresh
ACCESS_TOKEN_TTL=15m
REFRESH_TOKEN_TTL_SECONDS=604800
COOKIE_DOMAIN=
EMAIL_FROM=no-reply@example.com
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
OAUTH_REDIRECT_BASE=http://localhost:4000
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
REQUIRE_EMAIL_VERIFICATION=false
```

```json
// package.json
{
  "name": "auth-session-oauth2",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "ts-node-dev --respawn src/server.ts",
    "build": "tsc -p tsconfig.json",
    "start": "node dist/server.js"
  },
  "dependencies": {
    "argon2": "^0.41.1",
    "cookie-parser": "^1.4.6",
    "cors": "^2.8.5",
    "dotenv": "^16.4.5",
    "express": "^4.19.2",
    "helmet": "^7.1.0",
    "jsonwebtoken": "^9.0.2",
    "nodemailer": "^6.9.14",
    "passport": "^0.7.0",
    "passport-github2": "^0.1.12",
    "passport-google-oauth20": "^2.0.0",
    "pg": "^8.12.0",
    "redis": "^4.7.0",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/cookie-parser": "^1.4.7",
    "@types/cors": "^2.8.17",
    "@types/express": "^4.17.21",
    "@types/jsonwebtoken": "^9.0.6",
    "@types/node": "^20.14.9",
    "@types/nodemailer": "^6.4.15",
    "@types/passport": "^1.0.16",
    "@types/passport-github2": "^1.2.8",
    "@types/passport-google-oauth20": "^2.0.16",
    "@types/pg": "^8.11.6",
    "ts-node-dev": "^2.0.0",
    "typescript": "^5.5.2"
  }
}
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "moduleResolution": "node",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "sourceMap": true
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

```typescript
// src/types.ts
export interface User {
  id: string;
  email: string;
  password_hash: string | null;
  display_name: string;
  email_verified_at: string | null;
  created_at: string;
}

export interface RefreshTokenRow {
  jti: string;
  user_id: string;
  rotation_count: number;
  expires_at: string;
  created_at: string;
  revoked_at: string | null;
}

export interface AuthenticatedUser {
  userId: string;
  email: string;
  displayName: string;
}
```

```typescript
// src/config.ts
import { z } from 'zod';

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().int().default(4000),
  DATABASE_URL: z.string().default('postgres://postgres:postgres@localhost:5432/authdb'),
  REDIS_URL: z.string().default('redis://127.0.0.1:6379'),
  CORS_ORIGIN: z.string().optional(),
  JWT_ACCESS_SECRET: z.string().min(32),
  JWT_REFRESH_SECRET: z.string().min(32),
  ACCESS_TOKEN_TTL: z.string().default('15m'),
  REFRESH_TOKEN_TTL_SECONDS: z.coerce.number().int().default(7 * 24 * 60 * 60),
  COOKIE_DOMAIN: z.string().optional(),
  EMAIL_FROM: z.string().default('no-reply@example.com'),
  SMTP_HOST: z.string().optional(),
  SMTP_PORT: z.coerce.number().int().default(587),
  SMTP_USER: z.string().optional(),
  SMTP_PASS: z.string().optional(),
  OAUTH_REDIRECT_BASE: z.string().default('http://localhost:4000'),
  GOOGLE_CLIENT_ID: z.string().optional(),
  GOOGLE_CLIENT_SECRET: z.string().optional(),
  GITHUB_CLIENT_ID: z.string().optional(),
  GITHUB_CLIENT_SECRET: z.string().optional(),
  REQUIRE_EMAIL_VERIFICATION: z.coerce.boolean().default(false)
});

const parsed = envSchema.safeParse(process.env);
if (!parsed.success) {
  console.error('[config] invalid environment', JSON.stringify(parsed.error.flatten(), null, 2));
  process.exit(1);
}

export interface Config extends z.infer<typeof envSchema> {
  isProd: boolean;
}

export const config: Config = { ...parsed.data, isProd: parsed.data.NODE_ENV === 'production' };
```

```typescript
// src/db.ts
import { Pool } from 'pg';

export const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 10,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000
});

pool.on('error', (err) => {
  console.error('[pg] idle client error', err);
});

export async function query<T extends Record<string, unknown> = Record<string, unknown>>(
  text: string,
  params: unknown[] = []
): Promise<T[]> {
  const result = await pool.query<T>(text, params);
  return result.rows;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT,
  display_name TEXT NOT NULL,
  email_verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS oauth_accounts (
  provider TEXT NOT NULL,
  provider_account_id TEXT NOT NULL,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  access_token TEXT,
  refresh_token TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (provider, provider_account_id),
  UNIQUE (user_id, provider)
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  jti UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rotation_count INT NOT NULL DEFAULT 0,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_refresh_tokens_active
  ON refresh_tokens (user_id) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS email_verification_tokens (
  token_hash TEXT PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  token_hash TEXT PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ
);
`;

export async function initDb(): Promise<void> {
  await pool.query(SCHEMA);
}
```

```typescript
// src/redis.ts
import { createClient } from 'redis';

export const redis = createClient({
  url: process.env.REDIS_URL ?? 'redis://127.0.0.1:6379'
});

redis.on('error', (err) => {
  console.error('[redis] client error', err);
});

export async function connectRedis(): Promise<void> {
  if (!redis.isOpen) {
    await redis.connect();
  }
}
```

```typescript
// src/mailer.ts
import nodemailer from 'nodemailer';
import { config } from './config';

const transporter = nodemailer.createTransport({
  host: config.SMTP_HOST ?? 'localhost',
  port: config.SMTP_PORT,
  secure: config.isProd && config.SMTP_PORT === 465,
  auth: config.SMTP_USER && config.SMTP_PASS ? { user: config.SMTP_USER, pass: config.SMTP_PASS } : undefined
});

export interface MailPayload {
  to: string;
  subject: string;
  text: string;
  html?: string;
}

export async function sendMail(payload: MailPayload): Promise<void> {
  if (config.NODE_ENV === 'development' || config.NODE_ENV === 'test') {
    console.log('[mailer][stub]', JSON.stringify({ from: config.EMAIL_FROM, ...payload }));
    return;
  }
  await transporter.sendMail({ from: config.EMAIL_FROM, ...payload });
}
```

```typescript
// src/errors.ts
import type { NextFunction, Request, Response } from 'express';

export class AppError extends Error {
  public readonly statusCode: number;
  public readonly code: string;
  public readonly details?: unknown;

  constructor(statusCode: number, code: string, message: string, details?: unknown) {
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    Error.captureStackTrace(this, this.constructor);
  }

  public static badRequest(message: string, details?: unknown): AppError {
    return new AppError(400, 'BAD_REQUEST', message, details);
  }

  public static unauthorized(message = 'Unauthorized'): AppError {
    return new AppError(401, 'UNAUTHORIZED', message);
  }

  public static conflict(message: string): AppError {
    return new AppError(409, 'CONFLICT', message);
  }

  public static internal(message = 'Internal server error'): AppError {
    return new AppError(500, 'INTERNAL_ERROR', message);
  }
}

export function notFoundHandler(req: Request, _res: Response, next: NextFunction): void {
  next(new AppError(404, 'NOT_FOUND', `Route ${req.method} ${req.originalUrl} not found`));
}

export function errorHandler(err: unknown, _req: Request, res: Response, next: NextFunction): void {
  if (res.headersSent) {
    next(err);
    return;
  }
  if (err instanceof AppError) {
    res.status(err.statusCode).json({
      success: false,
      error: {
        code: err.code,
        message: err.message,
        ...(err.details === undefined ? {} : { details: err.details })
      }
    });
    return;
  }
  const normalized = err instanceof SyntaxError ? AppError.badRequest('Malformed JSON body') : AppError.internal();
  console.error('[error]', err);
  res.status(normalized.statusCode).json({
    success: false,
    error: { code: normalized.code, message: normalized.message }
  });
}
```

```typescript
// src/auth.middleware.ts
import type { NextFunction, Request, Response } from 'express';
import jwt from 'jsonwebtoken';
import { config } from './config';
import { AppError } from './errors';
import type { AuthenticatedUser } from './types';

export interface AuthenticatedRequest extends Request {
  user: AuthenticatedUser;
}

export function extractAccessToken(req: Request): string | null {
  const header = req.headers.authorization;
  if (header && header.startsWith('Bearer ')) return header.slice(7);
  const cookie = req.cookies?.['access_token'];
  return typeof cookie === 'string' ? cookie : null;
}

export function requireAuth(req: AuthenticatedRequest, _res: Response, next: NextFunction): void {
  const token = extractAccessToken(req);
  if (!token) {
    return next(AppError.unauthorized('Missing access token'));
  }

  let payload: { sub?: string; email?: string; displayName?: string; type?: string };
  try {
    payload = jwt.verify(token, config.JWT_ACCESS_SECRET) as typeof payload;
  } catch {
    return next(AppError.unauthorized('Invalid or expired access token'));
  }

  if (payload.type !== 'access' || typeof payload.sub !== 'string') {
    return next(AppError.unauthorized('Invalid token type'));
  }

  req.user = {
    userId: payload.sub,
    email: payload.email ?? '',
    displayName: payload.displayName ?? ''
  };
  next();
}
```

```typescript
// src/auth.service.ts
import argon2 from 'argon2';
import jwt from 'jsonwebtoken';
import { createHash, randomBytes, randomUUID } from 'node:crypto';
import type { CookieOptions, Response } from 'express';
import { config } from './config';
import { pool, query } from './db';
import { sendMail } from './mailer';
import { redis } from './redis';
import { AppError } from './errors';
import type { AuthenticatedUser, RefreshTokenRow, User } from './types';

export const ACCESS_COOKIE = 'access_token';
export const REFRESH_COOKIE = 'refresh_token';

interface AccessPayload {
  sub: string;
  email: string;
  displayName: string;
  type: 'access';
}

interface RefreshPayload {
  sub: string;
  jti: string;
  type: 'refresh';
}

export interface Session {
  accessToken: string;
  refreshToken: string;
  user: AuthenticatedUser;
}

function toAuthenticatedUser(user: User): AuthenticatedUser {
  return { userId: user.id, email: user.email, displayName: user.display_name };
}

function signAccessToken(user: AuthenticatedUser): string {
  return jwt.sign(
    { sub: user.userId, email: user.email, displayName: user.displayName, type: 'access' },
    config.JWT_ACCESS_SECRET,
    { expiresIn: config.ACCESS_TOKEN_TTL }
  );
}

function signRefreshToken(userId: string, jti: string): string {
  return jwt.sign(
    { sub: userId, jti, type: 'refresh' },
    config.JWT_REFRESH_SECRET,
    { expiresIn: config.REFRESH_TOKEN_TTL_SECONDS }
  );
}

function accessCookieOptions(): CookieOptions {
  return {
    httpOnly: true,
    sameSite: 'strict',
    secure: config.isProd,
    domain: config.COOKIE_DOMAIN,
    path: '/',
    maxAge: 15 * 60 * 1000
  };
}

function refreshCookieOptions(): CookieOptions {
  return {
    httpOnly: true,
    sameSite: 'strict',
    secure: config.isProd,
    domain: config.COOKIE_DOMAIN,
    path: '/api/auth',
    maxAge: config.REFRESH_TOKEN_TTL_SECONDS * 1000
  };
}

export function setSessionCookies(res: Response, session: Session): void {
  res.cookie(ACCESS_COOKIE, session.accessToken, accessCookieOptions());
  res.cookie(REFRESH_COOKIE, session.refreshToken, refreshCookieOptions());
}

export function clearSessionCookies(res: Response): void {
  res.clearCookie(ACCESS_COOKIE, accessCookieOptions());
  res.clearCookie(REFRESH_COOKIE, refreshCookieOptions());
}

export async function hashPassword(password: string): Promise<string> {
  return argon2.hash(password, {
    type: argon2.argon2id,
    memoryCost: 19 * 1024,
    timeCost: 2,
    parallelism: 1
  });
}

export async function verifyPassword(hash: string, password: string): Promise<boolean> {
  try {
    return await argon2.verify(hash, password);
  } catch {
    return false;
  }
}

export async function issueSession(user: User): Promise<Session> {
  const jti = randomUUID();
  const refreshToken = signRefreshToken(user.id, jti);
  await query(
    `INSERT INTO refresh_tokens (jti, user_id, rotation_count, expires_at)
     VALUES ($1, $2, 0, now() + make_interval(secs => $3))`,
    [jti, user.id, config.REFRESH_TOKEN_TTL_SECONDS]
  );
  return {
    accessToken: signAccessToken(toAuthenticatedUser(user)),
    refreshToken,
    user: toAuthenticatedUser(user)
  };
}

export async function register(input: {
  email: string;
  password: string;
  displayName: string;
}): Promise<AuthenticatedUser> {
  const email = input.email.trim().toLowerCase();
  const existing = await query<User>('SELECT * FROM users WHERE email = $1', [email]);
  if (existing.length > 0) throw AppError.conflict(`An account for ${email} already exists`);
  if (input.password.length < 8) throw AppError.badRequest('Password must be at least 8 characters');

  const passwordHash = await hashPassword(input.password);
  const rows = await query<User>(
    `INSERT INTO users (email, password_hash, display_name, email_verified_at)
     VALUES ($1, $2, $3, $4)
     RETURNING *`,
    [email, passwordHash, input.displayName, config.REQUIRE_EMAIL_VERIFICATION ? null : new Date().toISOString()]
  );
  const user = rows[0];
  if (config.REQUIRE_EMAIL_VERIFICATION && user.email_verified_at === null) {
    await sendVerificationEmail(user.id, user.email);
  }
  return toAuthenticatedUser(user);
}

export async function login(
  input: { email: string; password: string },
  res: Response
): Promise<AuthenticatedUser> {
  const email = input.email.trim().toLowerCase();
  const rows = await query<User>('SELECT * FROM users WHERE email = $1', [email]);
  const user = rows[0];
  if (!user || user.password_hash === null) throw AppError.unauthorized('Invalid email or password');

  const valid = await verifyPassword(user.password_hash, input.password);
  if (!valid) throw AppError.unauthorized('Invalid email or password');

  if (config.REQUIRE_EMAIL_VERIFICATION && user.email_verified_at === null) {
    throw AppError.unauthorized('Email not verified. Check your inbox.');
  }

  setSessionCookies(res, await issueSession(user));
  return toAuthenticatedUser(user);
}

export async function logout(refreshToken: string | undefined, res: Response): Promise<void> {
  if (refreshToken) {
    try {
      const payload = jwt.verify(refreshToken, config.JWT_REFRESH_SECRET) as RefreshPayload;
      await query('UPDATE refresh_tokens SET revoked_at = now() WHERE jti = $1', [payload.jti]);
      await redis.set(`refresh:denied:${payload.jti}`, '1', { EX: config.REFRESH_TOKEN_TTL_SECONDS });
    } catch {
      // Unknown or expired token: nothing to revoke.
    }
  }
  clearSessionCookies(res);
}

export async function rotateRefreshToken(refreshToken: string, res: Response): Promise<AuthenticatedUser> {
  let payload: RefreshPayload;
  try {
    payload = jwt.verify(refreshToken, config.JWT_REFRESH_SECRET) as RefreshPayload;
  } catch {
    throw AppError.unauthorized('Invalid or expired refresh token');
  }
  if (payload.type !== 'refresh') throw AppError.unauthorized('Invalid token type');

  const blacklisted = await redis.get(`refresh:denied:${payload.jti}`);
  if (blacklisted === '1') throw AppError.unauthorized('Refresh token revoked');

  const rows = await query<RefreshTokenRow>('SELECT * FROM refresh_tokens WHERE jti = $1', [payload.jti]);
  const row = rows[0];
  if (!row) throw AppError.unauthorized('Unknown refresh token');

  if (row.revoked_at !== null) {
    await query('UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = $1 AND revoked_at IS NULL', [row.user_id]);
    await redis.set(`refresh:denied:${payload.jti}`, '1', { EX: config.REFRESH_TOKEN_TTL_SECONDS });
    throw new AppError(401, 'TOKEN_REUSE_DETECTED', 'Refresh token reuse detected; session revoked');
  }

  if (new Date(row.expires_at).getTime() < Date.now()) {
    throw AppError.unauthorized('Refresh token expired');
  }

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('UPDATE refresh_tokens SET revoked_at = now() WHERE jti = $1', [row.jti]);
    const jti = randomUUID();
    await client.query(
      `INSERT INTO refresh_tokens (jti, user_id, rotation_count, expires_at)
       VALUES ($1, $2, $3, now() + make_interval(secs => $4))`,
      [jti, row.user_id, row.rotation_count + 1, config.REFRESH_TOKEN_TTL_SECONDS]
    );
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }

  const userRows = await query<User>('SELECT * FROM users WHERE id = $1', [row.user_id]);
  const user = userRows[0];
  if (!user) throw AppError.unauthorized('Account no longer exists');
  setSessionCookies(res, await issueSession(user));
  return toAuthenticatedUser(user);
}

async function sendVerificationEmail(userId: string, email: string): Promise<void> {
  const token = randomBytes(24).toString('base64url');
  const tokenHash = createHash('sha256').update(token).digest('hex');
  await query(
    `INSERT INTO email_verification_tokens (token_hash, user_id, expires_at)
     VALUES ($1, $2, now() + interval '24 hours')`,
    [tokenHash, userId]
  );
  await sendMail({
    to: email,
    subject: 'Verify your email',
    text: `Verify your email: ${config.OAUTH_REDIRECT_BASE}/verify-email?token=${token}`
  });
}

export async function verifyEmail(token: string): Promise<void> {
  const tokenHash = createHash('sha256').update(token).digest('hex');
  const rows = await query<{ token_hash: string; user_id: string; expires_at: string; used_at: string | null }>(
    'SELECT * FROM email_verification_tokens WHERE token_hash = $1',
    [tokenHash]
  );
  const row = rows[0];
  if (!row) throw AppError.badRequest('Invalid verification token');
  if (row.used_at !== null) throw AppError.badRequest('Verification token already used');
  if (new Date(row.expires_at).getTime() < Date.now()) throw AppError.badRequest('Verification token expired');
  await query('UPDATE users SET email_verified_at = now() WHERE id = $1', [row.user_id]);
  await query('UPDATE email_verification_tokens SET used_at = now() WHERE token_hash = $1', [tokenHash]);
}

export async function forgotPassword(email: string): Promise<void> {
  const rows = await query<User>('SELECT * FROM users WHERE email = $1', [email.trim().toLowerCase()]);
  const user = rows[0];
  if (!user || user.password_hash === null) return;
  const token = randomBytes(32).toString('base64url');
  const tokenHash = createHash('sha256').update(token).digest('hex');
  await query(
    `INSERT INTO password_reset_tokens (token_hash, user_id, expires_at)
     VALUES ($1, $2, now() + interval '30 minutes')`,
    [tokenHash, user.id]
  );
  await sendMail({
    to: user.email,
    subject: 'Password reset',
    text: `Reset your password: ${config.OAUTH_REDIRECT_BASE}/reset-password?token=${token}`
  });
}

export async function resetPassword(
  token: string,
  newPassword: string,
  res: Response
): Promise<AuthenticatedUser> {
  const tokenHash = createHash('sha256').update(token).digest('hex');
  const rows = await query<{ token_hash: string; user_id: string; expires_at: string; used_at: string | null }>(
    'SELECT * FROM password_reset_tokens WHERE token_hash = $1',
    [tokenHash]
  );
  const row = rows[0];
  if (!row) throw AppError.badRequest('Invalid reset token');
  if (row.used_at !== null) throw AppError.badRequest('Reset token already used');
  if (new Date(row.expires_at).getTime() < Date.now()) throw AppError.badRequest('Reset token expired');
  if (newPassword.length < 8) throw AppError.badRequest('Password must be at least 8 characters');

  const passwordHash = await hashPassword(newPassword);

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('UPDATE users SET password_hash = $1 WHERE id = $2', [passwordHash, row.user_id]);
    await client.query('UPDATE password_reset_tokens SET used_at = now() WHERE token_hash = $1', [tokenHash]);
    await client.query(
      'UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = $1 AND revoked_at IS NULL',
      [row.user_id]
    );
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }

  const userRows = await query<User>('SELECT * FROM users WHERE id = $1', [row.user_id]);
  const user = userRows[0];
  setSessionCookies(res, await issueSession(user));
  return toAuthenticatedUser(user);
}

export async function getProfile(
  userId: string
): Promise<{ userId: string; email: string; displayName: string; emailVerified: boolean }> {
  const rows = await query<User>('SELECT * FROM users WHERE id = $1', [userId]);
  const user = rows[0];
  if (!user) throw AppError.unauthorized('Account no longer exists');
  return {
    userId: user.id,
    email: user.email,
    displayName: user.display_name,
    emailVerified: user.email_verified_at !== null
  };
}
```

```typescript
// src/auth.routes.ts
import { Router } from 'express';
import type { NextFunction, Request, Response } from 'express';
import { z } from 'zod';
import { config } from './config';
import { AppError } from './errors';
import { requireAuth, type AuthenticatedRequest } from './auth.middleware';
import * as authService from './auth.service';

const router = Router();

function validate<T>(schema: z.ZodSchema<T>) {
  return (req: Request, _res: Response, next: NextFunction): void => {
    const result = schema.safeParse(req.body ?? {});
    if (!result.success) {
      return next(
        AppError.badRequest(
          'Validation failed',
          result.error.issues.map((issue) => ({ path: issue.path.join('.'), message: issue.message }))
        )
      );
    }
    req.body = result.data;
    next();
  };
}

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(72),
  displayName: z.string().min(1).max(64)
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1)
});

const forgotSchema = z.object({ email: z.string().email() });

const resetSchema = z.object({
  token: z.string().min(1),
  password: z.string().min(8).max(72)
});

const tokenSchema = z.object({ token: z.string().min(1) });

router.post('/register', validate(registerSchema), (req, res, next) => {
  authService
    .register(req.body as { email: string; password: string; displayName: string })
    .then((user) => {
      res.status(201).json({
        success: true,
        data: { user, requiresEmailVerification: config.REQUIRE_EMAIL_VERIFICATION }
      });
    })
    .catch(next);
});

router.post('/login', validate(loginSchema), (req, res, next) => {
  authService
    .login(req.body as { email: string; password: string }, res)
    .then((user) => res.status(200).json({ success: true, data: { user } }))
    .catch(next);
});

router.post('/refresh', (req, res, next) => {
  const token = req.cookies?.[authService.REFRESH_COOKIE];
  if (typeof token !== 'string') return next(AppError.unauthorized('Missing refresh token'));
  authService
    .rotateRefreshToken(token, res)
    .then((user) => res.status(200).json({ success: true, data: { user } }))
    .catch(next);
});

router.post('/logout', (req, res, next) => {
  const token = req.cookies?.[authService.REFRESH_COOKIE];
  authService
    .logout(typeof token === 'string' ? token : undefined, res)
    .then(() => res.status(200).json({ success: true, data: null }))
    .catch(next);
});

router.post('/forgot-password', validate(forgotSchema), (req, res, next) => {
  authService
    .forgotPassword((req.body as { email: string }).email)
    .then(() => res.status(200).json({ success: true, data: null }))
    .catch(next);
});

router.post('/reset-password', validate(resetSchema), (req, res, next) => {
  const { token, password } = req.body as { token: string; password: string };
  authService
    .resetPassword(token, password, res)
    .then((user) => res.status(200).json({ success: true, data: { user } }))
    .catch(next);
});

router.post('/verify-email', validate(tokenSchema), (req, res, next) => {
  authService
    .verifyEmail((req.body as { token: string }).token)
    .then(() => res.status(200).json({ success: true, data: null }))
    .catch(next);
});

router.get('/me', requireAuth, (req: AuthenticatedRequest, res, next) => {
  authService
    .getProfile(req.user.userId)
    .then((profile) => res.status(200).json({ success: true, data: profile }))
    .catch(next);
});

export default router;
```

```typescript
// src/oauth.routes.ts
import { Router } from 'express';
import type { NextFunction, Request, Response } from 'express';
import passport from 'passport';
import { Strategy as GoogleStrategy, type Profile as GoogleProfile } from 'passport-google-oauth20';
import { Strategy as GitHubStrategy, type Profile as GitHubProfile } from 'passport-github2';
import { config } from './config';
import { query } from './db';
import { AppError } from './errors';
import { issueSession, setSessionCookies } from './auth.service';
import type { User } from './types';

const router = Router();

passport.use(
  new GoogleStrategy(
    {
      clientID: config.GOOGLE_CLIENT_ID ?? 'unset',
      clientSecret: config.GOOGLE_CLIENT_SECRET ?? 'unset',
      callbackURL: `${config.OAUTH_REDIRECT_BASE}/api/auth/google/callback`
    },
    (_accessToken, _refreshToken, profile, done) => {
      done(null, profile);
    }
  )
);

passport.use(
  new GitHubStrategy(
    {
      clientID: config.GITHUB_CLIENT_ID ?? 'unset',
      clientSecret: config.GITHUB_CLIENT_SECRET ?? 'unset',
      callbackURL: `${config.OAUTH_REDIRECT_BASE}/api/auth/github/callback`
    },
    (_accessToken, _refreshToken, profile, done) => {
      done(null, profile);
    }
  )
);

async function findOrCreateOAuthUser(
  provider: 'google' | 'github',
  providerAccountId: string,
  email: string | null,
  displayName: string
): Promise<User> {
  const links = await query<{ user_id: string }>(
    'SELECT user_id FROM oauth_accounts WHERE provider = $1 AND provider_account_id = $2',
    [provider, providerAccountId]
  );
  if (links.length > 0) {
    const users = await query<User>('SELECT * FROM users WHERE id = $1', [links[0].user_id]);
    if (users.length > 0) return users[0];
  }

  let user: User | undefined;
  if (email) {
    const byEmail = await query<User>('SELECT * FROM users WHERE email = $1', [email.toLowerCase()]);
    user = byEmail[0];
  }

  if (!user) {
    const created = await query<User>(
      `INSERT INTO users (email, password_hash, display_name, email_verified_at)
       VALUES ($1, NULL, $2, $3)
       RETURNING *`,
      [email ?? `${providerAccountId}@${provider}.local`, displayName, email ? new Date().toISOString() : null]
    );
    user = created[0];
  }

  await query(
    `INSERT INTO oauth_accounts (provider, provider_account_id, user_id, access_token, refresh_token)
     VALUES ($1, $2, $3, $4, $5)
     ON CONFLICT (provider, provider_account_id) DO NOTHING`,
    [provider, providerAccountId, user.id, null, null]
  );
  return user;
}

function oauthCallback(provider: 'google' | 'github') {
  return (req: Request, res: Response, next: NextFunction): void => {
    const profile = req.user as GoogleProfile | GitHubProfile;
    if (!profile) {
      return next(AppError.unauthorized('OAuth callback without profile'));
    }
    const email = profile.emails?.[0]?.value ?? null;
    const username = 'username' in profile ? profile.username ?? undefined : undefined;
    const displayName = profile.displayName ?? username ?? 'OAuth User';

    findOrCreateOAuthUser(provider, profile.id, email, displayName)
      .then(async (user) => {
        setSessionCookies(res, await issueSession(user));
        res.redirect(config.OAUTH_REDIRECT_BASE);
      })
      .catch(next);
  };
}

router.get('/google', passport.authenticate('google', { scope: ['profile', 'email'], session: false }));
router.get(
  '/google/callback',
  passport.authenticate('google', { session: false, failureRedirect: `${config.OAUTH_REDIRECT_BASE}/login` }),
  oauthCallback('google')
);
router.get('/github', passport.authenticate('github', { session: false }));
router.get(
  '/github/callback',
  passport.authenticate('github', { session: false, failureRedirect: `${config.OAUTH_REDIRECT_BASE}/login` }),
  oauthCallback('github')
);

export default router;
```

```typescript
// src/server.ts
import 'dotenv/config';
import type { Server } from 'node:http';
import express from 'express';
import cookieParser from 'cookie-parser';
import cors from 'cors';
import helmet from 'helmet';
import { config } from './config';
import { initDb } from './db';
import { connectRedis } from './redis';
import { errorHandler, notFoundHandler } from './errors';
import authRouter from './auth.routes';
import oauthRouter from './oauth.routes';

export async function startServer(): Promise<Server> {
  await Promise.all([initDb(), connectRedis()]);

  const app = express();
  app.set('trust proxy', config.isProd ? 1 : 0);
  app.use(helmet());
  app.use(cors({ origin: config.CORS_ORIGIN ?? '*', credentials: true }));
  app.use(express.json({ limit: '256kb' }));
  app.use(cookieParser());

  app.get('/health', (_req, res) => {
    res.status(200).json({ success: true, data: { status: 'ok' } });
  });

  app.use('/api/auth', authRouter);
  app.use('/api/auth', oauthRouter);

  app.use(notFoundHandler);
  app.use(errorHandler);

  return new Promise((resolve) => {
    const server = app.listen(config.PORT, () => {
      console.log(`[auth] api listening on http://localhost:${config.PORT}`);
      resolve(server);
    });
  });
}

if (require.main === module) {
  startServer().catch((err) => {
    console.error('[auth] startup failed', err);
    process.exit(1);
  });
}
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Scaffold: create the project directory and copy all files from section 3 (package.json, tsconfig.json, `.env.example`, `src/*`).
2. Provision infra: `docker run -d --name authdb -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=authdb postgres:16` and `docker run -d --name authredis -p 6379:6379 redis:7`.
3. Configure: copy `.env.example` to `.env` and replace both `JWT_*_SECRET` values with `openssl rand -hex 32` output; fill OAuth client ids/secrets if Google/GitHub flows will be used.
4. Install: run `npm install`.
5. Migrate: schema tables are created automatically by `initDb()` on server boot — no separate migration tool is required.
6. Run: execute `npm run dev`; API listens on `http://localhost:4000`.
7. Verify register: `curl -s -X POST http://localhost:4000/api/auth/register -H "Content-Type: application/json" -d '{"email":"ada@example.com","password":"supersecret1","displayName":"Ada"}'`.
8. Verify login + cookies: `curl -s -c cookies.txt -X POST http://localhost:4000/api/auth/login -H "Content-Type: application/json" -d '{"email":"ada@example.com","password":"supersecret1"}'` and inspect `cookies.txt` for `access_token` and `refresh_token`.
9. Verify rotation: `curl -s -b cookies.txt -c cookies.txt -X POST http://localhost:4000/api/auth/refresh` twice; the second call returns `401 TOKEN_REUSE_DETECTED` because the first rotation revoked the old token.
10. Verify protected route: `curl -s -b cookies.txt http://localhost:4000/api/auth/me`.
11. Verify logout: `curl -s -b cookies.txt -c cookies.txt -X POST http://localhost:4000/api/auth/logout`, then confirm `/refresh` returns `401`.
12. Verify OAuth: open `http://localhost:4000/api/auth/google` and `http://localhost:4000/api/auth/github` in a browser (requires configured client credentials).
13. Production build: run `npm run build && npm start`.

## 5. Edge Cases & Error Handling

- Boot refuses to start when `JWT_ACCESS_SECRET`/`JWT_REFRESH_SECRET` are missing or shorter than 32 chars — no weak-secret default exists in production paths.
- Refresh-token rotation is atomic: `BEGIN` → revoke old row → insert new row → `COMMIT`; any failure rolls back leaving the old token usable, and the partial-index on `refresh_tokens(user_id) WHERE revoked_at IS NULL` enforces a single live token per user.
- Token replay detection: presenting an already-rotated token triggers `TOKEN_REUSE_DETECTED` and revokes the user's entire active token family plus a Redis `refresh:denied:<jti>` blacklist entry as a rollback guard.
- Redis failures do not break login/logout: the blacklist is auxiliary hardening; DB rows are the source of truth, and `rotateRefreshToken` still refuses revoked rows from PostgreSQL alone.
- Password reset and email-verification tokens are stored only as SHA-256 hashes, expire after 30 min / 24 h, are single-use (`used_at`), and `forgot-password` always returns 200 so account existence is not enumerable.
- Argon2id parameters (`m=19456, t=2, p=1`) are OWASP-aligned; `verifyPassword` swallows malformed-hash exceptions and returns `false` so unknown hashes degrade to a generic "Invalid email or password" and never crash the request.
- OAuth callback failure (canceled consent, invalid state, missing profile) redirects to `<OAUTH_REDIRECT_BASE>/login` and never sets partial cookies; a `UNIQUE(user_id, provider)` constraint prevents duplicate provider links.
- Rate limiting of login/refresh/forgot endpoints is expected in front of this service (e.g., `express-rate-limit`) — the scaffold deliberately leaves envelope and error codes standardized so a proxy or middleware can add throttling without touching the service layer.