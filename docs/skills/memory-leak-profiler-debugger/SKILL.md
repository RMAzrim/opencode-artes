---
name: Memory Leak Profiler & Debugger
description: Instruments a target callable under tracemalloc and the cyclic garbage collector, takes paired allocation snapshots across repeated runs, flags allocations whose cumulative bytes keep growing across iterations with a repeating traceback as leak signatures, counts live objects per type, verifies weak-reference lifetimes, and reports circular-reference clusters via gc.get_referrers, emitting a structured JSON LeakReport of LeakCandidate entries and documented Node.js v8 heap-snapshot equivalents.
metadata:
  source: skills/memory-leak-profiler-debugger/memory-leak-profiler-debugger.md
---

# Memory Leak Profiler & Debugger

## 1. System Architecture & Prerequisites

- Runtime binary: **Python 3.9 or newer** (relies on `tracemalloc.Statistic.traceback`, `gc.get_objects`, `weakref`, and `inspect`). Python 3.11+ is recommended.
- Standard library only: `tracemalloc`, `gc`, `weakref`, `inspect`, `importlib`, `atexit`, `argparse`, `json`, `sys`, `pathlib`, `dataclasses`, `typing`.
- For Node.js/V8 targets the same skill documents the equivalent invocation `node --heapsnapshot-near-heap-limit=5 --heap-prof app.js` (see Section 4); the Python module itself is interpreter-native.
- The target under test must be a zero-argument callable `module:func` that performs one unit of work (handler, request cycle, worker tick). Long-lived process frames are preferred over CLI programs that exit, because the leak signature this skill detects requires repeated calls in one Python process.

## 2. Input/Output Data Contracts

### 2.1 CLI input options (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "leak_profiler_cli_options",
  "type": "object",
  "properties": {
    "target":      { "type": "string", "description": "Zero-arg callable as 'module:func' or 'module.attr'." },
    "iterations":  { "type": "integer", "default": 6, "minimum": 2, "description": "Number of paired snapshot iterations." },
    "min-growth":  { "type": "integer", "default": 1048576, "description": "Bytes of cumulative growth required to classify a leak signature." },
    "key":         { "type": "string", "enum": ["lineno", "filename", "traceback"], "default": "lineno" },
    "out":         { "type": "string", "description": "Write the JSON report here." },
    "node":        { "type": "boolean", "default": false, "description": "Print V8 heap-snapshot guidance and exit." }
  }
}
```

### 2.2 Output artifacts

- **JSON report** (stdout and optional `--out <path>`):

```json
{
  "target": "leaky_demo",
  "iterations": 6,
  "min_growth_threshold_bytes": 1048576,
  "candidates": [
    {
      "type": "allocation",
      "size": 6291456,
      "growth": 5242880,
      "iterations": 6,
      "traceback": "leak_profiler.py:px <- leak_demo:py <- run:0"
    }
  ],
  "live_type_deltas": { "builtins.bytearray": 96 },
  "collections_fired": 12,
  "survived_weakrefs": [],
  "circular_clusters": [],
  "peak_traced_bytes": 8388608
}
```

- The instrumented target is never written to; only the report bytes and `tracemalloc`'s in-process tracing state are produced.

## 3. Production Reference Implementation

```python
"""Memory Leak Profiler & Debugger.

Instruments a target callable under ``tracemalloc`` and the cyclic garbage
collector, then classifies sustained per-traceback allocation growth as
leak signatures.

Pipeline:
1. ``take_snapshot()`` returns a ``tracemalloc.Snapshot`` (starting tracing
   on first use).
2. ``top_allocations()`` / ``compare()`` summarize snapshots and deltas.
3. ``Detector.run(target, iterations)``:
   a. runs the target inside ``tracemalloc.start()`` and keeps paired
      Nth snapshots (before/after each iteration),
   b. accumulates per-traceback cumulative bytes across iterations and
      flags signatures whose cumulative size keeps growing and whose
      traceback repeats (leak signature),
   c. uses ``gc.get_objects()`` to count live objects per type and tracks
      ``weakref.ref`` objects that should have died but did not,
   d. reports circular-reference clusters via ``gc.get_referrers``.
4. A ``LeakReport`` (list of ``LeakCandidate{type, size, iterations,
   traceback_fp}``) is emitted as JSON.

No third-party dependencies.  For Node.js/V8 the equivalent command is
documented in the node instructions section (``--heapsnapshot-near-heap-limit``).
"""

