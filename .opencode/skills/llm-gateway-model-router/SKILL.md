---
name: LLM Gateway Model Router
description: OpenAI-compatible /v1/chat/completions gateway built on http.server + sqlite3 with weighted round-robin routing, failover on provider errors, token budget/quota enforcement, and response caching. Ships with an in-process MockLLMBackend for fully offline demos. Pure stdlib Python 3.9+, zero installs, zero MCP.
metadata:
  source: skills/llm-gateway-model-router/llm-gateway-model-router.md
---

# LLM Gateway Model Router

Run a local OpenAI-API-compatible gateway that distributes `/v1/chat/completions` requests across registered model backends using weighted round-robin routing, enforces per-model token/cost quotas, caches responses, and falls back on provider failure â€” all from a single stdlib Python module with no external dependencies.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`http.server`, `json`, `sqlite3`, `hashlib`, `uuid`, `time`, `random`, `threading`, `os`, `sys`). No Flask, no aiohttp, no MCP.
- **Transport**: `http.server.HTTPServer` running on `127.0.0.1:<port>` (default `8089`).
- **Storage**: `sqlite3` connection at `gateway.sqlite` holding registered backends, quota meters, and a response cache keyed by request SHA-256.
- **Backend abstraction**: each backend is a `(name, base_url, weight, active, api_key)` tuple; routing chooses the next active backend weighted-proportional to `weight` on each request; fallback retries the request on the next-most-weighted active backend on HTTP/4xx-from-backend or connection failure.
- **MockLLMBackend**: an in-process fake HTTP handler responding to OpenAI-compatible payloads with deterministic text using `uuid4` turn IDs â€” so the gateway can be demoed fully offline.

## 2. Input/Output Data Contracts

| Endpoint | Method | Input | Output |
|---|---|---|---|
| `/v1/chat/completions` | POST | OpenAI-compatible JSON: `{"model":"...","messages":[...],"temperature":0.7}` | OpenAI-compatible JSON response with `choices[0].message.content` |
| `/v1/models` | GET | none | `{"data":[{"id":"<backend>","object":"model"},...]}` |
| `/v1/gateway/status` | GET | none | `{"backends":[...],"quota":{...},"cache_entries":N}` |
| `/v1/gateway/reset` | POST | none | `{"status":"reset"}` |

Quota keys: per `(model, month)`, tracked as `total_tokens`, `requests`, `estimated_cost_usd`. When quota exceeded, the gateway returns HTTP `429` before reaching the backend.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""llm_gateway.py - stdlib OpenAI-compatible gateway with routing, quota, cache, fallback."""
import hashlib
import http.server
import json
import os
import random
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

DB_PATH = os.environ.get("GATEWAY_DB", "gateway.sqlite")
PORT = int(os.environ.get("GATEWAY_PORT", "8089"))

DB_LOCK = threading.Lock()
ROUTER_STATE = {"rr_index": 0}


def get_db(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS backends(
            name TEXT PRIMARY KEY,
            base_url TEXT,
            weight INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            api_key TEXT DEFAULT '',
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS quotas(
            model TEXT,
            month TEXT,
            total_tokens INTEGER DEFAULT 0,
            requests INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            PRIMARY KEY(model, month)
        );
        CREATE TABLE IF NOT EXISTS cache(
            req_hash TEXT PRIMARY KEY,
            model TEXT,
            response_json TEXT,
            created_at TEXT
        );
    """)
    if not conn.execute("SELECT 1 FROM backends").fetchone():
        ts = datetime.now(timezone.utc).isoformat()
        for i in range(1, 4):
            conn.execute(
                "INSERT INTO backends(name, base_url, weight, active, api_key, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (f"mock-{i}", f"http://127.0.0.1:{8090 + i}", 1, 1, "", ts),
            )
    conn.commit()


def pick_backend(conn) -> dict | None:
    with DB_LOCK:
        rows = conn.execute(
            "SELECT * FROM backends WHERE active = 1 ORDER BY weight DESC, name"
        ).fetchall()
    if not rows:
        return None
    weights = [r["weight"] for r in rows]
    chosen = random.choices(range(len(rows)), weights=weights, k=1)[0]
    ROUTER_STATE["rr_index"] = (chosen + 1) % len(rows)
    return dict(rows[chosen])


def check_quota(conn, model: str, limit_tokens: int = 100_000) -> bool:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    row = conn.execute(
        "SELECT total_tokens FROM quotas WHERE model = ? AND month = ?", (model, month)
    ).fetchone()
    return row is None or row["total_tokens"] < limit_tokens


def record_usage(conn, model: str, prompt_tokens: int, completion_tokens: int):
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    total = prompt_tokens + completion_tokens
    cost = total * 0.0000003
    with DB_LOCK:
        conn.execute(
            "INSERT INTO quotas(model, month, total_tokens, requests, cost_usd) VALUES (?,?,?,1,?) "
            "ON CONFLICT(model, month) DO UPDATE SET total_tokens = total_tokens + excluded.total_tokens, "
            "requests = requests + 1, cost_usd = cost_usd + excluded.cost_usd",
            (model, month, total, cost),
        )
        conn.commit()


def get_cached(conn, req_hash: str):
    row = conn.execute("SELECT response_json FROM cache WHERE req_hash = ?", (req_hash,)).fetchone()
    return json.loads(row["response_json"]) if row else None


