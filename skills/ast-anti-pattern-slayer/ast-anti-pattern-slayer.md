---
id: ast-anti-pattern-slayer
file_path: skills/ast-anti-pattern-slayer/ast-anti-pattern-slayer.md
name: AST Anti-Pattern Slayer
category: core-coding
tags: [ast, refactoring, cyclomatic-complexity, dead-code, guard-clauses]
author: opencode-core
version: 1.0.0
description: Parses Python or JavaScript-style source into an AST, computes cyclomatic complexity v(G) as decision count plus one, maximum block nesting depth, bare except clauses and unreachable dead code, then uses a conservative ast.NodeTransformer to rewrite trailing if/else wrappers into semantics-preserving early return and continue guard clauses, emitting a structured JSON diagnostics report with file line and column locations.
---

# AST Anti-Pattern Slayer

## 1. System Architecture & Prerequisites

- Runtime binary: **Python 3.9 or newer** (requires `ast.unparse`, stable type hints, and `ast.TryStar`/`ast.Match` handling). Python 3.11+ is recommended.
- Standard library used (no third-party packages): `ast`, `argparse`, `json`, `sys`, `pathlib`.
- Input surface: a single Python source file (`*.py`) with the assignment to execute.
- The module never executes the analyzed code; all analysis is static and import-free, so the input file does not need resolvable imports at analysis time.
- The sample reference implementation `ast_slayer.py` doubles as a CLI:
  - `python ast_slayer.py path/to/script.py` — prints the JSON report.
  - `python ast_slayer.py path/to/script.py --fix` — additionally rewrites the file in place with guard clauses (only when a conservative rewrite is possible).
- JavaScript-style input is supported only conceptually (the same decision-node counting maps onto Mozilla ESTree shapes once the AST is parsed with a JS toolchain such as `acorn`/`esprima`); this skill ships the Python AST pipeline, which is architecture-identical.

## 2. Input/Output Data Contracts

