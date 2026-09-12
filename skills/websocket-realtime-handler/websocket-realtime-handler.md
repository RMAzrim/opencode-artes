---
id: websocket-realtime-handler
file_path: skills/websocket-realtime-handler/websocket-realtime-handler.md
name: WebSocket Realtime Handler
category: backend
tags: [websocket, realtime, heartbeat, reconnect, broadcasting]
author: opencode-core
version: 1.0.0
description: Implement WebSocket connection lifecycles, ping/pong heartbeats, reconnect logic, and event broadcasting.
---

# WebSocket Realtime Handler

## Prerequisites & Dependencies
- Node.js 18+ with `ws` or `socket.io` library
- Understanding of browser WebSocket API and same-origin policy
- Optional: Redis for distributed pub/sub across multiple server instances

## Execution Steps
1. Set up a WebSocket server (`ws` lightweight, `socket.io` feature-rich) on an HTTPS endpoint
2. Implement the connection lifecycle: `connection`, `open`, `message`, `close` events
3. Add a periodic ping/pong heartbeat (e.g., every 25s, timeout after 60s) to detect dead connections
4. Implement graceful reconnect logic on the client: exponential backoff, rejoin rooms/channels after reconnection
5. For broadcasting: use `socket.emit('event', data)` for single room, or Redis pub/sub (`socket.io-redis`) for multi-instance setups
6. Secure the WS handshake: validate JWT cookies/origins, reject unauthorized connections
7. Log connection metrics (connections per minute, disconnect reasons) for observability

```javascript
// ws server with heartbeat and room broadcasting
const WebSocket = require('ws');
const server = new WebSocket.Server({ noServer: true, path: '/ws' });

const HEARTBEAT_INTERVAL = 25000;
const HEARTBEAT_TIMEOUT = 60000;

server.on('connection', (ws) => {
  ws.isAlive = true;
  ws.on('pong', () => { ws.isAlive = true; });
  ws.on('close', () => { console.log('client disconnected'); });

  const heartbeat = setInterval(() => {
    ws.ping(null, (err) => {
      if (err) { clearInterval(heartbeat); ws.terminate(); }
    });
  }, HEARTBEAT_INTERVAL);

  ws.on('message', (msg) => {
    // broadcast to room 'auction-123'
    wss.clients.forEach(client => {
      if (client.room === 'auction-123') client.send(msg);
    });
  });
});

setInterval(() => {
  server.clients.forEach(ws => {
    if (ws.isAlive === false) return ws.terminate();
    ws.isAlive = false;
    ws.ping();
  });
}, 30000);
```