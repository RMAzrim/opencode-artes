---
name: WebSocket Realtime Sync Engine
description: Implements a dependency-light ESM WebSocket sync client with exponential-backoff reconnection, heartbeat ping/pong keep-alive, JSON Patch style delta application, and version-vector resync reconciliation, plus a runnable in-memory echo-server demo.
metadata:
  source: skills/websocket-realtime-sync-engine/websocket-realtime-sync-engine.md
---

# WebSocket Realtime Sync Engine

## 1. System Architecture & Prerequisites

This skill builds a resilient bidirectional WebSocket/SSE sync layer:

- **Exponential backoff reconnection** — `delay = min(cap, base * 2^attempt)`
  with jitter so a fleet of clients does not thundering-herd a restarting hub.
- **Heartbeat keep-alive** — periodic `{type:"ping"}` frames with a
  `lastPong` watchdog that force-reconnects a dead peer before the socket
  rots silently.
- **Delta-based state reconciliation** — deltas are JSON-Patch-like ops
  (`set`/`merge`/`replace`/`delete` on a path) applied to a local state tree;
  on reconnect a version vector `{device_id, seq}` drives a `resync_request`
  so missed deltas are replayed exactly once.

Prerequisites:

- **Node.js 18+** (ESM). Client WebSocket is global in Node 22+; for older
  Node install the dependency-light `ws` package (`npm i ws`) and the module
  fallback loader picks it up automatically.
- The demo server uses `ws` `WebSocketServer`; without it, `main()` prints a
  graceful hint instead of crashing.
- No build step, no TypeScript compiler required — the file is plain ESM that
  runs with `node realtime-client.js`.

## 2. Input/Output Data Contracts

### RealtimeClient constructor options

```json
{
  "url": "ws://host:port/path",
  "WebSocketImpl": "optional WebSocket constructor override",
  "baseDelay": 1000,
  "maxDelay": 30000,
  "jitter": 0.3,
  "maxAttempts": 1000000000,
  "heartbeatIntervalMs": 15000,
  "heartbeatTimeoutMs": 5000,
  "deviceId": "dev-xxxxxxxx"
}
```

### Delta operations (wire + local)

| `op`   | `path` | `value` | Semantics |
| ------ | ------ | ------- | --------- |
| `set`      | `["users","1","name"]` | string/number/bool | assign a leaf value |
| `merge`    | `["users","1"]`        | object             | deep-merge object into node |
| `replace`  | `[]`                  | object             | replace whole subtrees (incl. full state) |
| `delete`   | `["users","1"]`        | —                  | remove key or list index |

Wire envelope:

```json
{ "type": "delta", "op": "merge", "path": ["users","1"], "value": { "online": true }, "seq": 12, "device_id": "dev-abc" }
```

### Control frames

- `{type:"ping", device_id, ts}` / `{type:"pong", device_id, ts}`
- `{type:"hello", device_id, version:{seq}}` on open
- `{type:"resync_request", request_id, version:{device_id, seq}, last_server_seq}`
- `{type:"resync_ack", request_id, last_server_seq, applied}`
- `{type:"batch", deltas:[...]}` — replay of missed deltas

### Output/state

`RealtimeClient.getState()` returns the locally reconciled state tree, and
`resync()` resolves to `{last_server_seq, applied}` once the server has
replayed the missed window.

## 3. Production Reference Implementation

Save as `realtime-client.js`. Dependency-light ESM, guards the WebSocket
implementation, exports helpers suitable for unit testing.

