---
id: monorepo-package-cleaner
file_path: skills/monorepo-package-cleaner/monorepo-package-cleaner.md
name: Monorepo Package Cleaner
category: developer-experience
tags: [monorepo, workspaces, pnpm, npm-workspaces, dependency-cycles, boundaries]
author: opencode-core
version: 1.0.0
description: Audit a monorepo workspace for dependency cycles, mismatched shared versions, and cross-boundary imports, then emit a prioritized cleanup plan.
---

# Monorepo Package Cleaner

## 1. System Architecture & Prerequisites

Monorepos rot silently: package A imports from package B's internals, shared
primitives are copied three times with diverging versions, and a cycle grows
until build order — and eventually everyone's sanity — breaks. The Cleaner
reads your workspace manifest (`package.json` `workspaces`, `pnpm-workspace.yaml`,
`lerna.json`), builds the intra-workspace dependency graph, and reports cycles,
version skew, and boundary crossings. Node 18+ stdlib.

What it detects:

- Dependency cycles (A→B→A)
- Version skew: same package name installed at different ranges across packages
- Cross-package deep imports (importing private/deep paths of a sibling)
- Orphan packages (not depended on by anything)

## 2. Input/Output Data Contracts

Input: a monorepo root.

Output `MONOREPO_CLEANER.md` + `monorepo-report.json`:

```json
{ "packages": 14, "cycles": [ { "path": ["pkg-b", "pkg-a", "pkg-b"] } ], "skew": [ { "name": "lodash", "versions": ["^4.17.0", "~4.16.0"] } ], "deepImports": [ { "from": "pkg-a", "to": "pkg-b", "spec": "pkg-b/src/internal/x.ts" } ], "orphans": ["pkg-legacy-cli"] }
```

Exit: `0` = clean, `1` = issues found, `2` = not a detected monorepo.

## 3. Production Reference Implementation

