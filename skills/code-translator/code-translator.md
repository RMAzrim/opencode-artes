---
id: code-translator
file_path: skills/code-translator/code-translator.md
name: Code Translator
category: developer-experience
tags: [code-conversion, polyglot, refactoring, behavioral-parity]
author: opencode-core
version: 1.0.0
description: Precisely convert code logic from one programming language to another.
---

# Code Translator

## Prerequisites & Dependencies
- Toolchains of both source and target languages (compilers/interpreters, formatters)
- An executable test suite or reference inputs/outputs to prove behavioral parity after translation
- Standard library / dependency mapping notes (e.g., source packages → target equivalents)

## Execution Steps
1. Read the source fully and record observable behavior: inputs, outputs, side effects, error semantics, and edge cases (null/empty/overflow handling).
2. Build a dependency map: for each library call, select the target-language equivalent; for missing equivalents, plan a shim or wrapper.
3. Translate in order: type signatures → function bodies → control flow, preferring idiomatic target constructs (e.g., errors-as-values in Go, exceptions in Python, `Result` in Rust) over literal word-for-word substitution.
4. Preserve algorithmic complexity and memory semantics; note intentionally diverged locations (integer division, string encoding, hash ordering).
5. Port the test suite first, or generate golden tests from source behavior; then run against the translation and diff the outputs.
6. Run the target language's formatter/linter and document migration notes: changed APIs, dropped features, replacement libraries needed.

```python
# source (Python)
def top_scores(entries: list[tuple[str, int]], n: int) -> list[str]:
    return [name for name, _ in sorted(entries, key=lambda e: -e[1])[:n]]
```

```go
// target (Go)
type Entry struct { Name  string; Score int }

func TopScores(entries []Entry, n int) []string {
	sort.SliceStable(entries, func(i, j int) bool { return entries[i].Score > entries[j].Score })
	if n > len(entries) { n = len(entries) }
	names := make([]string, 0, n)
	for _, e := range entries[:n] { names = append(names, e.Name) }
	return names
}
```
```