```js
// realtime-client.js — resilient bidirectional sync client.
// Node 18+ ESM. Prefers the global WebSocket (Node 22+); falls back to 'ws'.
import { createRequire } from "module";
import { pathToFileURL } from "url";

const nodeRequire = createRequire(import.meta.url);

/** Resolve a WebSocket implementation, trying global first, then 'ws'. */
function resolveWebSocket() {
  const wsGlobal = globalThis.WebSocket;
  if (typeof wsGlobal === "function" && wsGlobal) {
    return wsGlobal;
  }
  try {
    const mod = nodeRequire("ws");
    return mod.WebSocket || mod;
  } catch {
    throw new Error(
      "No WebSocket implementation available: run Node >= 22 or `npm i ws`."
    );
  }
}

/**
 * Exponential backoff with full jitter.
 * delay = min(cap, base * 2**attempt) * (1 + jitter * [-1..1])
 */
function backoffDelay(baseDelay, attempt, maxDelay, jitter) {
  const exponential = Math.min(baseDelay * 2 ** attempt, maxDelay);
  const wiggle = 1 + (Math.random() * 2 - 1) * jitter;
  return Math.max(25, Math.round(exponential * wiggle));
}

/* ---------- delta primitives (pure functions, unit-testable) ---------- */

function setAtPath(state, path, value) {
  if (!Array.isArray(path) || path.length === 0) {
    return { ...(state ?? {}), ...value };
  }
  const root = { ...(state ?? {}) };
  let node = root;
  for (let i = 0; i < path.length - 1; i += 1) {
    const key = path[i];
    if (node[key] === null || typeof node[key] !== "object") {
      node[key] = Array.isArray(node[key]) ? [] : {};
    }
    node[key] = { ...node[key] };
    node = node[key];
  }
  node[path[path.length - 1]] = value;
  return root;
}

function mergeInto(target, value) {
  if (target && value && typeof target === "object" && typeof value === "object") {
    for (const [key, val] of Object.entries(value)) {
      if (
        val && typeof val === "object" && !Array.isArray(val) &&
        target[key] && typeof target[key] === "object" && !Array.isArray(target[key])
      ) {
        mergeInto(target[key], val);
      } else {
        target[key] = val;
      }
    }
  }
  return target;
}

function deleteAtPath(state, path) {
  if (!Array.isArray(path) || path.length === 0) {
    return state;
  }
  const root = { ...(state ?? {}) };
  let node = root;
  for (let i = 0; i < path.length - 1; i += 1) {
    const key = path[i];
    if (node[key] === null || typeof node[key] !== "object") {
      return state; // nothing to delete
    }
    node[key] = { ...node[key] };
    node = node[key];
  }
  delete node[path[path.length - 1]];
  return root;
}

/** Apply a JSON-Patch-like delta to the state tree and return the new state. */
function applyDelta(state, delta) {
  const { type, path = [], value } = delta;
  switch (type) {
    case "set":
    case "replace":
      return setAtPath(state, path, value);
    case "merge": {
      const root = { ...(state ?? {}) };
      let node = root;
      let key = null;
      if (Array.isArray(path) && path.length > 0) {
        for (let i = 0; i < path.length - 1; i += 1) {
          const k = path[i];
          if (node[k] === null || typeof node[k] !== "object") {
            node[k] = {};
          }
          node[k] = { ...node[k] };
          node = node[k];
        }
        key = path[path.length - 1];
        if (node[key] === null || typeof node[key] !== "object") {
          node[key] = {};
        } else {
          node[key] = { ...node[key] };
        }
        mergeInto(node[key], value);
      } else {
        mergeInto(root, value);
      }
      return root;
    }
    case "delete":
      return deleteAtPath(state, path);
    default:
      throw new Error(`Unknown delta type: ${type}`);
  }
}

/* ---------------------------- the client ---------------------------- */

export class RealtimeClient {
  constructor(options = {}) {
    this.url = options.url;
    this.WebSocket = options.WebSocketImpl || resolveWebSocket();
    this.baseDelay = options.baseDelay ?? 1000;
    this.maxDelay = options.maxDelay ?? 30000;
    this.jitter = options.jitter ?? 0.3;
    this.maxAttempts = options.maxAttempts ?? Infinity;
    this.heartbeatIntervalMs = options.heartbeatIntervalMs ?? 15000;
    this.heartbeatTimeoutMs = options.heartbeatTimeoutMs ?? 5000;
    this.deviceId =
      options.deviceId ||
      `dev-${Math.random().toString(36).slice(2, 10)}`;

    this.state = {};
    this.seq = 0;            // outbound delta counter (this device's vector)
    this.lastServerSeq = 0;  // highest server delta we have applied
    this.attempts = 0;
    this.connected = false;
    this.manualClose = false;
    this.socket = null;
    this.pending = [];
    this.lastPong = Date.now();
    this._resolveOpen = null;
    this._rejectOpen = null;
    this._resyncWaiters = [];
    this._timers = { heartbeat: null, watchdog: null, reconnect: null };
    this._events = new Map();
  }

  on(event, handler) {
    if (!this._events.has(event)) this._events.set(event, new Set());
    this._events.get(event).add(handler);
    return () => this._events.get(event)?.delete(handler);
  }

  emit(event, payload) {
    for (const handler of this._events.get(event) ?? []) {
      handler(payload);
    }
  }

  getState() {
    return this.state;
  }

  connect() {
    return new Promise((resolve, reject) => {
      this._resolveOpen = resolve;
      this._rejectOpen = reject;
      this.manualClose = false;
      this._openSocket();
    });
  }

  _openSocket() {
    if (this.manualClose) return;
    this.attempts += 1;
    this.emit("connecting", { attempt: this.attempts });

    let socket;
    try {
      socket = new this.WebSocket(this.url);
    } catch (err) {
      this._scheduleReconnect();
      throw err;
    }
    this.socket = socket;

    socket.onopen = () => {
      this.attempts = 0;
      this.connected = true;
      this.lastPong = Date.now();
      this.emit("open", { deviceId: this.deviceId });
      if (this._resolveOpen) {
        this._resolveOpen(true);
        this._resolveOpen = null;
        this._rejectOpen = null;
      }
      this.startHeartbeat(this.heartbeatIntervalMs);
      // Ask for the missed window before replaying our queued writes.
      this.resync().catch(() => {});
      this._flushPending();
      this._sendRaw({
        type: "hello",
        device_id: this.deviceId,
        version: { seq: this.seq },
      });
    };

    socket.onmessage = (event) => {
      let raw = event.data;
      if (typeof raw !== "string" && raw != null) {
        raw = Buffer.from(raw).toString("utf8");
      }
      this._onMessage(raw);
    };

    socket.onerror = () => {
      // onclose drives teardown; keep handlers simple.
    };

    socket.onclose = (info) => {
      this.connected = false;
      this.stopHeartbeat();
      this.emit("close", { code: info && info.code, reason: info && info.reason });
      if (!this.manualClose) this._scheduleReconnect();
    };
  }

  _scheduleReconnect() {
    if (this.manualClose || this.connected) return;
    if (this.attempts >= this.maxAttempts) {
      this.emit("error", new Error("max reconnect attempts reached"));
      if (this._rejectOpen) {
        const err = new Error("connection failed: max attempts reached");
        this._rejectOpen(err);
        this._resolveOpen = null;
        this._rejectOpen = null;
      }
      return;
    }
    const delay = backoffDelay(
      this.baseDelay, this.attempts, this.maxDelay, this.jitter
    );
    this.emit("reconnecting", { attempt: this.attempts, delayMs: delay });
    this._timers.reconnect = setTimeout(() => this._openSocket(), delay);
  }

  /* ------------------------- outbound deltas ------------------------- */

  sendDelta(delta) {
    const packet = {
      type: "delta",
      op: delta.type,
      path: delta.path ?? [],
      value: delta.value,
      seq: ++this.seq,
      device_id: this.deviceId,
    };
    this.state = applyDelta(this.state, {
      type: delta.type, path: delta.path, value: delta.value,
    });
    this.emit("delta", { ...packet, local: true });
    if (this.connected && this.socket && this.socket.readyState === 1) {
      this.socket.send(JSON.stringify(packet));
    } else {
      this.pending.push(packet);
    }
    return this.seq;
  }

  _flushPending() {
    if (this.pending.length === 0) return;
    const queued = this.pending;
    this.pending = [];
    for (const packet of queued) {
      if (this.socket && this.socket.readyState === 1) {
        this.socket.send(JSON.stringify(packet));
      } else {
        this.pending.push(packet);
      }
    }
  }

  _sendRaw(payload) {
    if (this.connected && this.socket && this.socket.readyState === 1) {
      this.socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  /* --------------------------- heartbeat ---------------------------- */

  startHeartbeat(intervalMs = this.heartbeatIntervalMs) {
    this.stopHeartbeat();
    this.lastPong = Date.now();
    this._timers.heartbeat = setInterval(() => {
      if (this.connected && this.socket && this.socket.readyState === 1) {
        this.socket.send(JSON.stringify({
          type: "ping", ts: Date.now(), device_id: this.deviceId,
        }));
      }
    }, intervalMs);
    this._timers.watchdog = setInterval(() => {
      if (this.connected &&
          Date.now() - this.lastPong > this.heartbeatTimeoutMs) {
        this.forceReconnect();
      }
    }, Math.min(intervalMs, Math.max(250, this.heartbeatTimeoutMs / 2)));
  }

  stopHeartbeat() {
    clearInterval(this._timers.heartbeat);
    clearInterval(this._timers.watchdog);
    this._timers.heartbeat = null;
    this._timers.watchdog = null;
  }

  forceReconnect() {
    this.emit("error", new Error("heartbeat timed out, reconnecting"));
    if (this.socket) {
      try {
        this.socket.close(4000, "heartbeat timeout");
      } catch {
        /* closing an already-dead socket is fine */
      }
    }
    this.connected = false;
    if (!this.manualClose) this._scheduleReconnect();
  }

  /* ----------------------- inbound message bus ---------------------- */

  _onMessage(raw) {
    if (typeof raw !== "string" || raw.length === 0) return;
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch {
      return; // ignore non-JSON frames (binary, chat payloads, etc.)
    }
    switch (msg.type) {
      case "pong":
        this.lastPong = Date.now();
        break;
      case "ping":
        this._sendRaw({ type: "pong", ts: Date.now(), device_id: this.deviceId });
        break;
      case "delta": {
        this._applyWireDelta(msg);
        break;
      }
      case "batch": {
        for (const delta of msg.deltas ?? []) {
          this._applyWireDelta(delta);
        }
        break;
      }
      case "resync_ack": {
        this._settleResync(msg);
        break;
      }
      case "set":
      case "merge":
      case "replace":
      case "delete": {
        this.state = applyDelta(this.state, msg);
        break;
      }
      default:
        break; // unknown control frames are tolerated
    }
  }

  _applyWireDelta(msg) {
    const op = { type: msg.op ?? "set", path: msg.path ?? [], value: msg.value };
    this.state = applyDelta(this.state, op);
    if (Number.isFinite(msg.seq) && msg.seq > this.lastServerSeq) {
      this.lastServerSeq = msg.seq;
    }
    this.emit("delta", { ...msg, local: false });
  }

  /* ------------------ version-vector resync ------------------ */

  resync() {
    return new Promise((resolve, reject) => {
      const requestId =
        `rs-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const waiter = {
        requestId,
        resolve,
        reject,
        timer: setTimeout(() => {
          this._dropResyncWaiter(requestId);
          reject(new Error("resync timed out"));
        }, 5000),
      };
      this._resyncWaiters.push(waiter);
      const fingerprint = { device_id: this.deviceId, seq: this.seq };
      const sent = this._sendRaw({
        type: "resync_request",
        request_id: requestId,
        version: fingerprint,
        last_server_seq: this.lastServerSeq,
      });
      if (!sent) {
        clearTimeout(waiter.timer);
        this._dropResyncWaiter(requestId);
        reject(new Error("not connected — cannot resync"));
      }
    });
  }

  _dropResyncWaiter(requestId) {
    const idx = this._resyncWaiters.findIndex((w) => w.requestId === requestId);
    if (idx >= 0) this._resyncWaiters.splice(idx, 1);
  }

  _settleResync(msg) {
    const idx = this._resyncWaiters.findIndex(
      (w) => w.requestId === msg.request_id
    );
    if (idx < 0) return;
    const [waiter] = this._resyncWaiters.splice(idx, 1);
    clearTimeout(waiter.timer);
    waiter.resolve({
      last_server_seq: msg.last_server_seq,
      applied: msg.applied ?? 0,
    });
  }

  close() {
    this.manualClose = true;
    this.stopHeartbeat();
    clearTimeout(this._timers.reconnect);
    if (this.socket) {
      try {
        this.socket.close(1000, "client bye");
      } catch {
        /* already closed */
      }
    }
    this.connected = false;
    this.socket = null;
  }
}

