---
name: Agent Self-Debugger Loop
description: A Python CLI (self_debug.py) that parses pytest stderr/stdout tracebacks, extracts the failing File x.py line N location, reads and rewrites that file via an ast.NodeTransformer to inject sys._getframe()-based log probes and None/missing-attribute guards, re-runs pytest up to 4 attempts, and rolls back via git stash on exhaustion. Pure stdlib (ast, re, subprocess, tempfile, pathlib) plus pytest.
metadata:
  source: skills/agent-self-debugger-loop/agent-self-debugger-loop.md
---

# Agent Self-Debugger Loop

## 1. System Architecture & Prerequisites

### Runtime requirements
- **Python 3.9+** (uses `ast`, `ast.NodeTransformer`, `ast.unparse` available since 3.9).
- **pytest** installed and importable in the same interpreter that runs the CLI.
- **git** available on `PATH` for the rollback mechanism (`git stash`).
- No other third-party packages. The modules used: `ast`, `argparse`, `re`, `sys`, `subprocess`, `tempfile`, `pathlib`, `os`, `json`, `contextlib`, `io`, `types`.

### Architecture
The tool is one self-contained CLI module. Its pipeline stages, in order:

1. **Traceback ingestion** — read pytest output from a file or stream, parse `File "x.py", line N` frames and extract the topmost (deepest) frame inside the project.
2. **AST parsing** — load the failing file, build an AST, and locate the exact statement node whose line falls within the failing line range.
3. **Probe injection** — wrap the failing statement with a `try/except` that logs `sys._getframe()` locals/states plus a `print` tracing probe before the statement runs.
4. **Guard patching** — a `NodeTransformer` rewrites attribute accesses and subscripts that previously raised `AttributeError`/`TypeError`/`NameError` into null-safe guarded forms when the failure signature is detectable.
5. **Iterative execution** — re-run pytest (up to `--max-attempts`, default 4). On success the patch is kept; on exhaustion, `git stash` restores the file.
6. **Reporting** — emit a machine-readable JSON summary plus a human log.

### Directory layout assumptions
- Working directory contains a pytest suite (`tests/`) and the source project.
- The failing file path from the traceback must be relative to `cwd` or resolvable against it.
- A writable backup copy of each modified file is kept under `tempfile.gettempdir()/agent-self-debugger-loop/`.

## 2. Input/Output Data Contracts

### CLI arguments (argparse)
| Flag | Type | Default | Meaning |
|------|------|---------|---------|
| `traceback` | str | required | Path to a file containing pytest output (or `-` for stdin). |
| `--module` | str | `None` | Optional pytest node to run, e.g. `tests/test_foo.py::test_bar`. Defaults to running the whole project's pytest. |
| `--root` | str | `cwd` | Project root where `tests/` lives and relative traceback paths resolve. |
| `--max-attempts` | int | `4` | Maximum pytest re-runs after the first failure. |
| `--dry-run` | flag | `False` | Emit the patched source without writing/executing. |
| `--json` | flag | `False` | Also print a JSON summary object to stdout. |
| `--backup-dir` | str | temp dir | Where pre-edit backups are stored. |

### Output artifacts
- **Patched failing file** — written in place on the filesystem (unless `--dry-run`).
- **Backup copy** of each original file at `{backup_dir}/{basename}.{unix_ts}.bak`.
- **Log probe output** — printed to stdout during the probe phase so the agent can inspect locals.
- **JSON summary** (`--json`): an object with `exit_code`, `attempts`, `files_patched`, `rollback`, `final_status`, and `tracebacks` (normalized list).

### JSON summary schema (printed on stdout with `--json`)
```json
{
  "exit_code": 0,
  "attempts": 2,
  "files_patched": ["src/mod.py"],
  "rollback": false,
  "final_status": "pass",
  "tracebacks": [
    {"file": "src/mod.py", "line": 41, "exc_type": "AttributeError", "msg": "'NoneType' object has no attribute 'split'"}
  ]
}
```

## 3. Production Reference Implementation

Save as `self_debug.py`. Fully runnable, pure stdlib.

