---
name: data-structure-optimizer
description: Analyze algorithm time/space complexity (Big O) and refactor logic using optimal data structures (Heaps, Tries, Hash Maps).
metadata:
  source: skills/data-structure-optimizer/data-structure-optimizer.md
---

# Data Structure Optimizer

## Prerequisites & Dependencies
- Comfortable with algorithm analysis (Big O notation)
- Language runtime: Node.js 18+, Python 3.10+, or Go 1.21+
- Optional: `npm i sortedmap` / `pip install rbtree` / `go data structures` for experimentation

## Execution Steps
1. Profile the target function/section with `console.time`, Python `timeit`, or Go `benchstat` to record current Big O behavior
2. Identify the bottleneck: nested loops, linear searches, frequent object allocations
3. Replace the incumbent structure with a more optimal one:
   - `Array → Hash Map` for O(1) lookups
   - `List → Heap` for priority-order processing
   - `Linear Scan → Trie` for prefix-heavy string sets
4. Rewrite the logic to use the new structure, keeping API compatibility
5. Re-benchmark and confirm the complexity class improved (e.g., O(n) → O(log n) or O(1))

```python
# From O(n) list lookup to O(1) hash map
# Before: linear search
def find_user(users, target_id):
    for u in users:
        if u['id'] == target_id:
            return u
    return None

# After: hash map lookup
user_map = {u['id']: u for u in users}
def find_user_fast(user_map, target_id):
    return user_map.get(target_id)
```
