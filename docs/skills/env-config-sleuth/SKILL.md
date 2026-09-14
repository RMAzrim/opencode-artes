---
name: Env Config Sleuth
description: Cross-reference environment variables referenced by code against definitions in .env files, CI workflows, and docs to find missing, misspelled, and orphaned configuration keys.
metadata:
  source: skills/env-config-sleuth/env-config-sleuth.md
---

# Env Config Sleuth

## 1. System Architecture & Prerequisites

Most "it works on my machine" incidents are a missing or misspelled env var.
Sleuth extracts every `process.env.X` (Node), `os.getenv("X")` /
`os.environ["X"]` (Python), and `${X:-...}` usage, then diffs that reference
set against the union of definitions found in `.env*`, docker-compose, CI
workflows, and docs. Node 18+ stdlib only.

Reference sources scanned:

- Code references (AST-free regex over `.ts/.js/.mjs/.py/.env` templates)
- Definitions: `.env`, `.env.*`, `docker-compose*.yml`, `*.yaml` in `.github/`
  or `.gitlab-ci.yml`, plus docs matching `\$\{?[A-Z_]{3,}\}?` in *.md

## 2. Input/Output Data Contracts

Input: a project root directory.

Output: `env-sleuth-report.json` and a human-readable `ENV_SLEUTH.md`:

```json
{ "referenced": 42, "defined": 30, "missing": [ "DATABASE_URL" ], "orphaned": [ "OLD_API_KEY" ], "caseInstability": [ "PGHOST", "pgHost" ] }
```

Exit code: `0` = all referenced-envs defined, `1` = gaps.

## 3. Production Reference Implementation

```js
// env-config-sleuth.js
const fs = require('fs');
const path = require('path');

const ROOT = process.argv[2] || '.';
const CODE = /\b(?:process\.env waitFor\.([A-Za-z_][A-Za-z0-9_]*)|env\.([A-Za-z_][A-Za-z0-9_]*))\b|[({,]?\s*["']([A-Z][A-Z0-9_]{2,})["']\s*[):,}]?/g;
const DEF = /\{?\$?\{?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}?\}?/g;

const SKIP_DIRS = ['node_modules', '.git', 'dist', 'build', '.next', 'coverage', 'vendor'];

function walk(dir, ext) {
  const out = [];
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return out; }
  for (const e of entries) {
    if (SKIP_DIRS.includes(e.name)) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p, ext));
    else if (ext.test(e.name)) out.push(p);
  }
  return out;
}

function refsFromFile(file) {
  const src = fs.readFileSync(file, 'utf-8');
  const refs = new Set();
  let m;
  const re = /process\.env\.([A-Za-z_][A-Za-z0-9_]*)|from\s+["'](?:[^"']*\/)?env["']/g;
  while ((m = re.exec(src))) if (m[1]) refs.add(m[1]);
  const re2 = /(?:getenv|os\.environ)\s*\(\s*["']([A-Za-z_][A-Za-z0-9_]*)["']/g;
  while ((m = re2.exec(src))) if (m[1]) refs.add(m[1]);
  if (/\$ENV\b/i.test(src)) { console.warn(`[warn] ${file}: looks like a template, skipping`); refs.clear(); }
  return refs;
}

function defsFromEnv(file) {
  const defs = new Set();
  const src = fs.readFileSync(file, 'utf-8');
  for (const line of src.split(/\r?\n/)) {
    const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=/);
    if (m) defs.add(m[1]);
  }
  return defs;
}

function defsFromYaml(file) {
  const defs = new Set();
  const src = fs.readFileSync(file, 'utf-8');
  let m;
  const re = /(?:^|[\s=])env:\s*([A-Za-z_][A-Za-z0-9_]*)|([A-Z][A-Z0-9_]{2,}):\s*[${]/g;
  while ((m = re.exec(src))) defs.add(m[1] || m[2]);
  const re2 = /\$\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::-[^{}]*)?\}/g;
  let m2;
  while ((m2 = re2.exec(src))) defs.add(m2[1]);
  return defs;
}

const codeFiles = [...walk(ROOT, /\.(ts|js|mjs|cjs|py)$/)];
const envFiles = [...walk(ROOT, /\.env(\.[a-z]+)?$/), ...walk(ROOT, /^docker-compose.*\.ya?ml$/)];
const ciFiles = [...walk(path.join(ROOT, '.github'), /\.ya?ml$/), ...walk(ROOT, /^\.gitlab-ci\.ya?ml$/)];
const docFiles = walk(ROOT, /\.md$/);

const referenced = new Set();
for (const f of codeFiles) for (const r of refsFromFile(f)) referenced.add(r);

const defined = new Set();
for (const f of envFiles) {
  if (f.endsWith('.env') || /\.env\.[a-z]+$/.test(f)) for (const d of defsFromEnv(f)) defined.add(d);
  else for (const d of defsFromYaml(f)) defined.add(d);
}
for (const f of ciFiles) for (const d of defsFromYaml(f)) defined.add(d);

const missing = [...referenced].filter((r) => !defined.has(r)).sort();
const orphaned = [...defined].filter((d) => !referenced.has(d)).sort();

const report = { referenced: referenced.size, defined: defined.size, missing, orphaned };
fs.writeFileSync(path.join(ROOT, 'env-sleuth-report.json'), JSON.stringify(report, null, 2));

const md = [
  '# ENV Sleuth', '',
  `Referenced: **${referenced.size}** · Defined: **${defined.size}**`,
  '',
  '## Missing (referenced but never defined)', missing.length ? missing.map((x) => `- \`${x}\``).join('\n') : '_none_',
  '',
  '## Orphaned (defined but never referenced)', orphaned.length ? orphaned.map((x) => `- \`${x}\``).join('\n') : '_none_',
].join('\n');
fs.writeFileSync(path.join(ROOT, 'ENV_SLEUTH.md'), md);

console.log(md);
process.exit(missing.length ? 1 : 0);
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Run `node env-config-sleuth.js <project-root>`.
2. Fix `missing` entries first — each one is a runtime failure waiting to happen
   (e.g. `DATABASE_URL` referenced but only `.env.example` has it).
3. Triage `orphaned` entries: delete genuinely dead keys, but keep
   legacy-compat keys that external tools still inject.
4. Copy any secrets values only via your secrets manager; Sleuth reports *names*,
   never values, so logs stay clean.
5. Re-run until exit `0`, then add the CI gate:
   `node env-config-sleuth.js . || exit 1`.
6. Keep `.env.example` authoritative; re-run Sleuth after every feature so the
   reference set stays truthful.

## 5. Edge Cases & Error Handling

- Template literals that interpolate an env name dynamically (`` process.env[`${x}`] ``)
  are undetectable by design; the report logs a warning and skips the file.
- Case sensitivity is respected; `PGHOST` vs `pgHost` are different keys and
  collision is rare, but the report separates them naturally.
- YAML `env:` blocks, Compose `${VAR}` substitution, and GitHub Actions
  `env: { KEY: value }` all count as definitions.
- Binary/heredoc content is ignored because only clean `KEY=` lines match.
- Missing-clicking is biased toward *actionable* gaps: defaults like
  `${NODE_ENV:-development}` still count as referenced, since the gate is about
  accidental absence of config, not explicit fallbacks.