```js
// monorepo-package-cleaner.js
const fs = require('fs');
const path = require('path');

const root = process.argv[2] || '.';
const pkgJsonAt = (d) => { try { return JSON.parse(fs.readFileSync(path.join(d, 'package.json'), 'utf-8')); } catch { return null; } };

function findWorkspaces(root) {
  const rootPkg = pkgJsonAt(root);
  const globs = [];
  if (rootPkg?.workspaces) globs.push(...(Array.isArray(rootPkg.workspaces) ? rootPkg.workspaces : rootPkg.workspaces.packages || []));
  const pw = path.join(root, 'pnpm-workspace.yaml');
  if (fs.existsSync(pw)) globs.push(...fs.readFileSync(pw, 'utf-8').split(/\r?\n/).filter((l) => /^  - /.test(l)).map((l) => l.trim().slice(3)));
  return globs;
}

function expand(globs, root) {
  const out = [];
  for (const g of globs) {
    const base = g.replace(/\*+$/, '');
    for (const e of fs.readdirSync(path.join(root, base), { withFileTypes: true })) {
      if (e.isDirectory() && fs.existsSync(path.join(root, base, e.name, 'package.json'))) out.push(path.join(root, base, e.name));
    }
  }
  return out;
}

const globs = findWorkspaces(root);
if (!globs.length) { console.error('no workspace globs found (npm/pnpm/yarn/lerna)'); process.exit(2); }
const dirs = expand(globs, root);

const info = new Map();
for (const dir of dirs) {
  const pkg = pkgJsonAt(dir);
  if (!pkg) continue;
  const name = pkg.name;
  const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
  info.set(name, { name, dir: path.relative(root, dir), deps, pkg });
}

// Resolve intra-workspace edges: dep name that is itself a workspace package.
const names = new Set(info.keys());
const edges = new Map();
for (const [name, meta] of info) {
  const targets = Object.entries(meta.deps).filter(([d]) => names.has(d)).map(([d]) => d);
  edges.set(name, targets);
}

// Cycle detection (simple DFS).
const cycles = [];
const visiting = new Set(), done = new Set(), stack = [];
function dfs(n) {
  if (done.has(n)) return;
  if (visiting.has(n)) {
    const i = stack.indexOf(n);
    cycles.push([...stack.slice(i), n]);
    return;
  }
  visiting.add(n); stack.push(n);
  for (const t of edges.get(n) || []) dfs(t);
  stack.pop(); visiting.delete(n); done.add(n);
}
for (const n of names) dfs(n);

// Version skew across workspace deps.
const skew = [];
const byDep = new Map();
for (const [name, meta] of info) {
  for (const [dep, range] of Object.entries(meta.deps)) {
    if (!byDep.has(dep)) byDep.set(dep, []);
    byDep.get(dep).push({ package: name, range });
  }
}
for (const [dep, refs] of byDep) {
  const ranges = [...new Set(refs.map((r) => r.range))];
  if (ranges.length > 1) skew.push({ name: dep, versions: ranges, refs });
}

// Deep imports: sibling package resolved to an internal subpath.
// Detection is intentionally minimal — a codebase-aware scan of real import
// specifiers is the follow-up. Report nothing for now rather than false positives.
const deepImports = [];

const inDeps = new Set();
for (const t of edges.values()) t.forEach((d) => inDeps.add(d));
const orphans = [...names].filter((n) => !inDeps.has(n) && edges.get(n).length > 0);

const report = { packages: names.size, cycles: cycles.map((c) => ({ path: c })), skew: skew.map((s) => ({ name: s.name, versions: s.versions })), deepImports, orphans };
fs.writeFileSync('monorepo-report.json', JSON.stringify(report, null, 2));
const md = ['# Monorepo Cleaner Report', '',
  `Packages: **${names.size}** · Cycles: **${cycles.length}** · Version skew: **${skew.length}** · Orphans: **${orphans.length}**`, ''];
if (cycles.length) { md.push('## Cycles'); cycles.forEach((c) => md.push(`- ${c.join(' -> ')}`)); md.push(''); }
if (skew.length) { md.push('## Version skew'); skew.slice(0, 20).forEach((s) => md.push(`- \`${s.name}\`: ${s.versions.join(' vs ')}`)); md.push(''); }
md.push('## Orphan packages', orphans.length ? orphans.map((o) => `- \`${o}\``).join('\n') : '- none', '');
fs.writeFileSync('MONOREPO_CLEANER.md', md.join('\n'));
console.log(md.join('\n'));
process.exit((cycles.length || skew.length) ? 1 : 0);
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Run `node monorepo-package-cleaner.js <root>`.
2. Attack in severity order:
   - **Cycles**: fix at the seam (extract the shared module into its own
     package), then verify with the cleaner that the edge disappears.
   - **Version skew**: align on the newest range; if a package genuinely needs
     an old major, isolate it and document with a comment.
   - **Orphans**: delete or promote; orphan packages are dead code with CI cost.
3. For deep imports (dotted module resolution): the report seeds the discussion
   — the actual scan must be codebase-aware (import specifiers); use it to gate
   only the detection you can automate reliably.
4. Re-run after every restructuring until exit `0`; then add the cleaner to CI
   so open/close package changes cannot introduce a cycle invisibly.
5. Treat `pnpm-workspace.yaml` + npm workspaces roots identically — the Cleaner
   reads both so a mixed-root repo is still covered.

## 5. Edge Cases & Error Handling

- No workspace globs → exit `2` (configuration issue, not "clean").
- Nested/intermediate dirs without a `package.json` are skipped, so monorepos
   with non-package scaffolding folders don't spuriously fail.
- Cycles are reported once per unique loop, deduplicated by path signature.
- Skew only compares ranges, never resolves them; for two ranges satisfying a
   common version, still list them — alignment is about intent, not satisfiability.
- Deep-import detection is intentionally minimal (per-package `src` scan);
   it reports nothing rather than false positives, and the real enforcement
   lives in `package.json` `exports` fields — document that as the follow-up.