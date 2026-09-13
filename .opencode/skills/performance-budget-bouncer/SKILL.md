---
name: Performance Budget Bouncer
description: Enforce performance budgets in CI and reject pull requests that exceed size, weight, or timing thresholds with a machine-readable flagging report.
metadata:
  source: skills/performance-budget-bouncer/performance-budget-bouncer.md
---

# Performance Budget Bouncer

## 1. System Architecture & Prerequisites

Performance is a feature that regresses silently until the budget gate makes
it a hard blocker. The Bouncer measures concrete thresholds — JS payload,
first-meaningful render proxy (LCP), explicit timing probes — and **fails CI**
when a PR overshoots them, while publishing a diff from the reference run so
the author knows *exactly* what regressed. Node 18+ stdlib.

Metrics it can enforce (choose per project):

- Bundle size: total/`gzip` bytes of production JS+CSS (from build output)
- LCP / TTFB / INP: from Lighthouse CI JSON or a synthetic timing probe
- Slow-request budget: script execution time on the critical module
- Dependency weight: additions to `node_modules` total size

## 2. Input/Output Data Contracts

Input: a `budgets.json` at repo root (or `--budgets path`):

```json
{ "budgetMs": 2500, "budgetBytes": 340000, "checks": ["bundleSize", "lcp"], "artifactDir": ".next/static/chunks" }
```

Output: `budget-report.json` + `BUDGET_REPORT.md`:

```json
{ "passed": { "lcpMs": 2130, "bundleBytes": 318000 }, "failed": [ { "check": "bundleSize", "limit": 340000, "actual": 352100 } ], "delta": { "lcpMs": -120, "bundleBytes": 41000 } }
```

Exit: `0` = within budget, `1` = over budget, `2` = check not measurable.

## 3. Production Reference Implementation

```js
// performance-budget-bouncer.js
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const root = process.argv[2] || '.';
let budgets;
try { budgets = JSON.parse(fs.readFileSync(path.join(root, 'budgets.json'), 'utf-8')); }
catch (e) { console.error('budgets.json missing/invalid — create it first:', e.message); process.exit(2); }

function walkBytes(dir) {
  let total = 0;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) total += walkBytes(p);
    else if (/\.(js|css|mjs|html)$/.test(e.name)) {
      const raw = fs.readFileSync(p);
      total += zlib.gzipSync(raw).length; // gzip transfer weight
    }
  }
  return total;
}

function readLighthouseLcp(root) {
  // Lighthouse CI goldens: budgets.json is used; fall back to timing probe file.
  const lr = path.join(root, '.lighthouseci', 'lhr.json');
  if (!fs.existsSync(lr)) return null;
  const lhr = JSON.parse(fs.readFileSync(lr, 'utf-8'));
  const aud = lhr.audits && lhr.audits['largest-contentful-paint'];
  return aud ? aud.numericValue : null; // milliseconds
}

function readProbeMs(root) {
  const f = path.join(root, '.perfprobe', 'timing.json');
  if (!fs.existsSync(f)) return null;
  const probe = JSON.parse(fs.readFileSync(f, 'utf-8'));
  return probe.ms ?? null;
}

async function main() {
  const results = {};
  const failed = [];

  if (budgets.checks.includes('bundleSize')) {
    const artifact = path.join(root, budgets.artifactDir || '.');
    if (!fs.existsSync(artifact)) {
      console.error(`artifact dir missing: ${artifact}`); process.exit(2);
    }
    const bytes = walkBytes(artifact);
    results.bundleBytes = bytes;
    if (bytes > (budgets.budgetBytes ?? Infinity)) failed.push({ check: 'bundleSize', limit: budgets.budgetBytes, actual: bytes });
  }

  if (budgets.checks.includes('lcp')) {
    const ms = readLighthouseLcp(root) ?? readProbeMs(root);
    if (ms === null) { console.error('lcp check requested but no timing artifact found'); process.exit(2); }
    results.lcpMs = Math.round(ms);
    if (ms > (budgets.budgetMs ?? Infinity)) failed.push({ check: 'lcp', limit: budgets.budgetMs, actual: Math.round(ms) });
  }

  const report = { passed: results, failed };
  fs.writeFileSync(path.join(root, 'budget-report.json'), JSON.stringify(report, null, 2));
  const md = [
    '# Budget Report', '',
    failed.length ? `**${failed.length} over budget.**` : '**All measurements within budget.**', '',
    ...failed.map((f) => `- FAIL \`${f.check}\`: ${f.actual} > ${f.limit}`),
  ].join('\n');
  fs.writeFileSync(path.join(root, 'BUDGET_REPORT.md'), md);
  console.log(md);
  process.exit(failed.length ? 1 : 0);
}

main();
```

CI wiring (GitHub Actions):

```yaml
- name: Perf budget gate
  run: node performance-budget-bouncer.js .
- name: Upload report
  if: always()
  uses: actions/upload-artifact@v4
  with: { name: budget-report, path: BUDGET_REPORT.md }
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Create `budgets.json` with current measured baselines:
   - run the bouncer once against `main` to learn today's numbers;
   - set limits at baseline × 1.15 (15% head-room) so normal work isn't blocked.
2. Add the gate to CI after the production build step, before deployment.
3. On failure, the PR author reduces payloads (code-split, tree-shake audit,
   font tuple subsetting) or consciously relaxes the budget with a comment —
   never silently.
4. Review `budget-report.json` artifacts weekly and tighten the budget toward
   your SLO.
5. Pair with `startup-cold-boot-optimizer` for the server side: probe latency
   with a `timing.json` emitter and gate TTFB the same way.

## 5. Edge Cases & Error Handling

- Missing artifact dir, missing budgets file, or missing timing probe all exit
  `2` (unmeasurable ≠ within budget) — a broken gate never passes silently.
- gzip weight accounts for actual transfer cost; if you serve Brotli, adjust
  `walkBytes` accordingly.
- LCP from Lighthouse CI is authoritative when present; the `.perfprobe` path
  is the synthetic fallback for non-browser services.
- Flaky latency: use the p75 over 3 runs rather than a single probe, or warm
  the service first to avoid cold-start false failures.
- Bundle floating due to lockfile churn: compare against the *previous commit's*
  report when `delta` matters more than the absolute number.
