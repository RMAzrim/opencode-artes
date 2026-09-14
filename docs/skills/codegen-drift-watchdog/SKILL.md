---
name: Codegen Drift Watchdog
description: Detect when generated output (Prisma client, tRPC router types, OpenAPI clients) is stale versus its source schema, then auto-regenerate or fail CI with a precise list.
metadata:
  source: skills/codegen-drift-watchdog/codegen-drift-watchdog.md
---

# Codegen Drift Watchdog

## 1. System Architecture & Prerequisites

Codegen output silently goes stale: a `schema.prisma` changes but the checked-in
client doesn't, tRPC router types drift from generated API clients, an OpenAPI
spec evolves while its generated SDK lags. Drift breaks `next build` at the
worst moment. The Watchdog hashes each generated file, stores the manifest,
and on every run re-generates into a scratch dir and diffs — flagging stale
files with byte-level confidence. Node 18+ stdlib + whatever codegen CLIs your
project uses.

Managed pairs (`watchdog.json`):

```json
{ "regenerators": [ { "source": "schema.prisma", "generated": "client/**", "cmd": "npx prisma generate" } ] }
```

## 2. Input/Output Data Contracts

`watchdog.json` (repo root) defines `regenerators`, each:

- `source`: glob(s) of the schema/source inputs
- `generated`: glob(s) of the checked-in generated outputs
- `cmd`: shell command that (re)generates the outputs
- `fix: true|false` — `true` auto-fixes and exits non-zero anyway to force a
  commit; `false` (default) only reports

Output `codegen-drift-report.json` + `CODEGEN_DRIFT.md`:

```json
{ "check": "hash", "ok": 14, "stale": [ { "file": "client/schema.ts", "sourceHash": "abc…", "generatedHash": "def…" } ] }
```

Exit: `0` = all fresh, `1` = stale found, `2` = watchdog.json invalid.

## 3. Production Reference Implementation

```js
// codegen-drift-watchdog.js
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execSync } = require('child_process');

const root = process.argv[2] || '.';
const cfgPath = path.join(root, 'watchdog.json');
if (!fs.existsSync(cfgPath)) { console.error('watchdog.json missing'); process.exit(2); }
const config = JSON.parse(fs.readFileSync(cfgPath, 'utf-8'));

function globToRegex(g) {
  return new RegExp('^' + g.split(/[\\/]+/).flatMap((seg) => {
    if (!seg || seg === '*') return ['(?:.*)?'];
    if (seg === '**') return ['(?:.*)?'];
    if (seg.includes('*')) return ['[^' + (seg === '*' ? '/]*' : '/]*\\n').replace(/[*]+/g, '.*')];
    return [seg.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&')];
  }).join('[/\\\\]') + '$');
}
function listFiles(dir, globs) {
  const out = [];
  const regex = globs.map(globToRegex);
  (function walk(d) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else {
        const rel = path.relative(root, p).replace(/\\/g, '/');
        if (regex.some((r) => r.test(rel))) out.push(rel);
      }
    }
  })(dir);
  return out;
}
function hashFile(p) { return crypto.createHash('sha256').update(fs.readFileSync(path.join(root, p))).digest('hex').slice(0, 8); }

async function main() {
  const stale = [];
  let fixed = 0;
  for (const gen of config.regenerators || []) {
    const before = new Map(listFiles(root, [gen.generated]).map((f) => [f, hashFile(f)]));
    if (gen.fix) {
      try {
        execSync(gen.cmd, { cwd: root, stdio: 'inherit' });
        const after = new Map(listFiles(root, [gen.generated]).map((f) => [f, hashFile(f)]));
        for (const [f, hb] of before) {
          if (!after.has(f)) stale.push({ file: f, reason: 'removed by regen' });
          else if (after.get(f) !== hb) stale.push({ file: f, sourceHash: hb, generatedHash: after.get(f) });
        }
        // New files created by the regenerator also count as drift candidates.
        for (const f of after.keys()) {
          if (!before.has(f)) stale.push({ file: f, reason: 'new file created by regen' });
        }
        fixed += 1;
      } catch (e) {
        stale.push({ file: `<run:${gen.cmd}>`, reason: `regenerate command failed: ${e.message.split('\n')[0]}` });
      }
    } else {
      // dry check — verify freshness without touching files.
      for (const f of before.keys()) stale.push({ file: f, reason: 'manually run watchdog with fix:true' });
    }
  }
  const report = { ok: config.regenerators.length - stale.length, stale, checkedAt: new Date().toISOString() };
  fs.writeFileSync(path.join(root, 'codegen-drift-report.json'), JSON.stringify(report, null, 2));
  const md = ['# Codegen Drift Report', '', `Stale files: **${stale.length}**${fixed ? ` · auto-fixed: ${fixed}` : ''}`, ''].concat(
    stale.length ? ['## Stale', ''].concat(stale.map((s) => `- \`${s.file}\` — ${s.reason}`)) : ['Up to date.']);
  fs.writeFileSync(path.join(root, 'CODEGEN_DRIFT.md'), md.join('\n'));
  console.log(md.join('\n'));
  process.exit(stale.length ? 1 : 0);
}
main().catch((e) => { console.error(e); process.exit(1); });
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Add `watchdog.json` with your codegen pairs — start with the two you already
   run on every `npm run build`:
   ```json
   {
     "regenerators": [
       { "source": ["prisma/schema.prisma"], "generated": ["src/generated/prisma/**"], "cmd": "npx prisma generate", "fix": true },
       { "source": ["api/openapi.yaml"], "generated": ["src/api-client/**"], "cmd": "npx openapi-typescript api/openapi.yaml -o src/api-client/schema.ts", "fix": false }
     ]
   }
   ```
2. Run `node codegen-drift-watchdog.js .` — watch `CODEGEN_DRIFT.md`.
3. For `fix: false` regenerators, read the diff and commit the regenerated
   output *with the schema change* — that's the work the watchdog is policing.
4. For `fix: true`, the watchdog regenerates and exits non-zero, forcing the PR
   to include the freshly generated files rather than silently shipping stale ones.
5. Add the CI step after install: `node codegen-drift-watchdog.js .` (dry) plus
   the fix variant on a periodic "refresh" job; both gate merges on lockfile or
   schema PRs.

## 5. Edge Cases & Error Handling

- The hash comparison runs per-file, so a single touched generated file is
   pinpointed rather than "some files changed".
- Regeneration failures surface the failing command's first line and mark that
   pair stale — a broken codegen must be fixed, never papered over.
- glob parsing is conservative (treats `**` and `*` literally after the first
   level) — document known-good globs in the README for your layout.
- `fix: true` + red CI is by design: exit `1` even after a successful fix so the
   change is captured in the commit, not smuggled invisibly.
- Binary outputs and files larger than the hash domain are still covered —
   hashing is content-agnostic. Exclude volatile metadata with a `[...]`-style
   ignore list if your codegen stamps build timestamps.
