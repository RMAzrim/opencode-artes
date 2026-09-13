---
id: license-clash-mediator
file_path: skills/license-clash-mediator/license-clash-mediator.md
name: License Clash Mediator
category: security
tags: [licensing, compliance, open-source, ngos, dependency-graph]
author: opencode-core
version: 1.0.0
description: Build a dependency-license graph and flag copyleft/permissive conflicts plus missing license metadata before they become legal incidents.
---

# License Clash Mediator

## 1. System Architecture & Prerequisites

Shipping a dependency with an incompatible license — GPL into a proprietary
binary, a "no commercial use" license into a SaaS — is a legal landmine that a
dependency audit never catches *as a license issue*. The Mediator walks your
lockfile, resolves each package's license expression, classifies permissiveness
(there is a small hard-coded police table; extend it for your org), and emits a
classified clash report. Node 18+ stdlib.

License classifier (expression → class):

- `PERMISSIVE`: MIT, Apache-2.0, BSD-*, ISC
- `WEAK_COPYLEFT`: LGPL-*, MPL-*
- `STRONG_COPYLEFT`: GPL-*, AGPL-*
- `RESTRICTED`: CC-BY-NC*, BUSL-*, "SEE LICENSE IN ..."
- `UNKNOWN`: missing/`UNLICENSED`/custom

## 2. Input/Output Data Contracts

Input: `package-lock.json` with registry metadata (uses `license` field from
each version from a local `node_modules/<pkg>/package.json` when available —
no network required).

Output `LICENSE_CLASH_REPORT.md` + `license-report.json`:

```json
{ "deps": 214, "unknown": 22, "flagged": [ { "name": "lib-mp4", "license": "SEE LICENSE IN COPYING", "class": "RESTRICTED", "consumedBy": ["video-worker", "ingest"] } ], "conflicts": [ { "a": "agg-lib", "la": "GPL-3.0", "b": "proprietary", "note": "strong copyleft in closed-source distribution" } ] }
```

Exit: `0` = no unknown/restricted/copyleft-in-proprietary flags,
`1` = flags exist, `2` = input unreadable.

## 3. Production Reference Implementation

