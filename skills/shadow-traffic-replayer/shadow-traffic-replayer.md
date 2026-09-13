---
id: shadow-traffic-replayer
file_path: skills/shadow-traffic-replayer/shadow-traffic-replayer.md
name: Shadow Traffic Replayer
category: testing
tags: [replay, shadow-traffic, regression, api-testing, traffic-capture]
author: opencode-core
version: 1.0.0
description: Replay recorded production HTTP traffic against a new build and diff responses to surface API regressions without writing a single test.
---

# Shadow Traffic Replayer

## 1. System Architecture & Prerequisites

Regression testing usually requires hand-written cases, but the *most
realistic* corpus is production traffic. The Replayer captures real
request/response pairs, replays them against a candidate build, and diffs
status + normalized JSON bodies to flag everything that silently changed.
Node 18+ stdlib (uses `http/https` only).

Two modi operandi:

- **Capture mode** — a tiny proxy records traffic in front of the live API.
- **Replay mode** — replays each recorded request to the candidate base URL
  and computes compatibility deltas.

## 2. Input/Output Data Contracts

Capture record (JSON Lines, one request+response per line):

```json
{ "id": "req_001", "method": "POST", "path": "/orders", "headers": { "content-type": "application/json" }, "body": "{}", "status": 201, "responseBody": "{\"id\":1}", "responseHeaders": {} }
```

Output: `replay-report.md` + `replay-report.json`:

```json
{ "replayed": 1200, "passed": 1178, "deltas": 22, "breaking": [ { "id": "req_042", "path": "/orders", "oldStatus": 201, "newStatus": 404 } ] }
```

Exit: `0` = no breaking deltas, `1` = breaking deltas.

## 3. Production Reference Implementation

```js
// shadow-traffic-replayer.js
const fs = require('fs');
const http = require('http');
const https = require('https');

const [,, mode] = process.argv;

// ---------- Capture: forward proxy that records traffic ----------
if (mode === 'capture') {
  const UPSTREAM = process.env.UPSTREAM || 'http://localhost:4000';
  const PORT = Number(process.env.PORT || 8081);
  const FILE = process.env.OUTFILE || './traffic.nl';
  const ws = fs.createWriteStream(FILE, { flags: 'a' });
  const upstream = new URL(UPSTREAM);

  const server = http.createServer((req, res) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => {
      const body = Buffer.concat(chunks).toString('utf-8');
      const client = upstream.protocol === 'https:' ? https : http;
      const preq = client.request({
        host: upstream.hostname, port: upstream.port || (upstream.protocol === 'https:' ? 443 : 80),
        path: req.url, method: req.method, headers: { ...req.headers, host: upstream.host },
      }, (pres) => {
        const rchunks = [];
        pres.on('data', (c) => rchunks.push(c));
        pres.on('end', () => {
          const respBody = Buffer.concat(rchunks).toString('utf-8');
          ws.write(JSON.stringify({
            id: `req_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
            method: req.method, path: req.url,
            headers: { 'content-type': req.headers['content-type'] || '' },
            body, status: pres.statusCode, responseBody: respBody,
          }) + '\n');
          res.writeHead(pres.statusCode, pres.headers); res.end(respBody);
        });
      });
      preq.on('error', () => { res.writeHead(502); res.end('upstream error'); });
      preq.end(body);
    });
  });
  server.listen(PORT, () => console.log(`capturing traffic on :${PORT} -> ${UPSTREAM} (${FILE})`));
  process.exit(0);
}

// ---------- Replay: compare recorded traffic against candidate ----------
const CANDIDATE = new URL(process.env.CANDIDATE || 'http://localhost:3000');
const SRC = './traffic.nl';

function stable(value) {
  const json = JSON.stringify(value, (k, v) => /^(id|_id|createdAt|updatedAt|ts|token)$/i.test(k) ? undefined : v);
  return Buffer.from(json).toString('base64');
}