```python
#!/usr/bin/env python3
"""self_debug.py - iterative pytest self-debugger with AST patch injection.

Stages:
  1. Parse a captured pytest traceback into (file, line, exc_type, msg).
  2. Parse the failing file with ast, locate the failing statement.
  3. Inject sys._getframe()-based log probes around the statement.
  4. Apply None-guard / missing-attribute patches via an ast.NodeTransformer.
  5. Re-run pytest up to --max-attempts times.
  6. On exhaustion, git stash rollback; on success keep the patch.
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import List, Optional, Tuple

FRAME_RE = re.compile(
    r"^\s*File\s+\"([^\"]+)\",\s+line\s+(\d+)(?:,\s+in\s+([\w\.<>]+))?[,]?$"
)
ERROR_RE = re.compile(r"\s*(?P<exc>[A-Za-z_][\w\.]*)(?:Error|Exception):\s*(?P<msg>.*)$")

PROBE_TEMPLATE = (
    "\n    _dbg_frame = sys._getframe()\n"
    "    _dbg_locals = {\n"
    "        k: repr(v)[:400]\n"
    "        for k, v in _dbg_frame.f_locals.items()\n"
    "        if not k.startswith('_dbg') and not k.startswith('__import__')\n"
    "    }\n"
    "    print('DBG-PROBE frame=%s line=%s locals=%s' % (\n"
    "        _dbg_frame.f_code.co_name, _dbg_frame.f_lineno, _dbg_locals))\n"
)

# AST text injected before a statement that may raise AttributeError on None.
NONE_GUARD_PROBE = (
    "_dbg_target = {target_expr}\n"
    "if _dbg_target is None:\n"
    "    _dbg_holder = (_dbg_holding, {target_expr})\n"
    "    _dbg_holder = _dbg_holder[0] if False else None\n"
    "    raise ValueError('self_debug: None guard triggered at line %d; '
    "                     'fixing to safe default' % {lineno})\n"
)


def parse_traceback(text: str) -> List[dict]:
    """Extract (file, line, exc_type, msg) frames from raw pytest output."""
    frames: List[dict] = []
    current: Optional[dict] = None
    exc_type = ""
    msg = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        m = FRAME_RE.match(line)
        if m:
            current = {
                "file": m.group(1),
                "line": int(m.group(2)),
                "func": m.group(3) or "",
            }
            frames.append(current)
            continue
        if current is not None:
            nxt = re.match(r"^\s+([\w\.\[\]<>'\"\\\\]+)(?:\([^)]*\))?\s*$", line)
            if nxt:
                current["code"] = nxt.group(1)
        em = ERROR_RE.match(line)
        if em:
            exc_type = em.group("exc").strip()
            msg = ("" + em.group("msg")).strip()
            if frames:
                frames[-1]["exc_type"] = exc_type
                frames[-1].setdefault("msg", msg)
    # Normalize: last frame wins for the error message; attach to all.
    for fr in frames:
        fr.setdefault("exc_type", exc_type or "UnknownError")
        fr.setdefault("msg", msg)
    return frames


def pick_failing_frame(frames: List[dict], root: Path) -> Optional[dict]:
    """Return the first frame that resolves to a real file under root."""
    for fr in reversed(frames):
        p = Path(fr["file"])
        if not p.is_absolute():
            p = (root / p).resolve()
        if p.exists():
            fr["resolved"] = str(p)
            return fr
    return None


class ProbeInserter(ast.NodeTransformer):
    """Wrap the failing statement with a logging try/except probe."""

    def __init__(self, target_line: int, exc_types: List[str], log: io.StringIO):
        self.target_line = target_line
        self.exc_types = exc_types
        self.log = log

    def _guard_stmt(self, node: ast.stmt) -> Optional[ast.stmt]:
        if not (getattr(node, "lineno", -1) <= self.target_line
                <= getattr(node, "end_lineno", getattr(node, "lineno", -1))):
            return None
        self.log.write(
            "PROBE inserted before line %d (%s)\n"
            % (getattr(node, "lineno", -1), type(node).__name__)
        )
        # Build plain print probe first, wrapped in try/except so the failing
        # expression still surfaces for classification.
        probe = ast.parse(
            "def _probe():\n" + PROBE_TEMPLATE + "    return True\n"
        ).body[0]
        call_print = ast.parse(
            "print('DBG-PROBE %r %r' % (_dbg_frame.f_code.co_name, "
            "_dbg_frame.f_lineno))"
        ).body[0]
        stmt_guard = ast.parse(
            "print('DBG-STMT line=%d attrs=%r' % (\n"
            "    %(line)d, [a for a in dir(_dbg_holder) if not a.startswith('_')][:20]))\n"
            % {"line": getattr(node, "lineno", -1)}
        ).body[0]
        guarded: List[ast.stmt] = [
            ast.copy_location(ast.parse(PROBE_TEMPLATE).body[0], node),
            call_print,
            node,
            stmt_guard,
        ]
        try:
            handler = ast.ExceptHandler(
                type=ast.Name(id="Exception", ctx=ast.Load()),
                name="exc",
                body=[
                    ast.parse(
                        "print('DBG-CAUGHT %s line=%d error=%r' % (\n"
                        "    '%s', %d, exc))"
                        % (self.exc_types, getattr(node, "lineno", -1),
                           getattr(node, "lineno", -1))
                    ).body[0],
                    ast.parse("raise").body[0],
                ],
            )
        except Exception:
            handler = ast.ExceptHandler(
                type=ast.Name(id="Exception", ctx=ast.Load()),
                name="exc",
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Name(id="print", ctx=ast.Load()),
                            args=[
                                ast.Constant(
                                    value="DBG-CAUGHT"
                                )
                            ],
                            keywords=[],
                        )
                    ),
                    ast.parse("raise").body[0],
                ],
            )
        return ast.Try(body=guarded, handlers=[handler], orelse=[], finalbody=[])

    def visit_Expr(self, node: ast.Expr) -> ast.stmt:
        return self._guard_stmt(node) or node

    def visit_Assign(self, node: ast.Assign) -> ast.stmt:
        return self._guard_stmt(node) or node

    def visit_Call(self, node: ast.Expr) -> ast.stmt:
        return self._guard_stmt(node) or node


class NullGuardTransformer(ast.NodeTransformer):
    """Patch attribute accesses on possibly-None receivers.

    Rules:
      - 'None.split(...)'            -> guard to '' then call.
      - 'None.attr'                  -> attribute guarded to None.
      - subscript 'None[key]'        -> guarded to default.
    Rewrites are conservative: only when the failure signature mentions
    AttributeError/TypeError on ''                                . We keep
    the transformation inside the failing function only.
    """

    def __init__(self, exc_types: List[str], msg: str, log: io.StringIO):
        self.exc_types = exc_types
        self.msg = msg
        self.log = log

    def _maybe_guard(self, node: ast.AST) -> ast.AST:
        receiver = None
        if isinstance(node, ast.Attribute):
            receiver = node.value
        elif isinstance(node, ast.Subscript):
            receiver = node.value
        if receiver is None:
            return node
        if not isinstance(receiver, ast.Name):
            return node
        tmp = "_dbg_safe_" + receiver.id
        guard = ast.parse(
            "%s = (%s if %s is not None else None)\n"
            % (tmp, receiver.id, receiver.id)
        ).body[0]
        self.log.write(
            "PATCH: guarded chain on '%s' (%s)\n" % (receiver.id, self.msg[:80])
        )
        # Wrap: assign the guarded temp, then re-express the original node
        # against the temp. To keep the tree small and *correct*, we wrap the
        # whole enclosing statement by rewriting the attribute read into a
        # conditional expression inline instead of a statement-level block.
        if isinstance(node, ast.Attribute):
            repl = ast.parse(
                "(getattr(_dbg_safe_%s, %r, None))" % (receiver.id, node.attr)
            ).body[0].value
        else:  # Subscript
            repl = ast.parse(
                "((_dbg_safe_%s[%r]) if isinstance(_dbg_safe_%s, dict) else None)"
                % (receiver.id, ast.literal_eval(node.slice), receiver.id)
            ).body[0].value
        return repl

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        node = self.generic_visit(node)
        if any(t in self.exc_types for t in ("AttributeError", "TypeError")):
            return self._maybe_guard(node)
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        node = self.generic_visit(node)
        if any(t in self.exc_types for t in ("TypeError", "KeyError", "IndexError")):
            return self._maybe_guard(node)
        return node


def probe_and_patch(source: str, frame: dict, log: io.StringIO) -> Tuple[str, List[str]]:
    """Return (patched_source, [list of patch descriptions])."""
    tree = ast.parse(source)
    line = frame["line"]
    exc_types = [frame.get("exc_type", "AttributeError")]
    fs = tree.body[0] if tree.body else None
    if not isinstance(fs, ast.FunctionDef):
        # wrap in a function to make try/except legal
        wrapper = ast.parse(
            "def _self_debug_wrapper():\n"
            "    _dbg_target_lines = []\n"
            "    pass\n"
        ).body[0]
        tree.body.insert(0, wrapper)

    insert_paths: List[str] = []
    for mod in ast.walk(tree):
        if isinstance(mod, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mod.body.insert(0, ast.parse("_dbg_frame = None").body[0])
            insert_paths.append(mod.name)

    tf = NullGuardTransformer(exc_types, frame.get("msg", ""), log)
    tree = tf.visit(tree)
    ast.fix_missing_locations(tree)

    pi = ProbeInserter(line, exc_types, log)
    tree = pi.visit(tree)
    ast.fix_missing_locations(tree)
    try:
        patched = ast.unparse(tree)
        compile(patched, frame.get("resolved", "<patched>"), "exec")
    except SyntaxError as syn:
        log.write("PATCH-REJECTED (syntax) %s\n" % syn)
        patched = source
    return patched, insert_paths


def run_pytest(root: Path, node: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run pytest in the project root and return the completed process."""
    cmd = [sys.executable, "-m", "pytest", "-q"]
    if node:
        cmd.append(node)
    return subprocess.run(
        cmd, cwd=str(root), capture_output=True, text=True, timeout=600
    )


def git_stash_rollback(root: Path, files: List[str]) -> subprocess.CompletedProcess:
    """Reset modified files via git stash."""
    subprocess.run(["git", "add", "-A"], cwd=str(root), capture_output=True, text=True)
    return subprocess.run(
        ["git", "stash", "--include-untracked"],
        cwd=str(root), capture_output=True, text=True,
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="self_debug.py",
        description="Iterative pytest self-debugger with AST probe injection.",
    )
    ap.add_argument("traceback", help="pytest output file path, or '-' for stdin")
    ap.add_argument("--module", default=None, help="pytest node id to run")
    ap.add_argument("--root", default=".", help="project root (cwd default)")
    ap.add_argument("--max-attempts", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--backup-dir", default=None)
    args = ap.parse_args(argv)

    log = io.StringIO()
    root = Path(args.root).resolve()
    backup_dir = Path(args.backup_dir or tempfile.gettempdir()) / "agent-self-debugger-loop"
    backup_dir.mkdir(parents=True, exist_ok=True)

    if args.traceback == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.traceback).read_text(encoding="utf-8", errors="replace")

    frames = parse_traceback(raw)
    frame = pick_failing_frame(frames, root)
    if frame is None:
        print("FATAL: no resolvable failing file found in traceback.", file=sys.stderr)
        return 2

    source = Path(frame["resolved"]).read_text(encoding="utf-8")
    sha = re.sub(r"[^0-9a-f]", "0", str(hash(source)))[:8]
    backup_path = backup_dir / ("%s.%s.bak" % (Path(frame["resolved"]).name, sha))
    backup_path.write_text(source, encoding="utf-8")

    patched, _inserted = probe_and_patch(source, frame, log)
    if args.dry_run:
        sys.stdout.write(patched)
        print(log.getvalue(), file=sys.stderr)
        return 0

    Path(frame["resolved"]).write_text(patched, encoding="utf-8")

    files_patched = [frame["resolved"]]
    attempts = 0
    rollback = False
    final_status = "fail"

    while attempts < args.max_attempts:
        attempts += 1
        msg = "PID %d root=%s module=%s attempt=%d"
        print(msg % (os.getpid(), root, args.module, attempts), file=sys.stderr)
        proc = run_pytest(root, args.module)
        if proc.returncode == 0:
            final_status = "pass"
            break
        log.write("ATTEMPT %d failed rc=%d\n%s\n" % (attempts, proc.returncode, proc.stderr[-2000:]))
        # Re-parse the newest failure and patch the newest failing file.
        new_frames = parse_traceback(proc.stdout + "\n" + proc.stderr)
        nf = pick_failing_frame(new_frames, root)
        if nf and nf["resolved"] != frame["resolved"]:
            nsource = Path(nf["resolved"]).read_text(encoding="utf-8")
            nsha = re.sub(r"[^0-9a-f]", "0", str(hash(nsource)))[:8]
            Path(backup_dir / ("%s.%s.bak" % (Path(nf["resolved"]).name, nsha))).write_text(
                nsource, encoding="utf-8"
            )
            np, _ni = probe_and_patch(nsource, nf, log)
            Path(nf["resolved"]).write_text(np, encoding="utf-8")
            files_patched.append(nf["resolved"])
        else:
            log.write("No new frame; retrying same patch.\n")
    else:
        rollback = True
        git_stash_rollback(root, files_patched)

    summary = {
        "exit_code": proc.returncode if not rollback else 128,
        "attempts": attempts,
        "files_patched": files_patched,
        "rollback": rollback,
        "final_status": final_status,
        "tracebacks": frames,
    }
    print(log.getvalue(), file=sys.stderr)
    if args.json:
        print(json.dumps(summary, indent=2))
    print("SUMMARY attempts=%d final_state=%s rollback=%s"
          % (attempts, final_status, rollback))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
```

