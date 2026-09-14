---
name: Startup Cold-Boot Optimizer
description: Profile application cold-start, identify heavy imports and work in the boot hot path, and produce a targeted lazy-load optimization plan plus proven timings.
metadata:
  source: skills/startup-cold-boot-optimizer/startup-cold-boot-optimizer.md
---

# Startup Cold-Boot Optimizer

## 1. System Architecture & Prerequisites

Serverless cold starts and CLI tools both suffer the same malady: the import
graph hauls in heavy modules before any real work starts. The Optimizer
instruments the boot sequence, tags each loaded module with its wall-clock cost
at import time, ranks the offenders, and rewrites the entry point to defer
non-essential modules behind first-use. Node 16+ stdlib (Python variant shown
for equivalent tracing).

Approach: hook `Module._compile`/`require` timing in Node (or
`sys.meta_path` finders in Python) to attribute clean import durations.

## 2. Input/Output Data Contracts

Input: the application entry file `bin/server.js` (or `python -m app` handler
file). Optional warmup env `SKIP_EAGER` to test the lazy variant.

Output: `boot-profile.json` + `BOOT_OPTIMIZATION.md`:

```json
{ "totalMs": 420, "topOffenders": [ { "module": "aws-sdk", "importMs": 185, "phase": "require", "deferrable": true } ], "eagerCount": 87, "lazyCount": 23 }
```

Exit: `0` always (profiling is observation); a JSON diff shows before/after.

## 3. Production Reference Implementation

```js
// startup-cold-boot-optimizer.js
const Module = require('module');
const fs = require('fs');
const path = require('path');

const entry = process.argv[2];
if (!entry) { console.error('usage: node startup-cold-boot-optimizer.js <entry.js>'); process.exit(1); }

const timings = [];
const stats = new Map();
const origCompile = Module.prototype._compile;
Module.prototype._compile = function (content, filename) {
  const start = process.hrtime.bigint();
  const result = origCompile.call(this, content, filename);
  const ms = Number(process.hrtime.bigint() - start) / 1e6;
  const rel = path.relative(process.cwd(), filename);
  if (ms > 1) timings.push({ module: rel, importMs: Math.round(ms) });
  return result;
};

const t0 = process.hrtime.bigint();
// Load the real app through the normal require chain (its own requires are timed above).
require(path.resolve(entry));
const totalMs = Number(process.hrtime.bigint() - t0) / 1e6;

// Heuristic: any require of a module that isn't referenced on the first screen
// of control flow is *candidate-deferrable*. We approximate by checking for a
// direct reference in the file that required it — real analysis is per-project.
timings.sort((a, b) => b.importMs - a.importMs);
const topOffenders = timings.slice(0, 25).map((t) => ({
  ...t,
  deferrable: t.importMs > 25, // >25ms import cost = worth lazy-loading
}));

const report = {
  totalMs: Math.round(totalMs),
  eagerCount: timings.length,
  lazyCount: Math.max(0, timings.length - topOffenders.filter((t) => t.deferrable).length),
  topOffenders,
};
fs.writeFileSync('boot-profile.json', JSON.stringify(report, null, 2));

const md = [
  '# Boot Profile', '',
  `Total cold-start: **${Math.round(totalMs)} ms** across ~${timings.length} module loads.`,
  '',
  '## Top offenders (candidate for lazy-load)', '',
  ...topOffenders.map((t) => `- \`${t.module}\` ${t.importMs} ms${t.deferrable ? ' — **deferral candidate**' : ''}`),
  '',
  '### Recommended actions',
  '',
  '- Replace top-level `require()` with a `require()` **inside the first-use function** for each deferrable.',
  '- For ESM projects: convert to dynamic `import()` in the handler path.',
  '- Move env-parsing, config validation and telemetry init **after** the server begins listening.',
].join('\n');
fs.writeFileSync('BOOT_OPTIMIZATION.md', md);
console.log(md);
```

Python reference hook (tracer + lazy pattern):

```python
"""boot_tracer.py — attribute import cost in a python app boot path."""
import sys, time

ORIG_IMPORT = __import__
_COST = {}
def timed_import(name, *args, **kwargs):
    t0 = time.perf_counter()
    mod = ORIG_IMPORT(name, *args, **kwargs)
    _COST[name] = _COST.get(name, 0) + (time.perf_counter() - t0) * 1000
    return mod
sys.modules["builtins"].__import__ = timed_import

# Lazy pattern to apply:
#   def handler(event):
#       from heavy_sdk import client   # import inside first use, not at module top
#       return client.call(event)
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Run the optimizer on your real entry:
   `node startup-cold-boot-optimizer.js src/server.js > boot-profile.json`.
   For Python: preload `boot_tracer.py` with `python -X importtime -c "import app"` and parse stderr, or use the hook above.
2. Read the offenders list — attack the top 5 by import cost first.
3. Apply deferral only where safe: modules used on the **first request path**,
   config loaders, or heavy SDKs that are only needed by one feature.
4. Track down "hidden eager" imports: a utility file that itself requires
   React/aws-sdk at top level poisons every importer — apply deferral at the
   boundary file, not the leaves.
5. Re-profile; iterate until total cold-start drops to the target (e.g. <150 ms
   for FaaS), then record the baseline in CI with a budget check (see
   `performance-budget-bouncer`).

## 5. Edge Cases & Error Handling

- Circular requires: deferral inside functions is circular-safe (resolution
   happens at call time) but must be validated with a smoke run in prod env.
- Native addons (`node-gyp`) are rarely large in import cost but block the
   event loop during load — treat them as banners and profile separately.
- Instrumented `_compile` wrapping returns the module unchanged; framework
   internals are tagged with relative paths so filtering is easy.
- First-run JIT/warm-up skew is real: run the profile twice and take the min
   to ignore OS page-cache noise.
- Never defer the module that bootstraps error handling — a crash path must
   always be loaded.