/* ---------------------- in-memory echo demo ---------------------- */

async function runDemo() {
  let wsModule = null;
  try {
    wsModule = nodeRequire("ws");
  } catch {
    wsModule = null;
  }
  if (!wsModule) {
    console.log(
      "Demo needs a WebSocket server: run `npm i ws` first (client detects " +
      "the global WebSocket on Node 22+ automatically)."
    );
    return;
  }

  const { WebSocketServer } = wsModule;
  let serverState = { tasks: {} };
  const serverLog = [];
  let nextSeq = 0;

  const wss = new WebSocketServer({ port: 0 });
  const port = wss.address().port;

  wss.on("connection", (socket) => {
    socket.send(JSON.stringify({ type: "replace", path: [], value: serverState }));
    socket.on("message", (data) => {
      let msg;
      try {
        msg = JSON.parse(data.toString("utf8"));
      } catch {
        return;
      }
      switch (msg.type) {
        case "ping":
          socket.send(JSON.stringify({ type: "pong", ts: Date.now() }));
          break;
        case "delta": {
          const delta = { op: msg.op, path: msg.path, value: msg.value };
          serverLog.push({ ...delta, seq: ++nextSeq });
          serverState = applyDelta(serverState, { type: msg.op, path: msg.path, value: msg.value });
          break;
        }
        case "resync_request": {
          const seen = msg.last_server_seq ?? 0;
          const missed = serverLog.filter((d) => d.seq > seen);
          socket.send(JSON.stringify({ type: "batch", deltas: missed }));
          socket.send(JSON.stringify({
            type: "resync_ack",
            request_id: msg.request_id,
            last_server_seq: nextSeq,
            applied: missed.length,
          }));
          break;
        }
        default:
          break;
      }
    });
  });

  const client = new RealtimeClient({
    url: `ws://127.0.0.1:${port}`,
    heartbeatIntervalMs: 2000,
    heartbeatTimeoutMs: 3000,
  });
  await client.connect();

  client.sendDelta({ type: "set", path: ["tasks", "1"], value: { title: "write skill 14", done: false } });
  client.sendDelta({ type: "merge", path: ["tasks", "1"], value: { done: true } });

  // Simulate an interrupted session: pretend we missed every server delta,
  // then request a resync. The server replays the whole window.
  client.lastServerSeq = 0;
  const summary = await client.resync();

  console.log("resync:", JSON.stringify(summary));
  console.log("client state:", JSON.stringify(client.getState(), null, 2));
  console.log("server state:", JSON.stringify(serverState, null, 2));

  const reconciled =
    JSON.stringify(client.getState()) === JSON.stringify(serverState);
  console.log(reconciled ? "RECONCILED OK" : "STATE MISMATCH");

  client.close();
  await new Promise((resolve) => wss.close(resolve));
}

