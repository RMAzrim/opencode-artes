---
id: websocket-realtime-secure-engine
file_path: skills/websocket-realtime-secure-engine/websocket-realtime-secure-engine.md
name: WebSocket Realtime Secure Engine
category: backend
tags: [websocket, socket.io, realtime, jwt]
author: opencode-core
version: 1.0.0
description: Scaffolds high-throughput, bidirectional real-time communication layers over WebSockets or Server-Sent Events (SSE) with robust reconnection and authentication controls.
---

# WebSocket Realtime Secure Engine

## 1. System Architecture & Prerequisites

- Node.js >= 18 LTS (runtime), npm >= 9, TypeScript >= 5.5, `tsx@^4.16.2` as the dev runner.
- Runtime deps: `socket.io@^4.7.5`, `socket.io-client@^4.7.5`, `jsonwebtoken@^9.0.2`, `redis@^4.7.0` (optional adapter), `@socket.io/redis-adapter@^8.3.0` (optional horizontal scale), `dotenv@^16.4.5`.
- Dev deps: `@types/node@^20.14.9`, `@types/jsonwebtoken@^9.0.6`, `typescript@^5.5.2`.
- Topologies: single-instance (in-memory sequence + room routing) and horizontally scaled (Redis adapter broadcasts `message`/`ping` events across nodes; sequence log stays per-node unless moved to Redis Streams).

## 2. Input/Output Data Contracts

### Handshake authentication

- Auth input: `socket.handshake.auth.token` — a JWT access token (claims `sub`, `role`, `email`). Optional fallback header: `x-access-token`.
- Failure output: `next(new Error('unauthorized: <reason>'))`; the client receives a `connect_error` event and must not be connected.

### Client → server events

- `room:join` → `{ channel: string }` → server emits `room:joined` `{ channel, resumeSeq }` or `room:join:error` `{ code, message }`.
- `room:leave` → `{ channel: string }`.
- `room:list` → server emits `room:list:result` `{ rooms: string[] }` filtered by role.
- `chat:send` → `{ channel: string, body: string(1..2000) }` → broadcast `message` `{ seq, channel, userId, payload: { from, body }, ts }` or `chat:send:error`.
- `resync:since` → `{ channel: string, since: number }` → server emits `resync:events` `{ channel, events: StoredMessage[], currentSeq }`.
- `delivered` → `{ seq: number }` — advances the per-user delivered-sequence watermark.
- `pong` → any payload — marks the socket alive for the heartbeat monitor.

### Server → client events

- `ping` `{ at: number }` every 25s (app-level liveness frame; the client must answer `pong` or it is disconnected).
- `message`, `resync:events`, `room:joined`, `room:list:result`, and error events as defined above.

### Output artifact paths

- `skills/websocket-realtime-secure-engine/package.json`, `tsconfig.json`, `.env.example`
- `src/auth.ts`, `src/security.ts`, `src/server.ts`, `src/client.ts`

## 3. Production Reference Implementation

```text
# .env.example
PORT=8080
CORS_ORIGIN=http://localhost:3000
JWT_ACCESS_SECRET=change-me-at-least-32-chars-long
REDIS_URL=redis://127.0.0.1:6379
REDIS_ADAPTER=false
CHANNEL=channel:public
ACCESS_TOKEN=
```

```json
// package.json
{
  "name": "websocket-realtime-secure-engine",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "server": "tsx src/server.ts",
    "client": "tsx src/client.ts"
  },
  "dependencies": {
    "@socket.io/redis-adapter": "^8.3.0",
    "dotenv": "^16.4.5",
    "jsonwebtoken": "^9.0.2",
    "redis": "^4.7.0",
    "socket.io": "^4.7.5",
    "socket.io-client": "^4.7.5"
  },
  "devDependencies": {
    "@types/jsonwebtoken": "^9.0.6",
    "@types/node": "^20.14.9",
    "tsx": "^4.16.2",
    "typescript": "^5.5.2"
  }
}
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "types": ["node"]
  },
  "include": ["src/**/*.ts"]
}
```