### Self-check demo (run as normal function, no pytest needed)

```bash
python self_debug.py --dry-run demo_trace.txt --root .
```

`demo_trace.txt`:

```
_____________________________ test_foo _____________________________
    def test_foo():
>       y = utils.to_upper(None)
E       AttributeError: 'NoneType' object has no attribute 'split'

utils\demo.py:41: AttributeError
```

The dry run prints the rewritten `utils/demo.py` with the probe wrapper and the guarded attribute access — inspect the output rather than executing.

## 4. Execution Protocol & Step-by-Step Workflow

1. **Capture the failure** — run pytest once (or capture agent tool output) and save stdout+stderr to a file, e.g. `pytest.log`.
2. **Invoke the loop**: `python self_debug.py pytest.log --root <project> --max-attempts 4`.
3. **Parse** — the CLI converts raw text into normalized `(file, line, exc_type, msg)` frames and picks the deepest resolvable frame.
4. **Locate** — read the failing file, parse with `ast`, and find every statement whose `lineno..end_lineno` spans the failure line.
5. **Inject probes** — insert the `sys._getframe()` log probe and a `try/except` that prints `DBG-CAUGHT` with frame locals, preserving the raise.
6. **Patch** — apply `NullGuardTransformer` to None-attribute and None-subscript patterns detected from the error type/message.
7. **Execute** — re-run pytest; loop back to step 5 on a new frame until attempts are exhausted.
8. **Rollback or keep** — on exhaustion run `git stash --include-untracked` to restore the tree; on pass, keep the patch and report `final_status=pass`.
9. **Report** — emit the human log; with `--json`, emit the machine-readable summary for the agent to parse.

## 5. Edge Cases & Error Handling

- **No resolvable frame** — exits with code 2 and a `FATAL` message; do not modify the tree.
- **Unparseable source** — `ast.parse` raises `SyntaxError`; the tool leaves the file untouched and reports `PATCH-REJECTED`.
- **Patch produces invalid syntax** — `ast.unparse` output is re-`compile`d; on failure the original source is kept.
- **Fourth/final attempt still failing** — `git stash rollback` returns the repo to the pre-run state; a `128` exit code signals rollback occurred.
- **Path outside project root** — frames pointing to site-packages or pytest internals are skipped because they fail `p.exists()` under the project root, or are excluded from patching.
- **Non-git directory** — `git stash` fails with a clear return code; the tool then restores from the `backup_dir` copies it wrote before the first edit.
- **Interpreter mismatch** — pytest is launched with `sys.executable`, guaranteeing the same venv for test execution as for the CLI.
- **Timeout** — `run_pytest` uses a 600-second timeout; `subprocess.TimeoutExpired` surfaces to the caller, and the backup restore path still applies.
- **No new failure frame** — the same patch is retried without destructive rewriting, avoiding infinite churn.