from __future__ import annotations

import argparse
import atexit
import gc
import importlib
import inspect
import json
import sys
import tracemalloc
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


def take_snapshot() -> tracemalloc.Snapshot:
    if not tracemalloc.is_tracing():
        tracemalloc.start(25)
    return tracemalloc.take_snapshot()


def top_allocations(snapshot: tracemalloc.Snapshot, n: int = 10,
                    key: str = "lineno") -> List[tracemalloc.Statistic]:
    if key not in ("lineno", "filename", "traceback"):
        raise ValueError(f"key must be one of lineno/filename/traceback, got {key!r}")
    stats = snapshot.statistics(key)
    stats.sort(key=lambda s: s.size, reverse=True)
    return stats[:n]


def compare(snap1: tracemalloc.Snapshot, snap2: tracemalloc.Snapshot,
            n: int = 10, key: str = "lineno") -> List[tracemalloc.StatisticDiff]:
    if key not in ("lineno", "filename", "traceback"):
        raise ValueError(f"key must be one of lineno/filename/traceback, got {key!r}")
    diffs = snap2.compare_to(snap1, key)
    diffs.sort(key=lambda d: d.size_diff, reverse=True)
    out = [d for d in diffs[:n] if d.size_diff > 0]
    return out or [d for d in diffs if d.size_diff > 0][:1]


def _frames_of(stat) -> List[Tuple[str, int, str]]:
    """Best-effort (filename, lineno, name) frames for a statistic object."""
    tb = getattr(stat, "traceback", None)
    if tb is None:
        return []
    frames: List[Tuple[str, int, str]] = []
    try:
        for frame in iter(tb):
            if hasattr(frame, "filename"):
                frames.append((frame.filename, frame.lineno, getattr(frame, "name", "")))
            else:
                frames.append((frame[0], frame[1], frame[2] if len(frame) > 2 else ""))
            if len(frames) >= 8:
                break
    except (TypeError, IndexError, AttributeError):
        try:
            formatted = tb.format()
            frames = [(ln, 0, "") for ln in formatted[:8]]
        except Exception:
            frames = [(repr(stat), 0, "")]
    return frames


def _fingerprint(stat) -> Tuple[Tuple[str, int], ...]:
    fr = _frames_of(stat)
    if not fr:
        return (("<unknown>", 0),)
    return tuple((f[0], f[1]) for f in fr[:4])


def live_object_counts() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for obj in gc.get_objects():
        t = type(obj)
        key = f"{t.__module__}.{t.__qualname__}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _is_leaky(vec: List[int], iterations: int, min_growth: int, min_iterations: int) -> bool:
    if len(vec) < max(2, min_iterations):
        return False
    if vec[-1] - vec[0] < min_growth:
        return False
    growths = sum(1 for a, b in zip(vec, vec[1:]) if b > a)
    return growths >= max(2, len(vec) - 1)


def _candidate_from(fp, vec: List[int]) -> "LeakCandidate":
    tail = " <- ".join(f"{f[0]}:{f[1]}" for f in fp)
    return LeakCandidate(
        type="allocation",
        size=vec[-1],
        growth=vec[-1] - vec[0],
        iterations=len(vec),
        traceback_fp=tail,
    )


def find_circular_clusters(root: Any, max_depth: int = 8, limit: int = 250) -> List[str]:
    """Find reference cycles that keep ``root`` alive; render type chains."""
    clusters: List[str] = []
    visited = 0

    def keep(referrer: Any) -> bool:
        return not (
            inspect.isframe(referrer) or inspect.iscode(referrer)
            or isinstance(referrer, (type, ModuleType))
        )

    def walk(obj: Any, path: List[Any]) -> None:
        nonlocal visited
        if len(clusters) >= 5 or visited >= limit or len(path) >= max_depth:
            return
        for referrer in gc.get_referrers(obj):
            visited += 1
            if referrer is root:
                chain = [type(o).__name__ for o in path] + [type(obj).__name__, type(root).__name__]
                clusters.append(" -> ".join(chain))
                return
            if not keep(referrer):
                continue
            if any(ref is referrer for ref in path):
                continue
            walk(referrer, path + [obj])

    walk(root, [])
    return list(dict.fromkeys(clusters))[:5]


