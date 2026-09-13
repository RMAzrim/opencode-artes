---
id: golden-snapshot-migrator
file_path: skills/golden-snapshot-migrator/golden-snapshot-migrator.md
name: Golden Snapshot Migrator
category: testing
tags: [snapshot, migration, regression, dependency-upgrade, behavior-contract]
author: opencode-core
version: 1.0.0
description: Capture golden snapshots before a major library or dependency migration and diff after to keep the external behavior contract intact.
---

# Golden Snapshot Migrator

## 1. System Architecture & Prerequisites

Upgrading a library (React, Express, ORM, SDK) is scary precisely because you
cannot predict what breaks. The Migrator pins down the *current observable
behavior* as golden snapshots before the swap and diffs it after, so every
behavior change is seen and accounted for instead of discovered by users.
Node 18+ stdlib.

Core idea: snapshot = serialized observable output of a surface (render output,
HTTP handler result, DB query, function returns) keyed by a stable input probe.

## 2. Input/Output Data Contracts

Input: a directory of probe files (same contract family as refactor-safety-harness,
compatible on purpose):

- `setup()` — optional pre-migration fixtures
- `probes: [{ name, inputs, invoke }]` — list baked into one module

Baseline stored as `snapshots/<surface>.golden.json` with format
`{ name, capturedAt, fields: { <probeName>: <normalized value> } }`.

Output for the migration diff: `migration-drift.md` + `migration-drift.json`
with `{ unchanged, changed, addedMarkedOK: [] }`; exit `1` on unacknowledged drift.

## 3. Production Reference Implementation

```js
// golden-snapshot-migrator.js
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const [,, surface, mode = 'record', sourceDir = '.'] = process.argv;
if (!surface) { console.error('usage: node golden-snapshot-migrator.js <surface> [record|diff] [probeDir]'); process.exit(1); }
const GOLD = path.join(sourceDir, `snapshots/${surface}.golden.json`);

function norm(v) {
  if (Array.isArray(v)) return v.map(norm);
  if (v && typeof v === 'object') {
    const out = {};
    for (const [k, val] of Object.entries(v)) {
      if (/(?:id|_id|token|createdAt|updatedAt|expiresAt|nonce|ts)/i.test(k)) continue;
      out[k] = norm(val);
    }
    return Object.keys(out).sort().reduce((acc, k) => { acc[k] = out[k]; return acc; }, {});
  }
  return v;
}
function digest(v) { return crypto.createHash('sha256').update(JSON.stringify(norm(v))).digest('hex'); }

async function collect(surfaceMod, sourceDir) {
  const fields = {};
  for (const p of surfaceMod.probes || []) {
    try { fields[p.name] = { hash: digest(await p.invoke(p.inputs)) }; }
    catch (err) { fields[p.name] = { hash: `throw:${err.name}` }; }
  }
  return fields;
}

async function main() {
  const modPath = path.join(sourceDir, `${surface}.surface.js`);
  if (!fs.existsSync(modPath)) { console.error(`surface module not found: ${modPath}`); process.exit(2); }
  const mod = require(modPath);
  if (mod.setup) await mod.setup();

  if (mode === 'record') {
    const fields = await collect(mod, sourceDir);
    const golden = { name: surface, capturedAt: new Date().toISOString(), fields };
    fs.mkdirSync(path.dirname(GOLD), { recursive: true });
    fs.writeFileSync(GOLD, JSON.stringify(golden, null, 2));
    console.log(`golden baseline recorded for ${surface} (${Object.keys(fields).length} probes)`);
    process.exit(0);
  }

  if (!fs.existsSync(GOLD)) { console.error(`golden baseline missing: ${GOLD} — run record first`); process.exit(2); }
  const base = JSON.parse(fs.readFileSync(GOLD, 'utf-8'));
  const now = await collect(mod, sourceDir);
  const drift = [];
  for (const [name, cur] of Object.entries(now)) {
    const prev = base.fields[name];
    if (!prev) { drift.push({ name, status: 'new' }); continue; }
    if (prev.hash !== cur.hash) drift.push({ name, status: 'changed' });
  }
  const unchanged = Object.keys(now).length - drift.filter((d) => d.status === 'new').length - drift.filter((d) => d.status === 'changed').length;
  const report = { unchanged, changed: drift.filter((d) => d.status === 'changed').map((d) => d.name), added: drift.filter((d) => d.status === 'new').map((d) => d.name) };
  fs.writeFileSync('migration-drift.json', JSON.stringify(report, null, 2));
  const md = ['# Migration Drift', '', `Surface: ${surface}`, `Unchanged: ${unchanged}`, `Changed: ${report.changed.length}`, `New: ${report.added.length}`, ''];
  report.changed.forEach((c) => md.push(`- CHANGED ${c}`));
  report.added.forEach((a) => md.push(`- new ${a}`));
  fs.writeFileSync('migration-drift.md', md.join('\n'));
  console.log(md.join('\n'));
  process.exit(report.changed.length ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
```

Example surface module:

```js
// api.surface.js
const { callOrderApi } = require('../src/orders');
const { callUserApi } = require('../src/users');
module.exports = {
  async setup() { /* seed DB, stand up test server */ },
  probes: [
    { name: 'orders-list', inputs: [{ limit: 10 }], async invoke([q]) { return callOrderApi('/orders', q); } },
    { name: 'user-create-invalid', inputs: [{ email: 'nope' }], async invoke([b]) { return callUserApi('/users', { method: 'POST', body: b }); } },
  ],
};
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Identify the migration surface (auth, render, DB, HTTP) and write one
   `*.surface.js` per bounded surface with 10–30 probes covering happy path,
   empty, boundary, and invalid inputs.
2. **Before** the upgrade: `node golden-snapshot-migrator.js api record .`.
   Commit the `.golden.json`.
3. Upgrade the dependency (e.g. `npm i express@5`), fix compile errors only.
4. `node golden-snapshot-migrator.js api diff .` — every `CHANGED` line is a
   behavior change. Review one by one:
   - intentional breaking change → capture new baseline + document it;
   - unintentional → treat as a regression and fix.
5. Confirm `changed: 0` after acknowledged changes, update the golden
   baseline, and run the normal test suite.

## 5. Edge Cases & Error Handling

- Thrown errors become a stable marker (`throw:ErrorName`) so a
   previously-returning path that now throws is visible instead of crashing.
- Hash comparison is order-insensitive within objects — `norm()` recursively
   sorts keys so key reordering doesn't trip the diff; array element order is
   still significant (sequences have meaning).
- Volatile fields are excluded by regex, so UUIDs and timestamps in the
   response never produce phantom changes.
- Missing baseline or surface module exits `2` (config error) — distinct from
   drift exit `1` — so CI can tell "not configured" from "behavior changed".
- Non-deterministic probes (random, clock) must be frozen in `setup`, matching
   the same discipline as refactor-safety-harness.