async function replayOne(line) {
  const rec = JSON.parse(line);
  const httpMod = CANDIDATE.protocol === 'https:' ? https : http;
  const headers = { ...rec.headers, host: CANDIDATE.host };
  if (rec.body) headers['content-length'] = Buffer.byteLength(rec.body);
  return new Promise((resolve) => {
    const req = httpMod.request({ host: CANDIDATE.hostname, port: CANDIDATE.port || (CANDIDATE.protocol === 'https:' ? 443 : 80), path: rec.path, method: rec.method, headers, timeout: 10_000 }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        const body = Buffer.concat(chunks).toString('utf-8');
        let newJson = null;
        try { newJson = safeParse(body); } catch {}
        let oldJson = null;
        try { oldJson = safeParse(rec.responseBody); } catch {}
        const statusBreak = res.statusCode !== rec.status;
        const bodyBreak = res.statusCode < 500 && newJson !== oldJson;
        resolve({ rec, status: res.statusCode, body, statusBreak, bodyBreak });
      });
    });
    req.on('error', () => resolve({ rec, status: 0, body: '', statusBreak: true, bodyBreak: true }));
    req.on('timeout', () => { req.destroy(); });
    if (rec.body) req.write(rec.body);
    req.end();
  });
}

function safeParse(s) { try { return JSON.parse(s); } catch { return s; } }

async function main() {
  const lines = fs.readFileSync(SRC, 'utf-8').split(/\r?\n/).filter(Boolean);
  let passed = 0; const breaking = [];
  for (const line of lines) {
    const r = await replayOne(line);
    if (r.statusBreak) breaking.push({ id: r.rec.id, path: r.rec.path, oldStatus: r.rec.status, newStatus: r.status, reason: 'status' });
    else if (r.bodyBreak) breaking.push({ id: r.rec.id, path: r.rec.path, oldStatus: r.rec.status, newStatus: r.status, reason: 'body' });
    else passed++;
  }
  const report = { replayed: lines.length, passed, deltas: breaking.length, breaking };
  fs.writeFileSync('replay-report.json', JSON.stringify(report, null, 2));
  const md = ['# Shadow Replay Report', '', `Replayed: ${lines.length} · Passed: ${passed} · Breaking: ${breaking.length}`, ''];
  breaking.slice(0, 30).forEach((b) => md.push(`- \`${b.id}\` ${b.path} — ${b.oldStatus}->${b.newStatus} (${b.reason})`));
  fs.writeFileSync('replay-report.md', md.join('\n'));
  console.log(md.join('\n'));
  process.exit(breaking.length ? 1 : 0);
}

if (mode === 'replay' && require.main === module) main();
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Capture a representative window against stable production:
   `UPSTREAM=http://prod:80 PORT=8081 OUTFILE=traffic.nl node shadow-traffic-replayer.js capture`
   and route a subset of clients through it (or replay an existing access-log
   generator). Capture until you have thousands of records across read + write
   verbs.
2. Sanitize records of sensitive payloads (redact `authorization` headers +
   personal body fields) before storing the corpus in the repo.
3. Point at your candidate build:
   `CANDIDATE=http://localhost:3000 node shadow-traffic-replayer.js replay`.
4. Triage `breaking` deltas: sort into *intentional* (versioned, document in
   CHANGELOG) vs *regressions* — every regression becomes a real
   pytest/Jest/Playwright test so the suite learns from the replay.
5. Promote the corpus into CI with a deterministic seed subset so the budget
   stays small (~200 representative calls) and runs on every PR.

## 5. Edge Cases & Error Handling

- Volatile fields (`id`, `token`, timestamps) are normalized before body
  comparison to avoid false drift.
- Non-JSON bodies compare as raw strings; large binary blobs should be excluded
  from capture by capture filter to keep the corpus portable.
- Timeouts (10s) treat a slow candidate as a breaking delta — pre-warm the
  candidate before replay to avoid cold-start false alarms.
- New endpoints the candidate never returns for an old path are surfaced as a
  body delta, not silently skipped.
- Write-path replays can mutate the candidate; point a throwaway or a sandbox
  database at it, never production.