@dataclass
class LeakCandidate:
    type: str = "allocation"
    size: int = 0
    growth: int = 0
    iterations: int = 1
    traceback_fp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "size": self.size,
            "growth": self.growth,
            "iterations": self.iterations,
            "traceback": self.traceback_fp,
        }


@dataclass
class LeakReport:
    target: str = ""
    iterations: int = 0
    min_growth: int = 0
    candidates: List[LeakCandidate] = field(default_factory=list)
    live_type_deltas: Dict[str, int] = field(default_factory=dict)
    collections_fired: int = 0
    survived_weakrefs: List[Dict[str, Any]] = field(default_factory=list)
    circular_clusters: List[str] = field(default_factory=list)
    peak_traced_bytes: int = 0

    def to_json(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "iterations": self.iterations,
            "min_growth_threshold_bytes": self.min_growth,
            "candidates": [c.to_dict() for c in self.candidates],
            "live_type_deltas": self.live_type_deltas,
            "collections_fired": self.collections_fired,
            "survived_weakrefs": self.survived_weakrefs,
            "circular_clusters": self.circular_clusters,
            "peak_traced_bytes": self.peak_traced_bytes,
        }


class Detector:
    """Iterative tracemalloc + GC leak detection around one callable."""

    def __init__(self, min_growth: int = 1 << 20,
                 key: str = "lineno",
                 min_iterations: int = 3):
        self.min_growth = int(min_growth)
        self.key = key
        self.min_iterations = min_iterations
        self.report = LeakReport(min_growth=self.min_growth)
        self._tracked: List[Tuple[weakref.ReferenceType, str]] = []

    def track_lifetime(self, obj: Any, name: str) -> weakref.ReferenceType:
        """Register an object that SHOULD be garbage when target() returns."""
        ref = weakref.ref(obj)
        self._tracked.append((ref, name))
        return ref

    def run(self, target: Callable[[], Any], iterations: int = 6) -> LeakReport:
        report = self.report
        report.target = getattr(target, "__qualname__",
                                getattr(target, "__name__", repr(target)))
        report.iterations = iterations

        gc.collect()
        tracemalloc.start(25)
        atexit.register(tracemalloc.stop)
        before_types = live_object_counts()

        running: Dict[Tuple[Tuple[str, int], ...], int] = {}
        series: Dict[Tuple[Tuple[str, int], ...], List[int]] = {}
        collections = 0
        for _ in range(iterations):
            collections += gc.collect()
            before = take_snapshot()
            target()
            collections += gc.collect()
            after = take_snapshot()
            for d in compare(before, after, n=4096, key=self.key):
                fp = _fingerprint(d)
                running[fp] = running.get(fp, 0) + d.size_diff
                series.setdefault(fp, []).append(running[fp])

        for fp, vec in series.items():
            if _is_leaky(vec, iterations, self.min_growth, self.min_iterations):
                report.candidates.append(_candidate_from(fp, vec))
        report.candidates.sort(key=lambda c: c.growth, reverse=True)

        after_types = live_object_counts()
        delta = {t: after_types.get(t, 0) - before_types.get(t, 0)
                 for t in set(after_types) | set(before_types)}
        top = sorted((t for t in delta.items() if t[1] > 0),
                     key=lambda kv: kv[1], reverse=True)[:10]
        report.live_type_deltas = dict(top)

        for ref, name in self._tracked:
            obj = ref()
            if obj is not None:
                clusters = find_circular_clusters(obj, max_depth=8)
                report.survived_weakrefs.append({
                    "name": name,
                    "surviving_type": f"{type(obj).__module__}.{type(obj).__qualname__}",
                    "candidate_clusters": clusters,
                })
                report.circular_clusters.extend(clusters)

        report.collections_fired = collections
        report.peak_traced_bytes = tracemalloc.get_traced_memory()[0]
        return report


