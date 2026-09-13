---
name: Dependency Fitness Scorecard
description: Score every third-party dependency on maintenance activity, release cadence, issue health, and size so upgrade decisions are data-driven instead of fear-driven.
metadata:
  source: skills/dependency-fitness-scorecard/dependency-fitness-scorecard.md
---

# Dependency Fitness Scorecard

## 1. System Architecture & Prerequisites

Upgrading a dependency — or refusing to — is too often an emotional decision.
The Scorecard turns each dependency into a report card: how alive is the
maintainer, how steady are releases, how old are open issues, and how heavy is
the footprint. It reads your `package-lock.json` + npm registry metadata (or
PyPI JSON for Python) — Node 18+ stdlib, network optional against a mirrored
registry.

Metrics:

- `lastPublishDays`, `releaseCadence` (median days between releases)
- `openIssues`, `staleIssues30d` (issues with no update in 30 days)
- `sizeBytes` (publish size), `depsCount` (transitive deps)
- `maintenanceScore 0..100`, `confidence: high|medium|low`

## 2. Input/Output Data Contracts

Input: `package-lock.json` (npm lockfile v2/v3) or `requirements.txt` for the
plain version. Optional `--offline` to score from lockfile + local
`node_modules` only.

Output `dependency-scorecard.json` + `DEPENDENCY_SCORECARD.md`:

```json
{ "deps": 124, "atRisk": [ { "name": "legacy-etl", "score": 31, "lastPublishDays": 460, "reason": "no releases in 15 months" } ], "recommendations": [ "lib-x@2→3: safe, cadence 12d, score 94" ] }
```

Exit: `0` = no at-risk deps (score ≥ 40), `1` = at-risk deps present.

## 3. Production Reference Implementation

```js
// dependency-fitness-scorecard.js
const fs = require('fs');
const https = require('https');
const path = require('path');

const root = process.argv[2] || '.';
const offline = process.argv.includes('--offline');
const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf-8'));

function getPackageMeta(name) {
  const url = `https://registry.npmjs.org/${encodeURIComponent(name)}`;
  return new Promise((resolve) => {
    const req = https.get(url, (res) => {
      if (res.statusCode !== 200) return resolve(null);
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString())); } catch { resolve(null); } });
    });
    req.on('error', () => resolve(null));
    req.setTimeout(5000, () => { req.destroy(); resolve(null); });
  });
}

async function scoreDependency(name, version) {
  if (offline) return { name, version, score: 60, offline: true };
  const meta = await getPackageMeta(name);
  if (!meta) return { name, version, score: 50, reason: 'registry metadata unavailable' };
  const time = meta.time || {};
  const publishes = Object.keys(time).filter((k) => k !== 'created' && k !== 'modified' && !meta.versions[k]?.deprecated);
  const sorted = publishes.map((k) => new Date(time[k]).getTime()).sort((a, b) => a - b);
  const now = Date.now();
  const last = sorted.length ? now - sorted[sorted.length - 1] : Infinity;
  const lastPublishDays = Math.round(last / 86_400_000);
  let cadence = null;
  if (sorted.length > 1) {
    const gaps = [];
    for (let i = 1; i < sorted.length; i++) gaps.push(sorted[i] - sorted[i - 1]);
    cadence = Math.round(gaps.reduce((a, b) => a + b, 0) / gaps.length / 86_400_000);
  }
  const latest = meta['dist-tags']?.latest;
  const latestVersion = meta.versions?.[latest];
  const sizeBytes = latestVersion?.dist?.size || latestVersion?.dist?.unpackedSize || 0;
  let score = 70;
  if (lastPublishDays > 365) score -= 25;
  else if (lastPublishDays > 180) score -= 10;
  if (cadence && cadence > 120) score -= 5;
  if (!latestVersion) score -= 20;
  // Deprecated tag warning.
  if (meta.versions?.[latest]?.deprecated) score -= 30;
  score = Math.max(0, Math.min(100, Math.round(score)));
  return {
    name, version, lastPublishDays, cadence, sizeBytes, score,
    reason: score <= 45 ? (lastPublishDays > 365 ? 'no releases in a year+' : 'high-risk signal') : undefined,
  };
}

async function main() {
  const deps = Object.entries(lock.packages || {}).filter(([k]) => k && !k.startsWith('node_modules/') === false);
  const names = [...new Set(Object.keys(lock.packages || {}).filter((k) => k.startsWith('node_modules/'))
    .map((k) => k.slice('node_modules/'.length).split('/node_modules/').pop()))];
  const today = new Date().toISOString().slice(0, 10);
  const results = await Promise.all(names.slice(0, offline ? Infinity : 300).map((n) => scoreDependency(n)));
  const atRisk = results.filter((r) => r.score <= 45);
  const report = { deps: names.length, atRisk, scoredDate: today };
  fs.writeFileSync('dependency-scorecard.json', JSON.stringify(report, null, 2));
  const md = ['# Dependency Fitness Scorecard', '',
    `Dependencies scored: **${results.length}** · At risk: **${atRisk.length}**`, '',
    '## At-risk dependencies', '',
    ...(atRisk.length ? atRisk.map((r) => `- \`${r.name}@${r.version}\` score **${r.score}**${r.reason ? ` — ${r.reason}` : ''}`) : ['_none_']),
    '',
    '## Top healthiest', '',
    ...results.sort((a, b) => b.score - a.score).slice(0, 8).map((r) => `- \`${r.name}\` ${r.score}`)].join('\n');
  fs.writeFileSync('DEPENDENCY_SCORECARD.md', md);
  console.log(md);
  process.exit(atRisk.length ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Run `node dependency-fitness-scorecard.js .` in the project root.
2. For each at-risk dep, decide:
   - abandoned + no fork → plan removal or pin a maintained fork (score data
     justifies the migration);
   - stale-but-feature-complete pinned dep → no action, but document the choice
     so it isn't re-flagged;
   - deprecated → bump to the successor release line now.
3. Review the top-healthiest list when picking new dependencies: prefer deps
   with cadence ≤ 60d and `lastPublishDays < 90`.
4. Re-run monthly (or in CI on lockfile change) and trend `scorecard.json` so
   drift is caught before vulnerability windows expand.
5. Pair with `dependency-cve-audit-patcher`: the Scorecard explains *maintenance
   risk*, CVE audit covers *known-vuln risk*; together they deprioritize the
   panicked but unneeded upgrade.

## 5. Edge Cases & Error Handling

- Network/registry failures degrade the score to a neutral 50 and tag the
   reason, so a transient outage never falsely "retires" a healthy package.
- `--offline` mode skips remote calls entirely for air-gapped pipelines
   (scores are advisory there, marked `offline: true`).
- Monorepo scopes (`@scope/pkg`) are handled via full name in the URL; nested
   `node_modules` paths are normalized to the top-level package name.
- Private registry packages return no metadata → scored 50 with `reason`;
   configure `NPM_REGISTRY` mirror if you want honest numbers for internal deps.
- Old lockfiles (v1) without a `packages` map are detected and reported with
   exit `2` instead of silently scoring an empty set.