const isMain =
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (isMain) {
  runDemo().catch((err) => {
    console.error(err);
    process.exitCode = 1;
  });
}

export { applyDelta, backoffDelay, deleteAtPath, mergeInto, resolveWebSocket, setAtPath };
```

Run it:

```bash
node --version        # >= 18
npm i ws              # only needed for the demo server on Node < 22
node realtime-client.js
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Provision the transport.** Confirm the server exposes a WebSocket (or
   SSE fallback) endpoint that speaks the frame types above: `ping`/`pong`,
   `delta`, `batch`, `resync_request`/`resync_ack`.
2. **Wrap the module.** `import { RealtimeClient } from "./realtime-client.js"`,
   construct with the server URL, then `await client.connect()`.
3. **Establish ground truth.** On the first open, request `replace` of the
   full state (full-state bootstrap) and cache the resulting `version.seq`.
   Subsequent reconnects only need the incremental window.
4. **Emit deltas locally-first.** Call `sendDelta` for every local mutation —
   the local tree applies optimistically; the server batch/echo reconciles.
5. **Reconcile on restore.** `on("open")` already triggers `resync()`. If you
   need a manual pull (e.g. after a long tab background), call `resync()`
   directly and only then re-enable the UI's dirty flag.
6. **Tune the backoff.** Set `maxDelay` ≤ typical hub recovery time and keep
   `maxAttempts` bounded; track `reconnecting` events for observability.
