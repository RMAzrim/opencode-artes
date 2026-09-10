---
id: memory-leak-debugger
file_path: skills/memory-leak-debugger.md
name: Memory Leak Debugger
category: debugging
tags: [memory-leak, debugging, garbage-collection, event-listeners]
author: opencode-core
version: 1.0.0
description: Identify and resolve unmanaged memory leaks, event listener leaks, and circular references across runtimes.
---

# Memory Leak Debugger

## Prerequisites & Dependencies
- Node.js with `--inspect` / Chrome DevTools, or Python `tracemalloc`, or Go `go tool pprof`
- Access to heap snapshots or memory profiling tools
- Basic understanding of GC roots and reference cycles

## Execution Steps
1. Start the application with memory profiling enabled (`node --inspect`, `python -m tracemalloc`, `go pprof http://localhost:6060`)
2. Exercise the app until the leak becomes noticeable (growing heap size, OOM warnings)
3. Take a heap snapshot and compare it over time (`heap-diff`, `tracemalloc.compare_to`, `pprof web`)
4. Identify retaining objects: look for large arrays, closures, DOM/event listeners, or unresolved Promises
5. Remove unexpected references: clear timers/intervals, remove event listeners (`removeEventListener`), use `WeakMap`/`weakref` where appropriate
6. Re-run the profile to confirm the leak is sealed, and add automated memory regression tests

```python
# Python example: detecting leaks with tracemalloc
import tracemalloc

tracemalloc.start()

def allocate_leak():
    # simulate unbounded growth
    data = [] * 10000  # grows each call
    return data

# Run and snapshot
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.compare_to(tracemalloc.take_snapshot(), 'lineno')
for stat in top_stats[:5]:
    print(stat)
```