# --------------------------------------------------------------------------
# demo targets
# --------------------------------------------------------------------------
_demo_holder: List[bytearray] = []


def leaky_demo() -> None:
    """Documented demo: appends 64 KiB blocks every call, unbounded growth."""
    for _ in range(16):
        _demo_holder.append(bytearray(1 << 16))


def make_closure_leak() -> Callable[[], None]:
    """Returns a callable that accumulates captured dicts (real-world shape)."""
    captured: List[Dict[str, Any]] = []

    def bump() -> None:
        captured.append({"big": bytearray(1 << 20)})

    return bump


# --------------------------------------------------------------------------
# resolution & CLI
# --------------------------------------------------------------------------
def resolve_target(spec: str) -> Callable[[], Any]:
    spec = spec.strip()
    if ":" in spec:
        module_name, _, attr = spec.partition(":")
    elif "." in spec:
        module_name, _, attr = spec.rpartition(".")
    else:
        raise ValueError("target must look like 'module:func' or 'module.attr'")
    if not module_name or not attr:
        raise ValueError("target must look like 'module:func' or 'module.attr'")
    module = importlib.import_module(module_name)
    target = getattr(module, attr)
    if not callable(target):
        raise TypeError(f"{spec} resolved to {type(target).__name__}, not callable")
    return target