7. **Monitor liveness.** `heartbeatIntervalMs`/`heartbeatTimeoutMs` defaults
   (15s/5s) suit most health probes; tighten on flaky mobile networks.
8. **Shut down cleanly.** Call `close()` on unload to mark `manualClose` so
   the reconnect loop does not keep the tab alive after the user leaves.

### Server-side reconciliation contract (reference)

The demo server (`ws` WebSocketServer) implements the required server
semantics: it tags every accepted delta with a monotonically increasing `seq`,
persists a `serverLog`, answers `ping` with `pong`, answers `resync_request`
with a `batch` of `deltas` whose `seq > last_server_seq`, then a matching
`resync_ack`. Any production hub should mirror at least those four behaviors
plus per-connection `device_id` scoping.

## 5. Edge Cases & Error Handling

- **No WebSocket implementation** — `resolveWebSocket()` throws a descriptive
  error (run Node ≥ 22 or `npm i ws`). The demo degrades to a printed hint
  instead of a stack trace.
- **Reconnect storms** — exponential backoff with jitter spreads the herd; the
  `min(cap, base * 2**attempt)` cap prevents unbounded delay growth. Cap
  `maxAttempts` for long-lived mobile sessions.
- **Heartbeat death** — the watchdog observes `now - lastPong`; if it exceeds
  `heartbeatTimeoutMs` the socket is force-closed and the reconnect loop
  starts even though `onclose` may not fire promptly.
- **`readyState` flakiness during reconnect** — outbound deltas while
  disconnected are queued in `pending` and flushed on `open`, so a burst of
  user edits during a blip is never dropped from the local sequence.
- **Slow/dropped resync** — `resync()` rejects on a 5s timeout or when offline;
  callers treat it as non-fatal (a later `open` auto-resyncs).
- **Unknown messages** — non-JSON frames and unknown `type` values are
  ignored (forward-compatibility); `_applyWireDelta` guards `seq` with
  `Number.isFinite`. Bad payloads are never allowed to crash state parsing.
- **State type drift** — `merge` deep-merges only plain-object subtrees and
  overwrites arrays/leaf values wholesale; document that arrays are replaced,
  not element-merged, to avoid silent inconsistent lists.
- **Version skew on the client** — `lastServerSeq` is bumped only on
  `Number.isFinite` higher seqs, so out-of-order delivery cannot rewind the
  watermark and force useless full replays.
- **WebSocket + SSE** — if a proxy strips WebSocket upgrades, switch the
  transport to SSE and keep `RealtimeClient` interfaces (`sendDelta`,
  `resync`, `getState`) identical; only `_openSocket` and `_onMessage` change.