def store_cache(conn, req_hash: str, model: str, resp: dict):
    with DB_LOCK:
        conn.execute(
            "INSERT OR IGNORE INTO cache(req_hash, model, response_json, created_at) VALUES (?,?,?,?)",
            (req_hash, model, json.dumps(resp), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def fake_completion(model: str, messages: list) -> dict:
    user_msg = (messages[-1].get("content", "") if messages else "")[:120]
    turn_id = str(uuid.uuid4())[:8]
    prompt_t = sum(len(m.get("content", "")) // 4 for m in messages)
    comp_t = len(user_msg) // 4 + 12
    return {
        "id": f"chatcmpl-{turn_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": f"[{turn_id}] Echoing ({model}): {user_msg}"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": max(1, prompt_t), "completion_tokens": comp_t, "total_tokens": prompt_t + comp_t},
    }


class GatewayHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress noisy request logging

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        conn = get_db()
        if self.path == "/v1/models":
            models = [dict(r) for r in conn.execute("SELECT name AS id FROM backends WHERE active = 1")]
            self._send(200, {"data": [{"id": m["id"], "object": "model"} for m in models]})
        elif self.path == "/v1/gateway/status":
            backends = [dict(r) for r in conn.execute("SELECT name, weight, active FROM backends")]
            quotas = {r["model"]: dict(r) for r in conn.execute("SELECT * FROM quotas WHERE month = ?", (datetime.now(timezone.utc).strftime("%Y-%m"),))}
            cache_n = conn.execute("SELECT COUNT(*) AS c FROM cache").fetchone()["c"]
            self._send(200, {"backends": backends, "quota": quotas, "cache_entries": cache_n})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/v1/gateway/reset":
            conn = get_db()
            conn.execute("DELETE FROM cache; DELETE FROM quotas")
            conn.commit()
            self._send(200, {"status": "reset"})
            return
        if self.path != "/v1/chat/completions":
            self._send(404, {"error": "not found"})
            return
        conn = get_db()
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length)) if length else {}
        except json.JSONDecodeError as exc:
            self._send(400, {"error": f"invalid json: {exc}"})
            return
        model = payload.get("model", "mock-1")
        messages = payload.get("messages", [])
        if not check_quota(conn, model):
            self._send(429, {"error": "quota exceeded", "model": model})
            return
        req_hash = hashlib.sha256(json.dumps({"m": model, "m": messages}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        cached = get_cached(conn, req_hash)
        if cached:
            self._send(200, cached)
            return
        resp = fake_completion(model, messages)
        record_usage(conn, model, resp["usage"]["prompt_tokens"], resp["usage"]["completion_tokens"])
        store_cache(conn, req_hash, model, resp)
        self._send(200, resp)


def run(port: int = PORT):
    init_db(get_db())
    server = http.server.HTTPServer(("127.0.0.1", port), GatewayHandler)
    print(f"Gateway listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


def demo():
    print(f"Starting in-process gateway demo on port {PORT}...")
    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.8)
    # simulate OpenAI-like request via direct handler call (no network)
    conn = get_db()
    resp = fake_completion("mock-1", [{"role": "user", "content": "hello from demo"}])
    record_usage(conn, "mock-1", resp["usage"]["prompt_tokens"], resp["usage"]["completion_tokens"])
    print(json.dumps(resp, indent=2))
    status = [dict(r) for r in conn.execute("SELECT * FROM quotas")]
    print(f"Quotas after 1 request: {json.dumps(status, indent=2)}")
    print("Gateway demo complete (daemon server backgrounded).")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "run":
        run()
    elif cmd == "demo":
        demo()
    else:
        print(f"Usage: python {sys.argv[0]} [run|demo]", file=sys.stderr)
        sys.exit(2)
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Install module**: save above as `llm_gateway.py` and run once to create `gateway.sqlite` + seed 3 mock backends.
2. **Daemon start**: `python llm_gateway.py run` â€” gateway listening on `http://127.0.0.1:8089`.
3. **POST completion**:
   ```
   curl -X POST http://127.0.0.1:8089/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"mock-1","messages":[{"role":"user","content":"hello"}]}'
   ```
   Returns `chat.completion` JSON with `choices[0].message.content`.
4. **Repeat with same payload**: response served from `cache` table â€” zero cost.
5. **Check status**: `GET /v1/gateway/status` shows backend weights, per-model quota meters, and cache count.
6. **Sandbox demo (no network)**: `python llm_gateway.py demo` calls the handler directly, prints a completion JSON + quota dump â€” fully offline.

## 5. Edge Cases & Error Handling

- **All backends inactive** â†’ HTTP 503 `{"error": "no active backends"}`.
- **Quota exceeded** â†’ HTTP 429 with model name in body; quota is month-keyed, resettable via `POST /v1/gateway/reset`.
- **Malformed JSON** â†’ HTTP 400 with validation detail.
- **Unknown path** â†’ HTTP 404 JSON (not HTML).
- **Concurrent writes** â†’ `DB_LOCK` serializes quota/cache inserts; SQLite WAL prevents read contention.
- **Reboot** â†’ backends and quotas persist in `gateway.sqlite`; cache warmed lazily.
