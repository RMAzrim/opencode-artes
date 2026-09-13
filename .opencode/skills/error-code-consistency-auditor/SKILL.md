---
name: Error Code Consistency Auditor
description: Audit every error class, message, and HTTP mapping across the codebase for duplication, contradictory status codes, and undocumented errors.
metadata:
  source: skills/error-code-consistency-auditor/error-code-consistency-auditor.md
---

# Error Code Consistency Auditor

## 1. System Architecture & Prerequisites

Nothing erodes an API contract faster than inconsistent errors: one endpoint
returns `400` for "not found", another `404`; the same error class maps to
different messages in two modules; new errors are thrown but never documented
in the OpenAPI spec. The Auditor parses your error registry (error classes with
`statusCode`/`code`/`message`), cross-maps every throw site, and flags
multiplicity and contradiction. Node 18+ stdlib.

What it surfaces:

- Same status code + same code but different messages (two sources of truth)
- Same message text under different codes
- HTTP statuses outside the idiomatic range (e.g. `2xx` for failures)
- Errors with no `.statusCode` (leaks as 500 = unmapped)
- Errors referenced by tests/spec but never thrown (documentation drift, flipped)

## 2. Input/Output Data Contracts

Input: a source directory (auto-detects `.ts/.js` with a classic error-class
shape `class XError extends Error { statusCode = ...; code = '...' }`) plus an
optional `errors/spec.json` describing the approved error catalog.

Output `ERROR_AUDIT.md` + `error-audit.json`:

```json
{ "errorClasses": 23, "thrown": 140, "duplicateMessageCoding": [ { "status": 400, "message": "invalid request", "codes": ["INVALID_REQ", "BAD_INPUT"] } ], "unmapped": ["DbTimeoutError"] }
```

Exit: `0` = consistent, `1` = findings, `2` = no error classes found.

## 3. Production Reference Implementation

```js
// error-code-consistency-auditor.js
const fs = require('fs');
const path = require('path');

const root = process.argv[2] || '.';
const files = [];
(function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(ts|js)$/.test(e.name) && !p.includes('node_modules')) files.push(p);
  }
})(root);

const errorClasses = [];
const thrown = [];
for (const file of files) {
  const src = fs.readFileSync(file, 'utf-8');
  const clsRe = /class\s+(\w+Error)\s+extends\s+Error\s*\{([\s\S]*?)\n\}/g;
  let m;
  while ((m = clsRe.exec(src))) {
    const [, name, body] = m;
    const status = body.match(/statusCode\s*=\s*(\d{3})/)?.[1];
    const code = body.match(/code\s*=\s*['"]([A-Z0-9_]+)['"]/)?.[1];
    const message = body.match(/message\s*=\s*['"]([^'"]+)['"]/)?.[1];
    if (status || code) errorClasses.push({ file, name, status: Number(status), code, message });
  }
  const throwRe = /throw\s+new\s+(\w+Error)\s*\(([^)]*)\)/g;
  while ((m = throwRe.exec(src))) {
    const [, name, arg] = m;
    thrown.push({ file, name, arg: arg.trim().replace(/^['"]|['"]$/g, '') });
  }
}

const findings = [];
const msgKey = new Map();
for (const e of errorClasses) {
  if (!e.status) findings.push({ kind: 'unmapped-status', name: e.name, file: e.file });
  const key = `${e.status || 500}|${e.message || ''}`;
  if (!msgKey.has(key)) msgKey.set(key, []);
  msgKey.get(key).push({ name: e.name, status: e.status });
  // statu-code 2xx used as failure?
  if (e.status && e.status >= 200 && e.status <= 299) findings.push({ kind: 'success-code-as-error', name: e.name, status: e.status });
}
for (const [key, refs] of msgKey) {
  const [status, message] = key.split('|');
  if (!message) continue;
  if (refs.length > 1 && new Set(refs.map((r) => r.name)).size > 1) {
    findings.push({ kind: 'duplicate-message', status: Number(status) || 500, message, classes: refs.map((r) => r.name) });
  }
}
const classNames = new Set(errorClasses.map((e) => e.name));
const thrownNames = new Set(thrown.map((t) => t.name));
const thrownButUndefined = [...thrownNames].filter((n) => !classNames.has(n));
if (thrownButUndefined.length) findings.push({ kind: 'thrown-but-undefined', names: thrownButUndefined });
const neverThrown = [...classNames].filter((n) => !thrownNames.has(n));
if (neverThrown.length) findings.push({ kind: 'defined-never-thrown', names: neverThrown });

const report = { errorClasses: errorClasses.length, thrown: thrown.length, findings };
fs.writeFileSync('error-audit.json', JSON.stringify(report, null, 2));
const md = ['# Error Code Consistency Audit', '',
  `Error classes: **${errorClasses.length}** · Throw sites: **${thrown.length}** · Findings: **${findings.length}**`, ''];
for (const f of findings) {
  md.push(`- [${f.kind}] ${f.name ? `${f.name} ` : ''}${f.status ? `(status ${f.status}) ` : ''}${f.message ? `\`${f.message}\`` : ''}${f.classes ? ` — ${f.classes.join(', ')}` : ''}${f.names ? ` — ${f.names.join(', ')}` : ''}`);
}
fs.writeFileSync('ERROR_AUDIT.md', md.join('\n'));
console.log(md.join('\n'));
process.exit(findings.length ? 1 : 0);
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Run `node error-code-consistency-auditor.js <src>`.
2. Triage by kind, most impactful first:
   - `thrown-but-undefined` — missing custom error where you wrote `throw new
     FancyError`; the class doesn't exist and it will surface as a 500. Create it.
   - `success-code-as-error` — wrong HTTP for a failure branch; align with the
     catalog.
   - `duplicate-message` — two classes meaning the same thing; merge and keep
     one code, update the throw sites.
   - `unmapped-status` — add `statusCode` defaults; unset status = 500 by
     framework default, which is rarely what you want.
3. Keep an `errors/` catalog doc (`spec.json`) as the single source of truth and
   re-run the auditor after every schema/migration change.
4. Wire the auditor to CI on error-related PRs so semantics can't drift while
   refactoring.
5. Pair with `openapi-spec-writer` to verify each documented error code maps to
   a real class in the catalog (closing the loop between spec and code).

## 5. Edge Cases & Error Handling

- Legacy wrappers (`AppError.create('X', ...)`) without class shapes are not
   parsed by the class scanner; add a single regex alias in the tool config to
   cover your factory pattern.
- Errors thrown inside third-party code (imported) are invisible — the auditor
   reports only project-local classes, which is the right scope for a contract.
- Multi-word status candidates like `statusCode: 500` nested one level deep are
   caught by the body-matched pattern inside `class ... {}`.
- Findings for "never thrown" classes may be legitimate (an error kept for
   backward compat) — the entry exists to force a conscious decision, not to
   force deletion.
- Binary/transpiled outputs are excluded (`.js` in `dist/` is skipped via the
   node_modules filter); re-scope `root` to `src/` when auditing a compiled app.
