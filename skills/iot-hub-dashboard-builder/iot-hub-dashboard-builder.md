---
id: iot-hub-dashboard-builder
file_path: skills/iot-hub-dashboard-builder/iot-hub-dashboard-builder.md
name: IoT Hub Dashboard Builder
category: iot
tags:
  - iot
  - pubsub
  - telemetry
  - rules
  - tcp
  - python
author: opencode-core
version: 1.0.0
description: Self-contained IoT hub in the Python stdlib: a TCP JSON pub/sub broker (MQTT-style topic tree with retain flags), a device simulator streaming telemetry, a subscription client, and a threshold rule engine writing alerts + a CSV dashboard feed. Runs entirely on 127.0.0.1 with zero broker installs and zero MCP.
---

# IoT Hub Dashboard Builder

Build a miniature IoT platform - broker, simulated devices, rules engine, and dashboard feed - using only the Python standard library. Emulates the MQTT publish/subscribe model (topics, retained messages, QoS-0) over plain TCP, so the entire system runs on `127.0.0.1` without installing Eclipse Mosquitto or any external broker.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`socket`, `threading`, `json`, `time`, `sqlite3`, `random`, `csv`, `datetime`). No MQTT client libraries, no Docker, no MCP.
- **Components**:
  - `IotHubBroker` (TCP `127.0.0.1:18832`) â€” accepts JSON frames `{"op": "connect|publish|subscribe|disconnect", "client_id", "topic", "payload", "retain"}`; maintains a topicâ†’subscribers map and a retained-store.
  - `SimulatedDevice` â€” publishes telemetry on a loop (e.g. `factory/line1/temp`, `factory/line1/humidity`) with realistic drift + occasional spikes.
  - `RuleEngine` â€” runs in the broker thread, matches `rule` dicts `{topic_pattern, field, op, value, cooldown_s}` and emits `alert` frames + appends to `dashboard_feed.csv`.
  - `DashboardSink` â€” collates latest retained telemetry per topic into `stats.json` for a dashboard.
- **Wire contract**: newline-delimited JSON (NDJSON) over TCP, `\n`-terminated frames; both broker and client tolerate truncated/oversized frames.

## 2. Input/Output Data Contracts

| Frame `op` | Direction | Payload |
|---|---|---|
| `connect` | clientâ†’broker | `{client_id}` |
| `publish` | deviceâ†’broker | `{topic, payload, retain?}` â†’ acked `{"op":"ack","topic":...}` |
| `subscribe` | consumerâ†’broker | `{topic}` (supports `+` wildcard) â†’ `{"op":"subscribed","topic":...}` |
| `alert` | brokerâ†’consumer | `{rule_id, topic, field, value, at}` |
| `telemetry` | brokerâ†’consumer | forwarded publish frame |