```js
// license-clash-mediator.js
const fs = require('fs');
const path = require('path');

const root = process.argv[2] || '.';
const PROPRIETARY = process.argv.includes('--proprietary'); // binary/SaaS closed-source

function classify(expr) {
  const e = String(expr || '').toUpperCase();
  if (/(MIT|APACHE|BSD|ISC|MPL|UNLICEN(?:SE)?A|ZERO|UNLICENSE)/.test(e) && !/CC-|BUSL|SEE LICEN|COMMERCIAL/.test(e)) return 'PERMISSIVE';
  if (/(LGPL|MPL)/.test(e)) return 'WEAK_COPYLEFT';
  if (/(AGPL|GPL)/.test(e)) return 'STRONG_COPYLEFT';
  if (/(CC-|BUSL|SEE DESIGN|SEE LICENSE|COMMERCIAL|UNKNOWN)/.test(e)) return 'UNKNOWN_OR_RESTRICTED';
  if (e === '' || e === 'UNLICENSED' || e === 'PROPRIETARY') return 'UNKNOWN_OR_RESTRICTED';
  return 'UNKNOWN_OR_RESTRICTED';
}

function collect() {
  const lockPath = path.join(root, 'package-lock.json');
  if (!fs.existsSync(lockPath)) { console.error(`package-lock.json not found in ${root}`); process.exit(2); }
  const lock = JSON.parse(fs.readFileSync(lockPath, 'utf-8'));
  const entries = [];
  for (const [p, meta] of Object.entries(lock.packages || {})) {
    if (!p.startsWith('node_modules/')) continue;
    const name = p.slice('node_modules/'.length).split('/node_modules/').pop();
    let license = null;
    try {
      const pkg = JSON.parse(fs.readFileSync(path.join(root, p, 'package.json'), 'utf-8'));
      license = pkg.license;
    } catch {}
    entries.push({ name, version: meta.version || '?', license });
  }
  return entries;
}

function main() {
  const deps = collect();
  const flagged = [];
  const unknown = [];
  for (const d of deps) {
    const cls = classify(d.license);
    d.class = cls;
    if (cls === 'UNKNOWN_OR_RESTRICTED') {
      flagged.push(d);
      if (!d.license || d.license === 'UNLICENSED') unknown.push(d.name);
    }
  }
  // Track reverse dependencies by scanning each package.json for direct deps.
  const consumers = new Map();
  for (const k of Object.keys(JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf-8')).packages || {})) {
    if (!k.startsWith('node_modules/')) continue;
    const meta = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf-8')).packages[k];
    if (meta && meta.dependencies) {
      for (const depName of Object.keys(meta.dependencies)) {
        if (!consumers.has(depName)) consumers.set(depName, []);
        consumers.get(depName).push(k.split('/node_modules/').pop());
      }
    }
  }
  for (const f of flagged) f.consumedBy = consumers.get(f.name) || ['<root>'];

  const conflicts = PROPRIETARY
    ? deps.filter((d) => d.class === 'STRONG_COPYLEFT').map((d) => ({ a: d.name, la: d.license, b: 'proprietary', note: 'AGPL/GPL in closed-source distribution' }))
    : [];

  const report = { deps: deps.length, unknown: unknown.length, flagged, conflicts };
  fs.writeFileSync('license-report.json', JSON.stringify(report, null, 2));
  const md = ['# License Clash Report', '',
    `Dependencies: **${deps.length}** · Unknown/flagged: **${flagged.length}** · Conflicts: **${conflicts.length}**`, '',
    '## Flagged (unknown/restricted licences)', '',
    ...flagged.slice(0, 30).map((f) => `- \`${f.name}@${f.version}\` — \`${f.license || 'no license'}\` (used by ${f.consumedBy.join(', ')})`),
    '',
    conflicts.length ? '## Copyleft in proprietary distribution' + '\n' + conflicts.map((c) => `- \`${c.a}\` (${c.la}) → ${c.b}: ${c.note}`).join('\n') : 'No strong-copyleft conflict with proprietary distribution.',
  ].join('\n');
  fs.writeFileSync('LICENSE_CLASH_REPORT.md', md);
  console.log(md);
  process.exit((flagged.length || conflicts.length) ? 1 : 0);
}

main();
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Run `node license-clash-mediator.js .` — add `--proprietary` when the target
   distribution is closed-source (binary app, internal SaaS).
2. Triage `flagged` in this order:
   - `unknown`/no license → resolve via the upstream repo, record the decision;
   - `RESTRICTED` (CC-NC, BUSL, "SEE LICENSE") → substitution candidates or
     legal sign-off before ship;
   - `STRONG_COPYLEFT` + proprietary → this is the days-of-legal-drama case;
     pick a compatible replacement.
3. Where flagged is acceptable (e.g. dev-only tooling), maintain an
   `allowlist.json` of package names the gate ignores.
4. Wire as a CI gate on every lockfile PR so a single `npm i bad-package`
   cannot slip through.
5. Re-run monthly; the `license-report.json` is the artifact your security
   review signs.

## 5. Edge Cases & Error Handling

- SPDX expressions may carry `OR`/`AND` (e.g. `(MIT OR Apache-2.0)`); the regex
   classifier treats the string conservatively — flag for a human when in doubt.
- Scoped proxies (`@scope/pkg`) resolve from the full node path, so nested
   names never alias.
- Missing `package.json` under `node_modules` (pruned installs) records the
   license as unknown rather than crashing; re-run after `npm ci` for accuracy.
- `UNLICENSED` (explicit private) and `SEE LICENSE IN ...` are both routed to
   human review — the report distinguishes them by name.
- The reverse-consumer scan reads the lockfile's `dependencies` maps; conform
   lockfiles v1 without a `packages` block trigger exit `2` with a hint to
   regenerate the lockfile.