### 2.1 CLI input options (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ast_slayer_cli_options",
  "type": "object",
  "properties": {
    "path":        { "type": "string", "description": "Path to the Python source file to analyze." },
    "fix":         { "type": "boolean", "default": false, "description": "Rewrite the file in place when a conservative guard-clause rewrite exists." },
    "require-else":{ "type": "boolean", "default": false, "description": "Only rewrite if/else wrappers; never rewrite a bare trailing if into a guard." },
    "max-depth":   { "type": "integer", "default": 4, "description": "Nesting depth above which blocks are flagged as 'deep-nesting'." },
    "json_out":    { "type": "string", "description": "Optional path to write the JSON report" }
  },
  "required": ["path"]
}
```

### 2.2 Output artifacts

- **JSON report** printed on stdout and optionally written to `--json <path>`:
  - `file`, `cyclomatic_complexity`, `max_nesting_depth`, `problem_count`, and `problems` (array of `{kind, line, col, detail}`), plus a `fix` object when `--fix` ran.
- **Transformed source** written back to the analyzed file only when `--fix` succeeded and at least one guard rewrite was applied. A failed parse or a failed rewrite leaves the file byte-for-byte untouched.

## 3. Production Reference Implementation

```python
"""AST Anti-Pattern Slayer.

Static-analysis module that parses a Python source file into an AST and
reports structural anti-patterns:

* cyclomatic complexity  v(G) = E - N + 2P, approximated as
  (# decision points) + 1. Decision points are ``if``/``elif``, ``while``,
  ``for``, ``except``, ``with``, conditional expressions, ``and``/``or``
  boolean operators, comprehensions and ``match`` cases.
* maximum block nesting depth (functions, classes, if/for/while/with/try/
  match/handler bodies each count as one level).
* bare ``except:`` handlers (they swallow BaseException subclasses such as
  KeyboardInterrupt and SystemExit).
* dead code: statements located after an unconditional ``return``, ``raise``,
  ``break`` or ``continue`` inside the same suite.

The ``GuardClauseTransformer`` then rewrites the very common "whole body
wrapped in an if/else" shape into early-return / continue guard clauses.

Fibonacci demo (docstring-level contract)::

    def fib(n):                              # original
        if n <= 1:
            return n
        else:
            return fib(n - 1) + fib(n - 2)

    def fib(n):                              # after guard-clause rewrite
        if not (n <= 1):
            return fib(n - 1) + fib(n - 2)
        return n

The rewrite is conservative: it only fires when the ``if`` is the *final*
statement of a function or loop body, so no statement that followed the
``if`` in the original code can change execution order, and the inverse
condition is filled either with the original ``else`` suite or with the
implicit fall-through jump (``return None`` in function context,
``continue`` in loop context) so both branches behave identically.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

# Block constructs: each nested suite counts as one nesting level.
_BLOCK = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ast.If, ast.For, ast.AsyncFor, ast.While,
    ast.With, ast.AsyncWith, ast.Try, ast.TryStar,
    ast.Match, ast.ExceptHandler,
)

# Simple decision leaves: +1 branch each.
_DECISION = (
    ast.If, ast.While, ast.For, ast.AsyncFor,
    ast.ExceptHandler, ast.With, ast.AsyncWith, ast.IfExp,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
)

_UNCONDITIONAL = (ast.Return, ast.Raise, ast.Break, ast.Continue)


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def cyclomatic_complexity(tree: ast.AST) -> int:
    """v(G) approximated as (# decision points) + 1 (P == 1 entry)."""
    decision_points = 1
    for node in ast.walk(tree):
        if isinstance(node, ast.Match):
            decision_points += len(node.cases)
        elif isinstance(node, ast.BoolOp):
            decision_points += max(0, len(node.values) - 1)
        elif isinstance(node, _DECISION):
            decision_points += 1
    return decision_points


def max_nesting_depth(tree: ast.AST) -> int:
    """Maximum depth of nested blocks/procedures in the tree."""
    deepest = 0

    def walk(node: ast.AST, depth: int) -> None:
        nonlocal deepest
        deepest = max(deepest, depth)
        for child in ast.iter_child_nodes(node):
            step = 1 if isinstance(child, _BLOCK) else 0
            walk(child, depth + step)

    walk(tree, 0)
    return deepest


def find_bare_excepts(tree: ast.AST) -> list:
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            hits.append({
                "kind": "bare-except",
                "line": node.lineno,
                "col": node.col_offset,
                "detail": "bare except: catches BaseException incl. KeyboardInterrupt",
            })
    return hits


def _suites(tree: ast.AST):
    """Yield every statement suite in the tree (each exactly once)."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor,
                             ast.With, ast.AsyncWith)):
            if node.body:
                yield node.body
            if node.orelse:
                yield node.orelse
        elif isinstance(node, (ast.Try, ast.TryStar)):
            if node.body:
                yield node.body
            for handler in node.handlers:
                if handler.body:
                    yield handler.body
            if node.orelse:
                yield node.orelse
            if node.finalbody:
                yield node.finalbody
        elif isinstance(node, ast.Match):
            for case in node.cases:
                if case.body:
                    yield case.body


def find_dead_code(tree: ast.AST) -> list:
    """Statements after an unconditional jump in the same suite are dead."""
    hits = []
    for suite in _suites(tree):
        dead = False
        for stmt in suite:
            if dead:
                hits.append({
                    "kind": "dead-code",
                    "line": getattr(stmt, "lineno", 0),
                    "col": getattr(stmt, "col_offset", 0),
                    "detail": f"unreachable after earlier jump; statement: {type(stmt).__name__}",
                })
            elif isinstance(stmt, _UNCONDITIONAL):
                dead = True
    return hits


def deep_nesting(tree: ast.AST, max_depth: int = 4) -> list:
    """Flag every block whose nesting depth exceeds ``max_depth``."""
    hits = []

    def walk(node: ast.AST, depth: int) -> None:
        if depth > max_depth and hasattr(node, "lineno"):
            hits.append({
                "kind": "deep-nesting",
                "line": node.lineno,
                "col": getattr(node, "col_offset", 0),
                "detail": f"nesting depth {depth} exceeds limit {max_depth}",
            })
        for child in ast.iter_child_nodes(node):
            step = 1 if isinstance(child, _BLOCK) else 0
            walk(child, depth + step)

    walk(tree, 0)
    return hits


# --------------------------------------------------------------------------
# refactoring
# --------------------------------------------------------------------------
class GuardClauseTransformer(ast.NodeTransformer):
    """Rewrite trailing if/else wraps into guard clauses.

    Only rewrites an ``If`` when it is the final statement of a function or
    loop body (never reorders code that followed it) and only when the
    ``if`` body is non-empty.  The relocated branch is placed under the
    inverted condition and an explicit fall-through jump is appended when
    the original branch would have fallen off the end of the block, so the
    control-flow outcome is preserved exactly.
    """

    def __init__(self, require_else: bool = False):
        super().__init__()
        self.require_else = require_else
        self.transforms_applied = 0

    # -- dispatch ------------------------------------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.body = self._transform_suite(node.body, context="function")
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node.body = self._transform_suite(node.body, context="function")
        return node

    def _loop_body(self, node: ast.stmt) -> ast.stmt:
        node.body = self._transform_suite(node.body, context="loop")
        return node

    def visit_For(self, node: ast.For) -> ast.AST:
        return self._loop_body(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> ast.AST:
        return self._loop_body(node)

    def visit_While(self, node: ast.While) -> ast.AST:
        return self._loop_body(node)

    # -- core ----------------------------------------------------------------
    def _transform_suite(self, body: list, context: str) -> list:
        transformed = []
        for stmt in body:
            out = self.visit(stmt)
            if out is None:
                continue
            if isinstance(out, list):
                transformed.extend(out)
            else:
                transformed.append(out)
        return self._tail_guard(transformed, context)

    def _tail_guard(self, body: list, context: str) -> list:
        if not body:
            return body
        tail = body[-1]
        if not isinstance(tail, ast.If) or not tail.body:
            return body
        if self.require_else and not tail.orelse:
            return body
        for stmt in body[:-1]:
            if isinstance(stmt, _UNCONDITIONAL):
                return body  # the trailing if itself would be unreachable
        return self._rewrite_tail(body, tail, context)

    def _rewrite_tail(self, body: list, tail: ast.If, context: str) -> list:
        prelude = body[:-1]
        jump = ast.Return(value=None) if context == "function" else ast.Continue()

        if tail.orelse:
            guard_body = list(tail.orelse)
            last_else = guard_body[-1]
            if not isinstance(last_else, _UNCONDITIONAL):
                guard_body.append(jump)
        else:
            guard_body = [jump]

        inverse = ast.UnaryOp(op=ast.Not(), operand=tail.test)
        ast.copy_location(inverse, tail.test)
        guard = ast.If(test=inverse, body=guard_body, orelse=[])
        ast.copy_location(guard, tail)

        main_suite = list(tail.body)
        self.transforms_applied += 1
        return prelude + [guard] + main_suite


# --------------------------------------------------------------------------
# reporting & CLI
# --------------------------------------------------------------------------
def report_tree(tree: ast.AST, path: Path, max_depth: int = 4) -> dict:
    problems = []
    problems.extend(find_bare_excepts(tree))
    problems.extend(find_dead_code(tree))
    problems.extend(deep_nesting(tree, max_depth=max_depth))
    return {
        "file": str(path),
        "cyclomatic_complexity": cyclomatic_complexity(tree),
        "max_nesting_depth": max_nesting_depth(tree),
        "problems": problems,
        "problem_count": len(problems),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="ast_slayer",
        description="Static AST analysis and conservative guard-clause refactoring.",
    )
    parser.add_argument("path", help="path to the Python source file")
    parser.add_argument("--fix", action="store_true",
                        help="rewrite the file in place with guard clauses")
    parser.add_argument("--require-else", action="store_true",
                        help="only rewrite if/else wrappers, never a bare trailing if")
    parser.add_argument("--max-depth", type=int, default=4,
                        help="nesting threshold to flag (default 4)")
    parser.add_argument("--json", dest="json_out",
                        help="also write the JSON report to this path")
    args = parser.parse_args(argv)

    source_path = Path(args.path)
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {source_path}: {exc}", file=sys.stderr)
        return 2
    try:
        tree = ast.parse(source, filename=str(source_path))
    except SyntaxError as exc:
        print(f"error: parse failed {source_path}:{exc.lineno}: {exc.msg}",
              file=sys.stderr)
        return 2

    report = report_tree(tree, source_path, args.max_depth)

    if args.fix:
        transformer = GuardClauseTransformer(require_else=args.require_else)
        try:
            new_tree = transformer.visit(tree)
        except Exception as exc:
            # never let a rewrite corrupt the file
            print(f"error: transformation failed, file left untouched: {exc}",
                  file=sys.stderr)
            report["fix"] = {"applied": False, "error": str(exc)}
        else:
            ast.fix_missing_locations(new_tree)
            report["fix"] = {
                "applied": transformer.transforms_applied > 0,
                "guard_transforms": transformer.transforms_applied,
            }
            if transformer.transforms_applied:
                source_path.write_text(ast.unparse(new_tree) + "\n", encoding="utf-8")

    payload = json.dumps(report, indent=2, sort_keys=True)
    print(payload)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    return 1 if report["problem_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Verify the runtime: `python --version` must report 3.9+.
2. Confirm the target file parses on its own compiler: `python -m py_compile <file>` (this catches syntax errors before AST analysis).
3. Run the report only first: `python ast_slayer.py path/to/file.py --json report.json`. Inspect `problem_count`, `cyclomatic_complexity`, and `max_nesting_depth` before changing anything.
4. Review the `problems` array. Fix **dead code** and **bare excepts** by hand — those two are never auto-rewritten by design.
5. For `deep-nesting` / high-complexity hits, run the conservative refactor: `python ast_slayer.py path/to/file.py --fix`. The transformer only rewrites a trailing `if ... else ...` (or bare trailing `if`) that is the last statement of a function or loop body into a guard clause:
   - function body: `if not <cond>: <else-suite>; return None` followed by the original main suite;
   - loop body: `if not <cond>: <else-suite>; continue` followed by the original main suite.
6. Re-run the report after the rewrite and diff the complexity / nesting deltas. If `guard_transforms` is 0, the file contains no structurally rewritable pattern — do not force it.
7. If the modification is intentional, run the project's own test/lint pipeline (e.g. `pytest`, `ruff check`) to confirm behavior is unchanged; the transformer is semantics-preserving but is not a substitute for the test suite.
8. Iterate per file. Each run is idempotent: a second `--fix` on an already-rewritten file is a no-op because the trailing `if` is gone.

## 5. Edge Cases & Error Handling

- **Syntax errors**: `ast.parse` failure aborts with exit code 2 and never touches the file. The agent must treat the file as un-analyzable and report the line/column from the `SyntaxError`.
- **Encoding**: read/write are `utf-8`. A non-UTF-8 file raises `UnicodeDecodeError`; catch it (or wrap the read) and fall back to `sys.getdefaultencoding()` detection before giving up.
- **Bare `if` rewrite is off by default of the guard pattern policy of this skill's conservative mode**: `--require-else` narrows the rewrite; without it, a bare trailing `if` that ends a function body is still safe to rewrite because fall-through equals an implicit `return None`.
- **Unreachable trailing `if`**: if any preceding statement in the suite is an unconditional jump, `_tail_guard` refuses the rewrite even though `find_dead_code` will have flagged it — semantics are preserved by not moving code across jumps.
- **Nested functions and generators**: `ast.Return(None)` inside a generator body behaves like `StopIteration`, i.e. identical to falling off the end, so generator functions remain correct after the rewrite.
- **`break`/`continue` inside `try`**: a trailing `if` used inside a `try` block is never in a function/loop tail position (the `try` body is the tail), so it is never rewritten — conservative by construction.
- **Non-printable / unusual unicode and `ast.unparse` limitations**: `ast.unparse` may normalize whitespace or reformat expressions (e.g. string quoting) even when only one guard was applied. Document that in the report; if byte-preservation is required, use `--require-else` and review the diff.
- **Failure recovery**: every exit path either leaves the original file untouched or has already completed a full atomic write; the CLI prints `error:` lines to stderr and returns 2 on recoverable failures. The agent should re-run against a copy (`cp file.py file.py.bak`) when iterating on source that is under version control.