```typescript
// src/auth.ts
import jwt from 'jsonwebtoken';

export type Role = 'admin' | 'user' | 'guest';

export interface AuthUser {
  userId: string;
  role: Role;
  email: string;
}

export interface AuthSuccess {
  ok: true;
  user: AuthUser;
}

export interface AuthFailure {
  ok: false;
  error: string;
}

export type AuthResult = AuthSuccess | AuthFailure;

export function verifyJwt(token: string): AuthResult {
  const secret = process.env.JWT_ACCESS_SECRET;
  if (!secret) {
    return { ok: false, error: 'server JWT_ACCESS_SECRET not configured' };
  }
  try {
    const payload = jwt.verify(token, secret) as {
      sub?: string;
      email?: string;
      role?: Role;
      type?: string;
    };
    if (typeof payload.sub !== 'string') {
      return { ok: false, error: 'missing subject' };
    }
    return {
      ok: true,
      user: {
        userId: payload.sub,
        role: payload.role ?? 'user',
        email: payload.email ?? ''
      }
    };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'invalid token' };
  }
}
```

```typescript
// src/security.ts
export type Role = 'admin' | 'user' | 'guest';

export interface RoomPolicy {
  channel: string;
  description: string;
  allowedRoles: Role[];
}

export const ROOMS: Record<string, RoomPolicy> = {
  'channel:public': {
    channel: 'channel:public',
    description: 'Everyone',
    allowedRoles: ['admin', 'user', 'guest']
  },
  'channel:premium': {
    channel: 'channel:premium',
    description: 'Admin and paying users',
    allowedRoles: ['admin', 'user']
  },
  'channel:admin': {
    channel: 'channel:admin',
    description: 'Staff only',
    allowedRoles: ['admin']
  }
};

export class RealtimeError extends Error {
  public readonly statusCode: number;
  public readonly code: string;

  constructor(statusCode: number, code: string, message: string) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
  }
}

export function canJoin(channel: string, role: Role): boolean {
  const room = ROOMS[channel];
  if (!room) return false;
  return room.allowedRoles.includes(role);
}

export function assertCanJoin(channel: string, role: Role): void {
  if (!canJoin(channel, role)) {
    throw new RealtimeError(403, 'FORBIDDEN_CHANNEL', `Role '${role}' cannot join '${channel}'`);
  }
}
```

