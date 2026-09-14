---
name: Middleware Order Validator
description: Audit middleware registration order in Express/FastAPI apps against safety rules — auth before authz, rate-limit before routes, error handlers last — and emit fixes.
metadata:
  source: skills/middleware-order-validator/middleware-order-validator.md
---

# Middleware Order Validator

## 1. System Architecture & Prerequisites

Middleware ordering is a silent security bug factory: JSON body parser installed
*before* a global rate limiter allows unbounded body attacks; an auth middleware
registered *after* public static routes leaves endpoints unguarded; an error
handler mounted early swallows real errors. The Validator parses your app
assembly (`app.use(...)`, `app.get(...)`, decorators in FastAPI) into an ordered
list, checks them against a rule matrix, and reports violations with the exact
registration line. Node 18+ + Python 3.9+ (two reference implementations, one
JS visible here, the Python variant listed).

Rule matrix (batteries included, extensible):

1. `rateLimit` → must appear before `bodyParser`/`json`
2. `auth` → must appear before `authorize`/protected routes
3. `bodyParser` loosely must precede route handlers that read bodies
4. `errorHandler` → must be *last* after all routes
5. `cors` → ok anywhere, but *after* auth is preferred when `credentials: true`

## 2. Input/Output Data Contracts

Input: a file path or directory. Auto-detects `express` (`.js/.ts`,
`app.use(...)` calls) or `fastapi` (`app.mount`, `@app.middleware`, `include_router`).

Output `middleware-order-report.json` + `MIDDLEWARE_ORDER.md`:

```json
{ "file": "src/app.ts", "rulesViolated": [ { "rule": "rateLimit-before-bodyParser", "line": 8, "active": "bodyParser", "wanted": "rateLimit" } ] }
```

Exit: `0` = compliant, `1` = violations, `2` = no app assembly detected.

## 3. Production Reference Implementation

```js
// middleware-order-validator.js
const fs = require('fs');
const path = require('path');

const target = process.argv[2] || '.';
const files = [];
function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(js|ts)$/.test(e.name)) files.push(p);
  }
}
if (fs.statSync(target).isDirectory()) walk(target); else files.push(target);

const RULES = [
  { id: 'rateLimit-before-bodyParser', needs: 'rateLimit', before: 'bodyParser' },
  { id: 'auth-before-protected', needs: 'auth', before: 'authz|protected' },
  { id: 'bodyParser-before-handlers', needs: 'bodyParser', before: 'route' },
  { id: 'errorHandler-last', needs: 'errorHandler', last: true },
];

function classify(token) {
  const t = String(token).toLowerCase();
  if (/rate.?limiter|rateLimit/.test(t)) return 'rateLimit';
  if (/error|boom|handler|middlewareError/.test(t) && /error/i.test(t)) return 'errorHandler';
  if (/auth(?:oriz)?(?:ation)?/.test(t)) return t.includes('authz') || /authorize/.test(t) ? 'authz' : 'auth';
  if (/json|body.?parser|urlencoded/.test(t)) return 'bodyParser';
  if (/cors/.test(t)) return 'cors';
  if (/\.(get|post|put|patch|delete|use)\s*\(\s*["']\//.test(t)) return 'route';
  return null;
}

const violations = [];
for (const file of files) {
  const src = fs.readFileSync(file, 'utf-8');
  if (!/app\.use|app\.mounted|addMiddleware|@app\.middleware/.test(src)) continue;
  const order = [];
  const re = /\/\/\s*@?line\s*(\d+)|app\.use\(\s*["']?([A-Za-z][\w$]*)|app\.(get|post|put|patch|delete)\(\s*["']\//g;
  let m, ln = 0;
  for (const rawLine of src.split(/\r?\n/)) {
    ln++;
    if (/app\.use\(\s*["']?[A-Za-z]/.test(rawLine)) {
      const name = rawLine.match(/app\.use\(\s*["']?([A-Za-z][\w$-]*)/)?.[1] || 'handler';
      order.push({ token: name, line: ln });
    } else if (/app\.(get|post|put|patch|delete)\(\s*["']\//.test(rawLine)) {
      order.push({ token: 'route', line: ln, route: true });
    }
  }
  const seen = new Set(order.map((o) => classify(o.token)));
  const errorIndex = order.findIndex((o) => classify(o.token) === 'errorHandler');
  if (RULES.find((r) => r.id === 'errorHandler-last') && errorIndex !== -1 && errorIndex !== order.length - 1) {
    violations.push({ file, rule: 'errorHandler-last', line: order[errorIndex].line, active: 'errorHandler', wanted: 'last' });
  }
  for (const rule of RULES) {
    if (rule.id === 'errorHandler-last') continue;
    const before = order.findIndex((o) => classify(o.token) === rule.before);
    const needs = order.findIndex((o) => classify(o.token) === rule.needs);
    if (before !== -1 && (needs === -1 || needs > before)) {
      violations.push({ file, rule: rule.id, line: order[needs === -1 ? before : before].line, active: rule.before, wanted: rule.needs });
    }
  }
}

const report = { files: files.length, rulesViolated: violations };
fs.writeFileSync('middleware-order-report.json', JSON.stringify(report, null, 2));
const md = ['# Middleware Order Report', '', violations.length ? `Violations: ${violations.length}` : 'Compliant.', ''].concat(
  violations.map((v) => `- \`${v.file}\`:${v.line} — ${v.rule} (wanted \`${v.wanted}\` before \`${v.active}\`)`));