NODE_GUIDANCE = """\
V8 / Node.js heap snapshot guidance
-----------------------------------
1. Start the server under heap profiling:

       node --heapsnapshot-near-heap-limit=5 --heap-prof app.js

   '--heapsnapshot-near-heap-limit=5' writes a .heapsnapshot file each
   time the heap approaches the configured limit, letting you diff
   snapshots across load-generating runs.

2. For a targeted before/after pair, snapshot explicitly:

       const v8 = require('v8');
       // after warmup, before the workload spike
       v8.writeHeapSnapshot('./heap-before.heapsnapshot');
       // run the workload under test, then:
       if (global.gc) global.gc();
       v8.writeHeapSnapshot('./heap-after.heapsnapshot');

3. Inspect snapshots in Chrome DevTools (chrome://inspect -> Memory
   -> 'Save and load profiles') and diff the retained-size histograms
   of 'CONCATENATED_STRING', 'ARRAY', 'CLOSURE' and object class names.
   Watch for constructors whose count grows monotonically between dumps.

4. Event-listener leaks: run with --trace-warnings and search the heap
   snapshot for 'EventListener' / 'Trigger' entries; prefer listeners
   registered with { once: true } or removed via .removeEventListener().

5. Map findings back to code: a growing 'CLOSURE' count usually means an
   event emitter or Promise chain retains the callback; use Chrome's
   Retainers panel to walk the reference chain to the leak root.

Use one profiler per runtime -- the Python pipeline in this module detects
the same class of leak from the interpreter side.
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="leak_profiler",
        description="Detect sustained allocation growth in a zero-arg callable.",
    )
    parser.add_argument("--target", default="",
                        help="module:func to run repeatedly (default: built-in demo)")
    parser.add_argument("--iterations", type=int, default=6,
                        help="paired snapshot iterations (default 6)")
    parser.add_argument("--min-growth", type=int, default=1 << 20,
                        help="cumulative byte threshold for a leak signature")
    parser.add_argument("--key", choices=("lineno", "filename", "traceback"),
                        default="lineno", help="tracemalloc grouping key")
    parser.add_argument("--out", default="", help="write the JSON report here")
    parser.add_argument("--node", action="store_true",
                        help="print V8/Node heap-snapshot guidance and exit")
    args = parser.parse_args(argv)

    if args.node:
        print(NODE_GUIDANCE)
        return 0

    if args.target:
        try:
            target = resolve_target(args.target)
        except (ImportError, AttributeError, ValueError, TypeError) as exc:
            print(f"leak_profiler: cannot load target: {exc}", file=sys.stderr)
            return 2
    else:
        target = leaky_demo
        print("no --target given, using built-in leaky_demo()", file=sys.stderr)

    detector = Detector(min_growth=args.min_growth, key=args.key)
    report = detector.run(target, iterations=max(2, args.iterations))
    payload = json.dumps(report.to_json(), indent=2, sort_keys=True)
    print(payload)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Warm up in a real environment, then attach the profiler to the *existing* process if possible. For Python: run the target under `python -X importtime` first only when import-time allocation matters; otherwise the module's own `tracemalloc.start()` covers everything.
2. Exercise the target manually the same number of times the detector will (default 6) so lazily-initialized singletons (caches, pools, connection managers) are warm *before* iteration zero; otherwise the first iteration looks like a leak.
3. Run the detector:
   - `python leak_profiler.py --target "app.services:create_client" --iterations 6 --out leak_report.json`
   - `python leak_profiler.py --key traceback --min-growth 2097152` raises the bar to 2 MiB and groups by full traceback.
   - `python leak_profiler.py` runs the built-in `leaky_demo` to smoke-test the pipeline.
4. Read `candidates`: a candidate needs (a) cumulative byte growth ≥ `--min-growth`, (b) mostly monotone growth, (c) a repeating traceback fingerprint. `iterations == n` means the signature was present in every iteration — the strongest leak signal.
5. Corroborate with the other signals:
   - `live_type_deltas` — an object type that grows but whose traceback is not in the candidates is usually a *cross-iteration* retention (the object was born in one call and retained by a global).
   - `survived_weakrefs` — objects the caller marked should die via `detector.track_lifetime(...)` that are still alive.
   - `circular_clusters` — type-name chains from `gc.get_referrers`; if a cluster names your own classes, the fix is often `__slots__` or breaking the cycle with `weakref`.
6. Fix candidates by removing the retaining reference, then re-run with the same parameters and confirm the candidate disappears and `collections_fired` rises (dead cycles now collectible).
7. For Node.js/V8 targets, follow `NODE_GUIDANCE` (`node --heapsnapshot-near-heap-limit=5 --heap-prof`) and diff before/after `.heapsnapshot` files in Chrome DevTools; keep the leak root's retainers chain for the ticket.
8. Turn the passing case into a regression guard: add a comment in the code or a CI step that runs the detector with `--target <hot-path>` and fails on non-empty `candidates`.

## 5. Edge Cases & Error Handling

- **`tracemalloc` overhead**: tracing multiplies allocation cost on hot paths; if wall-clock time matters, raise `--min-growth` and lower `--iterations` rather than disabling tracing.
- **First-iteration warm-up noise**: a candidate that only grows in iteration 1–2 but flattens later is a one-shot cache fill, not a leak. The monotonic-growth check plus `min_growth` already reject most of these; raise `min_iterations` (constructor parameter) if flaky.
- **`gc.get_objects()` counts depend on uncollectable dicts/tuples**: the tool's own report dict and frames are counted too. Compare deltas between runs, never absolute counts.
- **Frame/traceback objects hiding in `get_referrers`**: `find_circular_clusters` deliberately skips `type`/`ModuleType`/frames/code so it reports application cycles, not interpreter scaffolding.
- **Objects that cannot be weakref'd** (`int`, `str`, most `bytes`, `int`, `tuple`): `track_lifetime` will raise `TypeError` at registration — wrap the check so it degrades to a type-count delta rather than aborting the run.
- **`weakref` to an already-dead object returns `None`** from `ref()` — that is the *expected* outcome; `survived_weakrefs` only lists survivors, which is the leak signal.
- **Multi-threaded targets**: `tracemalloc` is interpreter-wide, so concurrent threads pollute deltas. Run the target single-threaded (or with a thread barrier) for clean signatures.
- **`--key traceback` fingerprints are memory-hungry** (each comparison materializes full stacks); keep `iterations <= 8` in that mode.
- **Interrupts / `KeyboardInterrupt`**: `atexit.register(tracemalloc.stop)` tears tracing down so a Ctrl-C does not leave the process tracing; the partially-collected `LeakReport` is still emitted.
- **Unexpected exceptions inside `target()`**: let them propagate — the detector's finally-equivalent bookkeeping (snapshots taken per iteration) means the failed iteration just contributes zero diffs; fix the target bug first and re-run.
