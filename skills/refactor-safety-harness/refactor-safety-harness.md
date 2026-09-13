---
id: refactor-safety-harness
file_path: skills/refactor-safety-harness/refactor-safety-harness.md
name: Refactor Safety Harness
category: core-coding
tags: [refactoring, golden-tests, characterization-testing, safety-net, regression]
author: opencode-core
version: 1.0.0
description: Record golden outputs of current behavior before a refactor, then diff outputs after to prove behavior is unchanged.
---

# Refactor Safety Harness

## 1. System Architecture & Prerequisites

A golden (characterization) harness captures the observable output of a code
unit before a refactor and re-runs the same probes after, failing loudly on
any behavioral drift. Node 18+ (no third-party deps for core flow).

- Target functions/procedures must be importable and deterministic for the
  probe inputs; non-determinism (timestamps, random, network) must be injected
  or frozen.
- Harness stores recordings as `destination/before/` and compares against a
  re-run emitted into `destination/after/`.

## 2. Input/Output Data Contracts

Input: a probe script exporting `{ name, setup?, inputs, invoke }`.

- `setup(): Promise<void>` — optional fixture preparation.
- `inputs: unknown[]` — argument tuples passed to `invoke`.
- `invoke(args: unknown[]) => Promise<unknown> | unknown` — the unit under test.
- `name: string` — stable identifier used for the golden file.

Output: normalized JSON payloads `<name>.json` per probe plus a `DRIFT_REPORT.md`.

## 3. Production Reference Implementation

```js
// refactor-safety-harness.js
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const [,, dir, mode = 'record'] = process.argv;
if (!dir) { console.error('usage: node refactor-safety-harness.js <dir> [record|verify]'); process.exit(1); }

// Normalizes volatile fields so timestamps/uuids do not create false drift.
function normalize(v) {
  if (Array.isArray(v)) return v.map(normalize);
  if (v && typeof v === 'object') {
    const out = {};
    for (const [k, val] of Object.entries(v)) {
      if (/^(id|uuid|_id|createdAt|updatedAt|ts|timestamp)$/i.test(k)) continue;
      out[k] = normalize(val);
    }
    return out;
  }
  return v;
}

function render(v) {
  const json = JSON.stringify(normalize(v), null, 2);
  return crypto.createHash('sha256').update(json).digest('hex') + '\n' + json;
}

async function main() {
  const probes = fs.readdirSync(dir).filter((f) => f.endsWith('.probe.js'));
  if (!probes.length) { console.error(`no *.probe.js found in ${dir}`); process.exit(1); }

  const beforeDir = path.join(dir, 'before');
  const afterDir = path.join(dir, 'after');
  if (mode === 'record') {
    fs.rmSync(beforeDir, { recursive: true, force: true });
    fs.mkdirSync(beforeDir, { recursive: true });
  } else {
    fs.mkdirSync(afterDir, { recursive: true });
  }

  let drift = 0;
  const report = ['# Drift Report', ''];

  for (const file of probes) {
    const mod = require(path.join(dir, file));
    if (mod.setup) await mod.setup();
    let result;
    try {
      result = await mod.invoke(mod.inputs);
    } catch (err) {
      result = { __threw: err.name, __message: err.message };
    }
    const name = mod.name || file.replace('.probe.js', '');
    if (mode === 'record') {
      fs.writeFileSync(path.join(beforeDir, `${name}.json`), render(result));
      report.push(`- [${mode}] ${name}: recorded`);
    } else {
      const beforeRaw = fs.readFileSync(path.join(beforeDir, `${name}.json`), 'utf-8');
      const afterRaw = render(result);
      if (beforeRaw === afterRaw) {
        report.push(`- [verify] ${name}: MATCH`);
      } else {
        drift++;
        fs.writeFileSync(path.join(afterDir, `${name}.json`), afterRaw);
        report.push(`- [verify] ${name}: DRIFT -> ${file}`);
      }
    }
  }

  if (mode === 'verify') {
    fs.writeFileSync(path.join(dir, 'DRIFT_REPORT.md'), report.join('\n') + '\n');
    console.log(drift ? `FAIL: ${drift} probe(s) drifted. See ${'DRIFT_REPORT.md'}` : 'PASS: all probes matched.');
    process.exit(drift ? 1 : 0);
  } else {
    fs.writeFileSync(path.join(dir, 'DRIFT_REPORT.md'), report.join('\n') + '\n');
    console.log(`recorded ${probes.length} probe(s) into before/.`);
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
```

Example probe:

```js
// order.total.probe.js
const { computeTotal } = require('../src/order');
module.exports = {
  name: 'order-total',
  inputs: [ { items: [ { qty: 2, price: 1.5 }, { qty: 1, price: 4.0 } ], taxRate: 0.1 } ],
  async invoke([order]) { return computeTotal(order); },
};
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Write one `*.probe.js` per unit you plan to touch, covering boundary-heavy
   inputs (empty, negatives, max values, nulls).
2. Before touching code: `node refactor-safety-harness.js ./probes record`.
3. Refactor as planned.
4. Re-run: `node refactor-safety-harness.js ./probes verify`.
5. Inspect `after/` diffs for genuine behavior changes; iterate until PASS.
6. Run your real test suite on top — golden tests supplement, never replace,
   assertion-based tests.

## 5. Edge Cases & Error Handling

- Thrown errors are captured as `__threw/__message` objects so "now throws" vs
  "used to return" is a first-class drift signal, not a crash.
- Normalization drops id/date-shaped fields; extend the regex if your domain
  uses different volatile keys.
- Async setup failures abort the run with a non-zero exit so a broken probe
  is never mistaken for a passing verification.
- Ordering: `inputs` may be a single tuple; `invoke` receives it as-is to keep
  the probe contract tiny.
- Determinism caveat: if a unit reads global state (env, clock), freeze it in
  `setup` before recording, or drift will be a false alarm.