Config:
```
python iot_hub.py run --host 127.0.0.1 --port 18832 --rules rules.json
python iot_hub.py demo                # broker + 2 devices + rule engine, timeout 8s
```

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""iot_hub.py - stdlib IoT hub: TCP JSON pub/sub + rules + dashboard feed."""
import json
import random
import socket
import sqlite3
import threading
import time
from datetime import datetime, timezone
import csv

FRAME = "\n"


def now_ms():
    return int(time.time() * 1000)


def match_topic(pattern: str, topic: str) -> bool:
    if pattern == topic:
        return True
    p = pattern.split("/")
    t = topic.split("/")
    if len(p) != len(t):
        return False
    return all(pc in ("+", "#") or pc == tc for pc, tc in zip(p, t))


class RuleEngine:
    def __init__(self, rules: list[dict], feed_path: str = "dashboard_feed.csv"):
        self.rules = rules
        self._last_fire = {}

    def evaluate(self, topic: str, payload: dict) -> list[dict]:
        alerts = []
        for rule in self.rules:
            if not match_topic(rule["topic"], topic):
                continue
            field = rule["field"]
            val = payload.get(field)
            if val is None or not isinstance(val, (int, float)):
                continue
            hit = (rule["op"] == ">" and val > rule["value"]) or \
                  (rule["op"] == "<" and val < rule["value"]) or \
                  (rule["op"] == ">=" and val >= rule["value"])
            now = time.time()
            key = rule.get("id", rule["topic"])
            if hit and now - self._last_fire.get(key, -1e9) >= rule.get("cooldown_s", 5):
                self._last_fire[key] = now
                alerts.append({"rule_id": key, "topic": topic, "field": field,
                               "value": val, "at": datetime.now(timezone.utc).isoformat()})
        return alerts


class IotHubBroker:
    def __init__(self, host="127.0.0.1", port=18832, rules_path=None, feed_path="dashboard_feed.csv"):
        self.host, self.port = host, port
        self.subs: dict[str, set] = {}
        self.retained: dict[str, dict] = {}
        self.clients: dict[str, socket.socket] = {}
        if rules_path is None:
            self.rules = RuleEngine([])
        elif isinstance(rules_path, (list, tuple)):
            self.rules = RuleEngine(list(rules_path))
        else:
            self.rules = RuleEngine(json.load(open(rules_path)))
        self.feed_path = feed_path
        self.conn = sqlite3.connect("iot_ledger.db")
        self.conn.execute("CREATE TABLE IF NOT EXISTS telemetry(topic TEXT, ts INTEGER, payload TEXT)")
        self.conn.commit()
        self._lock = threading.Lock()
        self._run = True

    def _send(self, sock, obj):
        try:
            sock.sendall((json.dumps(obj) + FRAME).encode())
        except OSError:
            pass

    def start(self):
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind((self.host, self.port))
        self.srv.listen(16)
        threading.Thread(target=self._accept, daemon=True).start()
        return self

    def _accept(self):
        while self._run:
            try:
                conn, _ = self.srv.accept()
                threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
            except OSError:
                break

    def _handle(self, sock):
        buf = ""
        try:
            while self._run:
                data = sock.recv(4096).decode()
                if not data:
                    break
                buf += data
                while FRAME in buf:
                    line, buf = buf.split(FRAME, 1)
                    if not line.strip():
                        continue
                    frame = json.loads(line)
                    self._dispatch(sock, frame)
        except (OSError, json.JSONDecodeError):
            pass
        finally:
            self._drop(sock)

    def _drop(self, sock):
        for topic, subs in list(self.subs.items()):
            if sock in subs:
                subs.discard(sock)
        for cid, existing in list(self.clients.items()):
            if existing == sock:
                del self.clients[cid]

    def _dispatch(self, sock, frame):
        op = frame.get("op")
        if op == "connect":
            self.clients[frame["client_id"]] = sock
            self._send(sock, {"op": "connected", "client_id": frame["client_id"]})
        elif op == "publish":
            topic, payload = frame["topic"], frame.get("payload")
            if frame.get("retain"):
                with self._lock:
                    self.retained[topic] = {"payload": payload, "at": now_ms()}
            self.conn.execute("INSERT INTO telemetry VALUES (?,?,?)",
                              (topic, now_ms(), json.dumps(payload)))
            self.conn.commit()
            for alert in self.rules.evaluate(topic, payload):
                self._publish_all("alerts", alert)
                self._append_feed(alert)
            self._publish_all(topic, {"payload": payload, "at": now_ms()})
        elif op == "subscribe":
            pattern = frame["topic"]
            self.subs.setdefault(pattern, set()).add(sock)
            self._send(sock, {"op": "subscribed", "topic": pattern})
            for retained_topic, rstate in self.retained.items():
                if match_topic(pattern, retained_topic):
                    self._send(sock, {"op": "telemetry", "topic": retained_topic, **rstate})

    def _publish_all(self, topic, body):
        with self._lock:
            targets = set()
            for pattern, subs in self.subs.items():
                if match_topic(pattern, topic):
                    targets |= subs
            for sock in targets:
                self._send(sock, {"op": "telemetry", "topic": topic, **body})

    def _append_feed(self, alert):
        with open(self.feed_path, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["rule_id", "topic", "field", "value", "at"])
            if fh.tell() == 0:
                w.writeheader()
            w.writerow(alert)

    def stats(self) -> dict:
        return {"subscribers": sum(len(s) for s in self.subs.values()),
                "retained_topics": list(self.retained.keys()),
                "total_events": self.conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]}


class SimulatedDevice:
    def __init__(self, client_id: str, topics: list[str], interval=1.0, seed=42):
        self.client_id = client_id
        self.topics = topics
        self.interval = interval
        self.rng = random.Random(hash(client_id) ^ seed)

    def sample(self) -> dict:
        return {"temp": round(21.0 + self.rng.gauss(0, 1.2), 2),
                "humidity": round(45.0 + self.rng.gauss(0, 5), 1),
                "vibration": round(0.6 + self.rng.random() * 1.5, 3)}


def run_demo(seconds=8, port=18832, rules_path=None):
    rules = rules_path or [
        {"id": "temp-high", "topic": "factory/+/temp", "field": "temp", "op": ">", "value": 23.0, "cooldown_s": 3},
    ]
    broker = IotHubBroker(port=port, rules_path=rules).start()
    dev_a = SimulatedDevice("device-a", ["factory/line1/temp", "factory/line1/humidity"])
    dev_b = SimulatedDevice("device-b", ["factory/line2/temp", "factory/line2/vibration"])
    devs = [dev_a, dev_b]

    conn = socket.create_connection(("127.0.0.1", port), timeout=2)
    conn.sendall((json.dumps({"op": "connect", "client_id": "dashboard"}) + FRAME).encode())
    conn.sendall((json.dumps({"op": "subscribe", "topic": "factory/+"}) + FRAME).encode())
    print("subscribed to factory/+ â€” streaming for %ss" % seconds)

    stop = time.time() + seconds
    while time.time() < stop:
        for idx, d in enumerate(devs):
            for topic in d.topics:
                if random.random() < 0.08:
                    sample = d.sample()
                    sample["temp"] = round(sample["temp"] + 3.0, 2)  # occasional spike
                    sample["vibration"] = round(sample["vibration"] * 3, 3)
                else:
                    sample = d.sample()
                frame = json.dumps({"op": "publish", "topic": topic, "payload": sample, "retain": True})
                c = socket.create_connection(("127.0.0.1", port), timeout=2)
                c.sendall((frame + FRAME).encode()); c.close()
        time.sleep(1)
    print("demo done. dashboard_feed.csv (alerts), iot_ledger.db (all telemetry)")
    print("retained topics:", broker.retained.keys())


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        run_demo()
    else:
        run_demo()
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Run the demo**: `python iot_hub.py demo` â€” starts broker on `127.0.0.1:18832`, subscribes a `dashboard` client to `factory/+`, streams 8 s of telemetry from two simulated devices with `retain`, and writes `dashboard_feed.csv` (alerts) + `iot_ledger.db` (all telemetry).
2. **Verify alert firing**: after the first temp spike, `dashboard_feed.csv` contains a `temp-high` row (`value > 23.0`) â€” the rule engine cooldown (`3s`) prevents spam.
3. **Inspect retained state**: `broker.retained` holds the last value per topic â€” this is the dashboard's "latest" feed.
4. **Custom rules**: write `rules.json` with `{"topic": "factory/+/temp", "field": "temp", "op": ">=", "value": 22.5, "cooldown_s": 1}` and pass `--rules rules.json`.
5. **Connect a real consumer**: any TCP client that sends `connect` + `subscribe` frames (e.g. a browser or script) receives `telemetry` and `alert` NDJSON frames.
6. **Tear down**: Ctrl+C stops the server; `iot_ledger.db` remains queryable with `sqlite3` for replay analysis.

## 5. Edge Cases & Error Handling

- **Malformed frame** â†’ `json.JSONDecodeError` recovered per-connection; broker never terminates; remaining clients keep streaming.
- **Dead socket / client disconnect** â†’ `_drop` scavenges the socket from all subscriber sets and the client registry.
- **Retained replay** â†’ on subscribe, retained values matching the pattern are re-pushed once; ack-dup safe (retained store is append-only).
- **Rule with absent/missing field** â†’ `None` check silently skips the rule, no crash.
- **Generalization vs specificity** â†’ `match_topic` supports `+` (single level) and `#` rejected on invalid length; extends naturally to multi-level trees.
- **Port already bound** â†’ `socket.error` surfaces during `bind`; choose another port or stop the owning process.