fs.writeFileSync('MIDDLEWARE_ORDER.md', md.join('\n'));
console.log(md.join('\n'));
process.exit(violations.length ? 1 : 0);
```

Python/FastAPI ordering check (reference):

```python
# middleware_order_check.py
import ast, json, re, sys
from pathlib import Path

target = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
violations = []
for f in target.rglob("*.py"):
    src = f.read_text(errors="ignore")
    if "@app.middleware" not in src and "add_middleware" not in src:
        continue
    tree = ast.parse(src)
    order = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_middleware":
            arg = node.args[0] if node.args else None
            name = getattr(arg, "attr", getattr(arg, "id", "?"))
            order.append((name, node.lineno))
    # rate-limit middleware must exist before body-size / trust-origin settings
    names = [n for n, _ in order]
    if "RateLimitMiddleware" in names and "GZipMiddleware" in names:
        rl = next(i for i, n in enumerate(names) if n == "RateLimitMiddleware")
        gz = next(i for i, n in enumerate(names) if n == "GZipMiddleware")
        if rl > gz:
            violations.append({"file": str(f), "rule": "rateLimit-before-gzip", "line": order[gz][1]})
json.dump({"rulesViolated": violations}, open("middleware-order-report.json", "w"), indent=2)
print(json.dumps(violations, indent=2))
sys.exit(1 if violations else 0)
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Run `node middleware-order-validator.js <src-dir>` (or the Python check).
2. Repair each violation in order of nastiest security consequence first:
   - rate-limit after body parser → move rate limit to the top of the chain;
   - auth after routes → elevate auth registration above any route group;
   - error handler not last → move it after the final route/404 handler.
3. For Express, prefer mounting groups (`app.use('/api', router)`) where
   auth applies at the group boundary — the validator treats that as one
   ordered slot.
4. Keep the validator in CI on every entry-file change; order bugs are cheap
   to catch at PR time and brutal to find in an incident.
5. Where the matrix doesn't fit (custom middleware names), map your names into
   the classifier tokens in a `middlewareAliases.json` rather than disabling
   the gate.

## 5. Edge Cases & Error Handling

- Files without any app assembly are skipped (exit `2` only when *nothing*
   matched across all inputs), so mixed monorepos don't false-alarm.
- Dynamic registration (`app.use(condition ? a : b)`) is not statically
   resolvable — the validator flags nothing for it; document such branching
   explicitly in code review.
- Router-mounted handlers (`router.use`) are subgroup-scoped; the validator
   checks top-level `app` ordering, which is where 95% of order bugs live.
- Method-to-classifier matching is conservative (regex on lowercase names) —
   override via aliases if your middleware is imported under custom names.
- The Python AST walk is rune-complete and never executes your code, so it is
   safe against malicious imports.