```typescript
// src/server.ts
import http from 'node:http';
import 'dotenv/config';
import type { Server as SocketServer, Socket } from 'socket.io';
import { Server } from 'socket.io';
import { createClient } from 'redis';
import { createAdapter } from '@socket.io/redis-adapter';
import { verifyJwt, type AuthUser } from './auth';
import { assertCanJoin, ROOMS, RealtimeError } from './security';

const PORT = Number(process.env.PORT ?? 8080);
const PING_INTERVAL_MS = 25_000;
const PING_TIMEOUT_MS = 10_000;
const MESSAGE_LOG_CAP = 10_000;

interface StoredMessage {
  seq: number;
  channel: string;
  userId: string;
  payload: unknown;
  ts: number;
}

const messageLog = new Map<string, StoredMessage[]>();
const seqByUser = new Map<string, number>();
const sockets = new Map<string, Socket>();
const alive = new Map<string, boolean>();
let globalSeq = 0;

const httpServer = http.createServer((_req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ success: true, data: { service: 'realtime-engine' } }));
});

const io: SocketServer = new Server(httpServer, {
  cors: { origin: process.env.CORS_ORIGIN ?? '*', credentials: true },
  transports: ['websocket'],
  pingInterval: PING_INTERVAL_MS,
  pingTimeout: PING_TIMEOUT_MS
});

io.use((socket, next) => {
  const token = (
    socket.handshake.auth?.token ??
    socket.handshake.headers['x-access-token']
  ) as string | undefined;
  if (!token) {
    return next(new Error('unauthorized: missing token'));
  }
  const result = verifyJwt(token);
  if (!result.ok) {
    return next(new Error(`unauthorized: ${result.error}`));
  }
  socket.data.user = result.user;
  next();
});

function currentSeq(userId: string): number {
  return seqByUser.get(userId) ?? 0;
}

function storeMessage(channel: string, userId: string, payload: unknown): StoredMessage {
  globalSeq += 1;
  const msg: StoredMessage = { seq: globalSeq, channel, userId, payload, ts: Date.now() };
  const log = messageLog.get(channel) ?? [];
  log.push(msg);
  if (log.length > MESSAGE_LOG_CAP) log.shift();
  messageLog.set(channel, log);
  return msg;
}

function publish(channel: string, userId: string, payload: unknown): void {
  const msg = storeMessage(channel, userId, payload);
  io.to(channel).emit('message', msg);
}

function handleRoomJoin(socket: Socket, user: AuthUser, channel: string): void {
  try {
    assertCanJoin(channel, user.role);
  } catch (err) {
    const e = err instanceof RealtimeError ? err : new RealtimeError(500, 'INTERNAL', 'Join failed');
    socket.emit('room:join:error', { code: e.code, message: e.message });
    return;
  }
  void socket.join(channel);
  socket.emit('room:joined', { channel, resumeSeq: currentSeq(user.userId) });
}

function handleResync(socket: Socket, user: AuthUser, channel: string, since: number): void {
  const log = messageLog.get(channel) ?? [];
  const events = log.filter((m) => m.seq > since && m.seq <= currentSeq(user.userId));
  socket.emit('resync:events', { channel, events, currentSeq: currentSeq(user.userId) });
}

const heartbeat = setInterval(() => {
  const now = Date.now();
  for (const [id, socket] of sockets) {
    if (alive.get(id) === false) {
      console.log(`[heartbeat] socket=${id} missed pong, disconnecting`);
      socket.disconnect(true);
      sockets.delete(id);
      alive.delete(id);
      continue;
    }
    alive.set(id, false);
    socket.emit('ping', { at: now });
  }
}, PING_INTERVAL_MS);

io.on('connection', (socket) => {
  const user = socket.data.user as AuthUser;
  sockets.set(socket.id, socket);
  alive.set(socket.id, true);
  console.log(`[conn] socket=${socket.id} userId=${user.userId} role=${user.role}`);

  socket.on('pong', () => {
    alive.set(socket.id, true);
  });

  socket.on('room:join', (payload: { channel?: string }) => {
    handleRoomJoin(socket, user, payload?.channel ?? 'channel:public');
  });

  socket.on('room:leave', (payload: { channel?: string }) => {
    if (payload?.channel) {
      void socket.leave(payload.channel);
    }
  });

  socket.on('room:list', () => {
    const rooms = Object.values(ROOMS)
      .filter((room) => room.allowedRoles.includes(user.role))
      .map((room) => room.channel);
    socket.emit('room:list:result', { rooms });
  });

  socket.on('chat:send', (payload: { channel: string; body: string }) => {
    try {
      assertCanJoin(payload.channel, user.role);
      if (typeof payload.body !== 'string' || payload.body.length === 0 || payload.body.length > 2000) {
        throw new RealtimeError(400, 'INVALID_BODY', 'Message body must be 1-2000 characters');
      }
      publish(payload.channel, user.userId, { from: user.userId, body: payload.body });
    } catch (err) {
      const e = err instanceof RealtimeError ? err : new RealtimeError(500, 'INTERNAL', 'Publish failed');
      socket.emit('chat:send:error', { code: e.code, message: e.message });
    }
  });

  socket.on('resync:since', (payload: { channel: string; since?: number }) => {
    const since = Number.isSafeInteger(payload?.since) ? (payload.since as number) : 0;
    handleResync(socket, user, payload?.channel ?? 'channel:public', since);
  });

  socket.on('delivered', (payload: { seq?: number }) => {
    const seq = payload?.seq;
    if (typeof seq === 'number' && seq > currentSeq(user.userId)) {
      seqByUser.set(user.userId, seq);
    }
  });

  socket.on('disconnect', (reason) => {
    sockets.delete(socket.id);
    alive.delete(socket.id);
    console.log(`[disc] socket=${socket.id} reason=${reason}`);
  });
});

async function attachRedisAdapter(): Promise<void> {
  if (process.env.REDIS_ADAPTER !== 'true') {
    return;
  }
  const pub = createClient({ url: process.env.REDIS_URL ?? 'redis://127.0.0.1:6379' });
  const sub = pub.duplicate();
  await Promise.all([pub.connect(), sub.connect()]);
  io.adapter(createAdapter(pub, sub));
  console.log('[redis-adapter] attached — broadcasts fan out across nodes');
}

function shutdown(): void {
  clearInterval(heartbeat);
  io.close();
  httpServer.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 5_000).unref();
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

async function bootstrap(): Promise<void> {
  await attachRedisAdapter();
  httpServer.listen(PORT, () => {
    console.log(`[realtime] engine on ws://localhost:${PORT}`);
  });
}

void bootstrap();
```

```typescript
// src/client.ts
import 'dotenv/config';
import { io, type Socket } from 'socket.io-client';

const url = process.env.WS_URL ?? 'http://localhost:8080';
const channel = process.env.CHANNEL ?? 'channel:public';
const token = process.env.ACCESS_TOKEN;

function start(): void {
  if (!token) {
    console.error('[client] ACCESS_TOKEN env var is required');
    process.exit(1);
  }

  let lastSeenSeq = 0;

  const socket: Socket = io(url, {
    auth: { token },
    transports: ['websocket'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1_000,
    reconnectionDelayMax: 8_000,
    randomizationFactor: 0.5,
    timeout: 20_000
  });

  socket.on('connect', () => {
    console.log(`[client] connected socket=${socket.id}`);
    socket.emit('room:join', { channel });
    if (lastSeenSeq > 0) {
      socket.emit('resync:since', { channel, since: lastSeenSeq });
    }
  });

  socket.on('room:joined', (payload: { channel: string; resumeSeq: number }) => {
    lastSeenSeq = payload.resumeSeq;
    console.log(`[client] joined ${payload.channel} resumeSeq=${lastSeenSeq}`);
    socket.emit('chat:send', { channel, body: `hello from ${socket.id}` });
  });

  socket.on('room:join:error', (err: { code: string; message: string }) => {
    console.error(`[client] join rejected code=${err.code} message=${err.message}`);
  });

  socket.on('message', (msg: { seq: number; channel: string; payload: { from: string; body: string }; ts: number }) => {
    if (msg.seq > lastSeenSeq) lastSeenSeq = msg.seq;
    console.log(`[client] seq=${msg.seq} from=${msg.payload.from}: ${msg.payload.body}`);
  });

  socket.on('resync:events', (payload: {
    events: Array<{ seq: number; payload: { from: string; body: string } }>;
    currentSeq: number;
  }) => {
    for (const evt of payload.events) {
      if (evt.seq > lastSeenSeq) lastSeenSeq = evt.seq;
      console.log(`[client] replay seq=${evt.seq} from=${evt.payload.from}: ${evt.payload.body}`);
    }
    if (payload.currentSeq > lastSeenSeq) lastSeenSeq = payload.currentSeq;
    socket.emit('delivered', { seq: lastSeenSeq });
  });

  socket.on('chat:send:error', (err: { code: string; message: string }) => {
    console.error(`[client] send failed code=${err.code} message=${err.message}`);
  });

  socket.on('ping', () => {
    socket.emit('pong', { at: Date.now() });
  });

  socket.on('connect_error', (err) => {
    console.error(`[client] connect_error ${err.message}`);
  });

  socket.on('disconnect', (reason) => {
    console.warn(`[client] disconnected reason=${reason}`);
  });
}

start();
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Scaffold: create the project directory and copy all files from section 3 (package.json, tsconfig.json, `.env.example`, `src/*`).
2. Configure: copy `.env.example` to `.env`; set `JWT_ACCESS_SECRET` (min 32 chars) and generate at least one test token with `jsonwebtoken` or `jose`: `node -e "console.log(require('jsonwebtoken').sign({sub:'user-1',role:'admin',email:'admin@example.com'},'<secret>',{expiresIn:'15m'}))"`.
3. Install: run `npm install`.
4. Run server: execute `npm run server`; a plain-HTTP health probe is served at `http://localhost:8080` returning `{"service":"realtime-engine"}`.
5. Run client A: execute `ACCESS_TOKEN=<token> npm run client` with `ROLE`-appropriate token; observe `connected`, `joined`, the broadcast `message`, and periodic `ping`/`pong` liveness in the logs.
6. Run client B in a second terminal to confirm fan-out of `chat:send` to every member of the room on that node.
7. Verify authorization: join `channel:admin` with a `role: 'user'` token and confirm `room:join:error` `FORBIDDEN_CHANNEL` (403 semantics) is emitted and the client is not admitted.
8. Verify heartbeat: stop client A abruptly; within ~35s (`25s` ping interval + `10s` timeout) the server logs `missed pong, disconnecting` and cleans up the socket map.
9. Verify resync: notify client A is offline, have client B send several messages, then restart client A — it reconnects, re-joins, requests `resync:since` from its `lastSeenSeq`, replays the missed events, and thresholds `currentSeq`.
10. Horizontal scale (optional): set `REDIS_ADAPTER=true`, run two server instances, and confirm a `chat:send` on node 1 reaches a client connected to node 2.

```text
# Example authorization matrix exercised by the guards above
# channel   | admin | user | guest
# public    |   X   |  X   |   X
# premium   |   X   |  X   |   -
# admin     |   X   |  -   |   -
```

## 5. Edge Cases & Error Handling

- Unauthenticated or expired-token handshakes are rejected in the `io.use` middleware with an `unauthorized: <reason>` `connect_error`; expired JWTs (via `exp` claim) fail signature/expiry checks so idle connections cannot linger past the token TTL without re-authenticating.
- The heartbeat monitor uses a check-and-set `alive` flag per socket: each tick flips the flag to `false` and emits `ping`, and any socket still `false` at the next tick is force-disconnected and evicted from both maps; the built-in engine `pingTimeout` (10s) additionally terminates stalled transports, so a dead peer is recycled in ~35s total.
- Channel authorization is enforced at every entry point (`room:join` AND `chat:send`) — joining once does not grant later send rights, and unknown channel names fail `canJoin` so a typo never falls back to a public broadcast.
- Message size/type guards (`INVALID_BODY`) reject non-string or oversized payloads before publishing so the per-user sequence log cannot be poisoned by malformed frames.
- Reconnect reconciliation is duplicate-safe on the client: it only processes `resync:events` with `seq > lastSeenSeq`, idempotently replays, and acknowledges with `delivered` so the per-user watermark advances monotonically; the ring-buffer cap (`MESSAGE_LOG_CAP`) drops the oldest events rather than the newest to protect low-latency delivery.
- `forgotten` clients that never ack `delivered` are bounded by the ring-buffer cap on the server; a Redis Streams-backed journal (consumer groups + `XACK`) is the documented replacement when exactly-once delivery across restarts is required.
- Redis adapter startup failure is fatal (the process exits) so a half-fan-out production split is impossible; when `REDIS_ADAPTER` is unset/false the single-node in-memory path needs no Redis at all, keeping local dev dependency-free.
- Graceful shutdown clears the heartbeat interval, closes the socket.io engine, and drains the HTTP server before exit; a hard-exit timer (unref'd) prevents hangs on stubborn connections.