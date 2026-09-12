---
id: bytecode-decompiler-assistant
file_path: skills/bytecode-decompiler-assistant/bytecode-decompiler-assistant.md
name: Bytecode Decompiler & Obfuscation Assistant
category: core-coding
tags: [bytecode, decompiler, dis, pyc, obfuscation]
author: opencode-core
version: 1.0.0
description: Loads Python pyc bytecode via marshal after importlib header validation, pretty-prints raw dis, reconstructs a basic-block control-flow graph annotated with loop heads and try/except regions, renames mangled single-letter variables using usage heuristics, renders a readable structured pseudo-Python outline, flags obfuscation signatures such as missing strings, oversized constants and dynamic eval execution, and documents the uncompyle6 byte-exact pipeline when it is installable.
---

# Bytecode Decompiler & Obfuscation Assistant

## 1. System Architecture & Prerequisites

- Runtime binary: **Python 3.9 or newer** (uses `dis.get_instructions`, `ast.unparse`-free rendering, `importlib.util.MAGIC_NUMBER`, `marshal`). Tested primarily on CPython 3.9–3.13 `.pyc` files.
- Standard library only: `dis`, `marshal`, `importlib.util`, `io`, `json`, `argparse`, `re`, `sys`, `pathlib`, `types.CodeType`, `dataclasses`, `typing`.
- Optional (documented in Section 4, never required by the ship'ed module): **`uncompyle6`** from PyPI for byte-exact decompilation of matching CPython versions, and the `xdis` package it wraps. When the installed interpreter matches the `.pyc` version, `uncompyle6 file.pyc` produces exact source.
- Input: a single `.pyc` (Python bytecode) file — either a timestamp pyc (16-byte header: magic + flags + mtime + source size), a PEP 552 hash-based pyc (magic + flags + 8-byte hash), or a bare `marshal`-dumped code object. Loading is **not** a security boundary: `marshal` can craft hostile objects; analyze only trusted files or run inside a throwaway sandbox.

## 2. Input/Output Data Contracts

### 2.1 CLI input options (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "unpyc_assistant_cli_options",
  "type": "object",
  "properties": {
    "pyc":    { "type": "string", "description": "Path to the .pyc file to analyze." },
    "out":    { "type": "string", "description": "Path where reconstructed pseudo-Python is written." },
    "report": { "type": "string", "description": "Path where the JSON diagnostics/show report is written." },
    "dis":    { "type": "boolean", "default": false, "description": "Print raw disassembly for the module and nested code objects." },
    "demo":   { "type": "boolean", "default": false, "description": "Reconstruct a compiled built-in sample instead of --pyc." }
  },
  "oneOf": [
    { "required": ["pyc"] },
    { "required": ["demo"] }
  ]
}
```

### 2.2 Output artifacts

- **Reconstructed source** (`--out`): readable pseudo-Python with `def` headers, `for`/`while`/`if`/`try` framing, renamed variables, and `#` block annotations. Documented as a faithful structured reconstruction, not a byte-exact decompilation.
- **Diagnostics report** (`--report`): JSON with one entry per code object (`name`, `argc`, `varnames`, `rendered_lines`) plus `obfuscation` findings (`no-string-constants`, `oversized-constants`, `dynamic-execution`) and `nested_code_objects` count.
- No input files are modified by this skill.

## 3. Production Reference Implementation

```python
"""Bytecode Decompiler & Obfuscation Assistant.

Loads Python ``.pyc`` bytecode, disassembles it, rebuilds a structured
basic-block control-flow graph, renames mangled single-letter variables by
usage heuristics, renders readable pseudo-Python, and flags obfuscation
signatures.

Pipeline:
``load_pyc()``   -> CodeType (importlib.header-aware marshal load)
``disassemble()``-> raw ``dis.dis`` text
``flow_reconstruct()`` -> CFG of basic blocks with loop-head / try-except
                          annotations and edge lists
``usage_stats()`` + ``rename_mangled()`` -> semantic variable names
``render_source()`` -> readable pseudo-Python outline (NOT byte-exact)
``detect_obfuscation()`` -> report of stripped-string and eval-style payloads

Section on obfuscation: obfuscated/decompiler-hostile ``.pyc`` files are
detected by (a) an absence of string constants (string-stripped pycs),
(b) oversized int/bytes constants (payload blobs), and (c) module-level
references to ``eval``/``exec``/``marshal``/``base64``/``zlib`` used to
decode a payload at runtime.

When ``uncompyle6`` (PyPI) is installed and the CPython version matches the
pyc, byte-exact source can be produced externally:
    python -m uncompyle6 file.pyc
The structured reconstruction in this module remains the dependency-free
fallback.
"""

from __future__ import annotations

import argparse
import dis
import importlib.util
import io
import json
import marshal
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------
def load_pyc(path: Union[str, Path]) -> CodeType:
    """Load a .pyc file into a code object.

    When the on-disk magic matches the running interpreter, the marshaled
    code object starts right after the fixed 16-byte header (magic, flags,
    timestamp/size, or PEP 552 hash).  Otherwise a raw marshal attempt is
    made against every plausible header offset so legacy pycs without a
    recognized magic can still load when their marshal stream aligns.
    """
    data = Path(path).read_bytes()
    if not data:
        raise ValueError(f"{path} is empty")
    magic = data[:4]
    if magic == importlib.util.MAGIC_NUMBER:
        code = _code_from_marshal(data[16:], str(path), magic)
        return code
    for offset in (8, 12, 16, 0):
        try:
            code = marshal.loads(data[offset:])
        except (ValueError, TypeError, EOFError, MemoryError):
            continue
        if isinstance(code, CodeType):
            return code
    raise ValueError(
        f"{path}: unrecognized pyc magic {magic!r}; this interpreter expects "
        f"{importlib.util.MAGIC_NUMBER!r}. Recompile with the matching "
        f"Python or point load_pyc at the writer's runtime."
    )


def _code_from_marshal(blob: bytes, label: str, magic: bytes) -> CodeType:
    try:
        code = marshal.loads(blob)
    except (ValueError, TypeError, EOFError, MemoryError) as exc:
        raise ValueError(f"{label}: magic matches but marshal load failed: {exc}") from exc
    if not isinstance(code, CodeType):
        raise ValueError(f"{label}: marshal payload is not a code object")
    return code


# --------------------------------------------------------------------------
# dis
# --------------------------------------------------------------------------
def disassemble(code: CodeType, show_caches: bool = False) -> str:
    out = io.StringIO()
    dis.dis(code, file=out, show_caches=show_caches)
    return out.getvalue()


# --------------------------------------------------------------------------
# control-flow reconstruction
# --------------------------------------------------------------------------
@dataclass
class Block:
    index: int
    start: int
    instructions: List[dis.Instruction] = field(default_factory=list)
    kind: str = "plain"
    exits: List[int] = field(default_factory=list)
    ends_with: str = "fall"      # fall | jump | return | raise
    loop_head: bool = False
    try_root: bool = False
    handler: bool = False


@dataclass
class CFG:
    code: CodeType
    blocks: List[Block] = field(default_factory=list)
    vacuous: bool = False

    def index_of(self, target: int) -> Optional[int]:
        for b in self.blocks:
            if b.start == target:
                return b.index
        return None


_TERMINATORS = {"RETURN_VALUE", "RETURN_CONST", "RAISE_VARARGS", "RAISE_CONST",
                "POP_EXCEPT", "END_FINALLY", "BREAK_LOOP", "CONTINUE_LOOP",
                "EXCEPT_HANDLER"}


def _is_jump(ins: dis.Instruction) -> bool:
    return ins.opname.startswith("JUMP") or ins.opname == "FOR_ITER"


_COND_JUMPS = {
    "POP_JUMP_IF_FALSE", "POP_JUMP_IF_TRUE",
    "POP_JUMP_FORWARD_IF_FALSE", "POP_JUMP_FORWARD_IF_TRUE",
    "POP_JUMP_BACKWARD_IF_FALSE", "POP_JUMP_BACKWARD_IF_TRUE",
    "JUMP_IF_FALSE_OR_POP", "JUMP_IF_TRUE_OR_POP",
    "JUMP_IF_FALSE", "JUMP_IF_TRUE",
}


def _is_conditional_jump(ins: dis.Instruction) -> bool:
    return ins.opname in _COND_JUMPS


def flow_reconstruct(code: CodeType) -> CFG:
    """Split the instruction stream into basic blocks and annotate loops
    and try/except regions."""
    instrs = list(dis.get_instructions(code))
    cfg = CFG(code=code)
    if not instrs:
        cfg.vacuous = True
        return cfg

    starts = {instrs[0].offset}
    for ins in instrs:
        if _is_jump(ins) or ins.opname in {"SETUP_LOOP", "SETUP_EXCEPT", "SETUP_FINALLY"}:
            if isinstance(ins.argval, int):
                starts.add(ins.argval)
    for i, ins in enumerate(instrs[:-1]):
        if _is_jump(ins) or ins.opname in _TERMINATORS:
            starts.add(instrs[i + 1].offset)
    starts = sorted(starts)

    i = 0
    while i < len(instrs):
        block_start = instrs[i].offset
        block_ins: List[dis.Instruction] = []
        while i < len(instrs):
            ins = instrs[i]
            block_ins.append(ins)
            barrier = _is_jump(ins) or ins.opname in _TERMINATORS
            nxt_offset = instrs[i + 1].offset if i + 1 < len(instrs) else None
            if barrier or (nxt_offset is not None and nxt_offset in starts):
                i += 1
                break
            i += 1
        cfg.blocks.append(Block(index=len(cfg.blocks), start=block_start,
                                instructions=block_ins))

    _compute_edges(cfg)
    _annotate(cfg)
    return cfg


def _compute_edges(cfg: CFG) -> None:
    for block in cfg.blocks:
        last = block.instructions[-1]
        name = last.opname
        if name in {"RETURN_VALUE", "RETURN_CONST"}:
            block.ends_with = "return"
        elif name in {"RAISE_VARARGS", "RAISE_CONST", "RERAISE"}:
            block.ends_with = "raise"
        elif _is_jump(last):
            block.ends_with = "jump"
            if isinstance(last.argval, int):
                t = cfg.index_of(last.argval)
                if t is not None:
                    block.exits.append(t)
            if (name == "FOR_ITER" or "JUMP_IF" in name
                    or name.startswith("POP_JUMP")):
                if block.index + 1 < len(cfg.blocks):
                    block.exits.append(block.index + 1)


def _annotate(cfg: CFG) -> None:
    for block in cfg.blocks:
        if any(ins.opname == "FOR_ITER" for ins in block.instructions):
            block.loop_head = True
        for ins in block.instructions:
            if ins.opname in {"SETUP_EXCEPT", "SETUP_FINALLY"}:
                block.try_root = True
            if ins.opname in {"POP_EXCEPT", "END_FINALLY", "EXCEPT_HANDLER", "RERAISE"}:
                block.handler = True
    for src in cfg.blocks:
        for tgt_idx in src.exits:
            tgt = cfg.blocks[tgt_idx]
            if tgt.start < src.start:
                tgt.loop_head = True


# --------------------------------------------------------------------------
# graph helpers
# --------------------------------------------------------------------------
def _reachable(cfg: CFG, start: int) -> Set[int]:
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for e in cfg.blocks[cur].exits:
            if e not in seen:
                seen.add(e)
                stack.append(e)
    return seen


def _preds(cfg: CFG, nodes: Set[int]) -> Dict[int, Set[int]]:
    preds: Dict[int, Set[int]] = {n: set() for n in nodes}
    for n in nodes:
        for e in cfg.blocks[n].exits:
            if e in preds:
                preds[e].add(n)
    return preds


def _loop_body(cfg: CFG, head: int) -> Set[int]:
    reach = _reachable(cfg, head)
    preds = _preds(cfg, reach)
    back: Set[int] = set()
    work = [head]
    while work:
        n = work.pop()
        if n in back:
            continue
        back.add(n)
        for p in preds.get(n, ()):
            if p not in back:
                work.append(p)
    return reach & back


def _loop_exit(cfg: CFG, head: int, body: Set[int]) -> Optional[int]:
    for b in body:
        for e in cfg.blocks[b].exits:
            if e not in body:
                return e
    return None


# --------------------------------------------------------------------------
# expression / statement translator
# --------------------------------------------------------------------------
_BIN = {0: "+", 1: "-", 2: "*", 3: "/", 4: "//", 5: "%", 6: "**",
        7: "<<", 8: ">>", 9: "&", 10: "^", 11: "|"}
_CMP = {0: "<", 1: "<=", 2: "==", 3: "!=", 4: ">", 5: ">=",
        6: "is", 7: "is not", 8: "in", 9: "not in"}
_OLD_BIN = {"BINARY_ADD": "+", "BINARY_SUBTRACT": "-", "BINARY_MULTIPLY": "*",
            "BINARY_TRUE_DIVIDE": "/", "BINARY_FLOOR_DIVIDE": "//",
            "BINARY_MODULO": "%", "BINARY_POWER": "**",
            "BINARY_LSHIFT": "<<", "BINARY_RSHIFT": ">>",
            "BINARY_AND": "&", "BINARY_XOR": "^", "BINARY_OR": "|"}


def _clean_sym(s: str) -> str:
    s = s.strip()
    if s.startswith("bool(") and s.endswith(")"):
        return s[5:-1]
    if s.startswith("(") and s.endswith(")"):
        return s[1:-1]
    return s


def _op_sym(ins: dis.Instruction) -> str:
    av = getattr(ins, "argval", None)
    if isinstance(av, str) and av.strip():
        return _clean_sym(av)
    if ins.arg is not None and isinstance(ins.arg, int):
        if "COMPARE" in ins.opname:
            return _CMP.get(ins.arg, "?")
        return _BIN.get(ins.arg, "?")
    return _OLD_BIN.get(ins.opname, "?")


def _expr(ins: dis.Instruction, stack: List[str], names: Dict[str, str]) -> Optional[str]:
    """Translate one instruction.  Statement-producing instructions return a
    line; all others push/pop the expression stack and return None."""
    name = ins.opname
    if (name.startswith("LOAD_CONST") or name == "PUSH_CONST"
            or "SMALL_INT" in name or "MEDIUM_INT" in name or "SMALL_STR" in name):
        if isinstance(ins.argval, CodeType):
            return None  # nested code objects are rendered as their own section
        stack.append(repr(ins.argval))
        return None
    if (name.startswith("LOAD_FAST") or name in {"LOAD_NAME", "LOAD_DEREF",
                                                 "LOAD_GLOBAL", "LOAD_CLASSDEREF"}):
        if isinstance(ins.argval, str):
            stack.append(names.get(ins.argval, ins.argval))
        return None
    if name.startswith("LOAD_ATTR") and isinstance(ins.argval, str):
        if stack:
            stack.append(f"{stack.pop()}.{ins.argval}")
        return None
    if name in {"CALL", "CALL_FUNCTION", "CALL_FUNCTION_KW"}:
        argc = ins.arg if isinstance(ins.arg, int) else 0
        kw = 1 if name == "CALL_FUNCTION_KW" else 0
        n_args = max(0, argc - kw)
        if len(stack) >= n_args + 1:
            args = stack[-n_args:] if n_args else []
            if n_args:
                del stack[-n_args:]
            func = stack.pop()
            stack.append(f"{func}({', '.join(args)})")
        return None
    if name.startswith("IMPORT_NAME") and isinstance(ins.argval, str):
        stack.append(ins.argval)
        return None
    if name in {"BINARY_SUBSCR", "BINARY_OP", "COMPARE_OP", "COMPARISON_OP"}:
        if name == "BINARY_SUBSCR" and len(stack) >= 2:
            idx = stack.pop()
            obj = stack.pop()
            stack.append(f"{obj}[{idx}]")
            return None
        if len(stack) >= 2:
            rhs = stack.pop()
            lhs = stack.pop()
            stack.append(f"{lhs} {_op_sym(ins)} {rhs}")
        return None
    if name in _OLD_BIN and len(stack) >= 2:
        rhs = stack.pop()
        lhs = stack.pop()
        stack.append(f"{lhs} {_op_sym(ins)} {rhs}")
        return None
    if name.startswith("UNARY_NOT"):
        if stack:
            stack.append(f"not ({stack.pop()})")
        return None
    if name.startswith("UNARY_NEGATIVE"):
        if stack:
            stack.append(f"-({stack.pop()})")
        return None
    if name in {"STORE_FAST", "STORE_NAME", "STORE_DEREF"}:
        var = ins.argval if isinstance(ins.argval, str) else "?"
        value = stack.pop() if stack else "..."
        return f"{names.get(var, var)} = {value}"
    if name.startswith("STORE_ATTR") and isinstance(ins.argval, str):
        if len(stack) >= 2:
            attr = ins.argval
            obj = stack.pop()
            value = stack.pop()
            return f"{obj}.{attr} = {value}"
        return None
    if name == "POP_TOP":
        if stack:
            stack.pop()
        return None
    if name == "RETURN_VALUE":
        value = stack.pop() if stack else "None"
        return f"return {value}"
    if name == "RETURN_CONST":
        return f"return {repr(ins.argval)}"
    if name.startswith("RAISE"):
        return "raise <exception>"
    if name in {"GET_ITER", "PUSH_NULL", "PRECALL", "KW_NAMES",
                "RESUME", "NOT_TAKEN", "END_FOR", "POP_ITER",
                "MAKE_FUNCTION", "RETURN_GENERATOR"}:
        return None
    return None


# --------------------------------------------------------------------------
# variable renaming
# --------------------------------------------------------------------------
def _fresh() -> Dict[str, int]:
    return {"stores": 0, "loads": 0, "iter": 0, "incremented": 0}


def usage_stats(code: CodeType) -> Dict[str, Dict[str, int]]:
    """Heuristic per-variable usage: how often each name is stored/loaded,
    whether it is the target of a FOR_ITER (loop variable) and whether it
    is fed straight into a BINARY_OP (increment-ish)."""
    stats: Dict[str, Dict[str, int]] = {}
    insns = list(dis.get_instructions(code))
    for i, ins in enumerate(insns):
        v = ins.argval
        if not isinstance(v, str):
            continue
        d = stats.setdefault(v, _fresh())
        if (ins.opname.startswith("STORE_FAST") or ins.opname.startswith("STORE_NAME")
                or ins.opname.startswith("STORE_DEREF")):
            d["stores"] += 1
        elif (ins.opname.startswith("LOAD_FAST") or ins.opname.startswith("LOAD_NAME")
              or ins.opname.startswith("LOAD_DEREF") or ins.opname == "LOAD_GLOBAL"):
            d["loads"] += 1
        if "FOR_ITER" in ins.opname:
            for nxt in insns[i + 1:]:
                if nxt.opname.startswith("STORE_FAST") or nxt.opname.startswith("STORE_NAME"):
                    if isinstance(nxt.argval, str):
                        stats.setdefault(nxt.argval, _fresh())["iter"] += 1
                    break
        if (ins.opname.startswith("BINARY_") or ins.opname.startswith("INPLACE_")):
            if i - 1 >= 0 and insns[i - 1].opname.startswith("LOAD_") \
                    and isinstance(insns[i - 1].argval, str):
                stats.setdefault(insns[i - 1].argval, _fresh())["incremented"] += 1
    return stats


def rename_mangled(varnames: List[str], usage: Dict[str, Dict[str, int]]) -> Dict[str, str]:
    """Map single-letter/underscore names to semantic names based on the
    usage statistics (i -> index when incremented, l1/iter vars -> item,
    n -> count, and so on), guaranteeing unique outputs."""
    preferred = {
        "i": "index", "j": "index2", "k": "index3",
        "n": "count", "c": "char", "v": "value", "d": "data",
        "t": "tmp", "x": "coord_x", "y": "coord_y",
        "l": "item", "ln": "line", "idx": "index", "s": "string",
    }
    mapping: Dict[str, str] = {}
    used: Set[str] = set()
    for v in varnames:
        if not isinstance(v, str) or not v:
            continue
        base = v.lstrip("_") or "var"
        u = usage.get(v, {})
        if u.get("iter", 0) > 0 and u.get("incremented", 0) == 0:
            suggested = "item"
        elif u.get("incremented", 0) > 0:
            suggested = "index"
        elif base in preferred:
            suggested = preferred[base]
        else:
            suggested = base
        candidate = suggested
        suffix = 2
        while candidate in used:
            candidate = f"{suggested}_{suffix}"
            suffix += 1
        used.add(candidate)
        mapping[v] = candidate
    return mapping


# --------------------------------------------------------------------------
# pseudo-source rendering
# --------------------------------------------------------------------------
INDENT = "    "


def _cond_expr(block: Block, names: Dict[str, str]) -> str:
    stack: List[str] = []
    for ins in block.instructions:
        if _is_conditional_jump(ins):
            break
        _expr(ins, stack, names)
    return stack[-1] if stack else "<condition>"


def _for_iterable(block: Block, names: Dict[str, str]) -> str:
    stack: List[str] = []
    for ins in block.instructions:
        if ins.opname == "FOR_ITER":
            break
        _expr(ins, stack, names)
    return stack[-1] if stack else "<iterable>"


def _for_loop_var(cfg: CFG, head: int, names: Dict[str, str]) -> Optional[str]:
    body = _loop_body(cfg, head)
    cands = [(cfg.blocks[b].start, b) for b in body if b != head]
    if not cands:
        return None
    first = min(cands)[1]
    for ins in cfg.blocks[first].instructions:
        if ins.opname in {"STORE_FAST", "STORE_NAME", "STORE_DEREF"}:
            if isinstance(ins.argval, str):
                return names.get(ins.argval, ins.argval)
        return None
    return None


def _loop_cond(cfg: CFG, head: int, body: Set[int], names: Dict[str, str]) -> str:
    for b in sorted(body):
        c = cfg.blocks[b]
        last = c.instructions[-1]
        if _is_conditional_jump(last):
            e = _cond_expr(c, names)
            if "TRUE" in last.opname and "FALSE" not in last.opname:
                return f"not ({e})"
            return e
    return "True"


def _ends_in_forward_jump(cfg: CFG, ids: List[int]) -> Optional[int]:
    if not ids:
        return None
    lastb = ids[-1]
    last = cfg.blocks[lastb].instructions[-1]
    if _is_jump(last) and not _is_conditional_jump(last) \
            and isinstance(last.argval, int):
        tgt = cfg.index_of(last.argval)
        if tgt is not None and tgt > lastb:
            return tgt
    return None


def render_source(cfg: CFG, names: Optional[Dict[str, str]] = None) -> str:
    """Render a faithful structured pseudo-Python outline of the CFG."""
    if names is None:
        usage = usage_stats(cfg.code)
        names = rename_mangled(list(cfg.code.co_varnames), usage)
    if cfg.vacuous:
        return "# (no bytecode)"

    out: List[str] = []
    emitted: Set[int] = set()
    DEPTH_LIMIT = 60
    LINE_LIMIT = 12000

    def pad(level: int) -> str:
        return INDENT * level

    def flush_block(block: Block, level: int) -> None:
        stack: List[str] = []
        for ins in block.instructions:
            if _is_jump(ins):
                break
            stmt = _expr(ins, stack, names)
            if stmt:
                out.append(pad(level) + stmt)
            if ins.opname in {"RETURN_VALUE", "RETURN_CONST",
                              "RAISE_VARARGS", "RAISE_CONST"}:
                break

    def emit_blocks(ids: List[int], level: int, depth: int) -> None:
        for rid in ids:
            emit(rid, level, depth)

    def emit(idx: Optional[int], level: int, depth: int) -> None:
        while idx is not None:
            if len(out) > LINE_LIMIT or depth > DEPTH_LIMIT:
                return
            if idx >= len(cfg.blocks) or idx in emitted:
                return
            block = cfg.blocks[idx]

            # --- loop head --------------------------------------------------
            if block.loop_head:
                emitted.add(idx)
                body = _loop_body(cfg, idx)
                body_ids = sorted(b for b in body if b != idx)
                if any(i.opname == "FOR_ITER" for i in block.instructions):
                    var = _for_loop_var(cfg, idx, names) or "item"
                    it = _for_iterable(block, names)
                    out.append(f"{pad(level)}for {var} in {it}:")
                else:
                    out.append(f"{pad(level)}while {_loop_cond(cfg, idx, body, names)}:")
                for b in body_ids:
                    emit(b, level + 1, depth + 1)
                idx = _loop_exit(cfg, idx, body)
                continue

            # --- try root ---------------------------------------------------
            if block.try_root:
                emitted.add(idx)
                out.append(f"{pad(level)}try:  # setup at offset {block.start}")
                handler_idx = None
                for ins in block.instructions:
                    if ins.opname in {"SETUP_EXCEPT", "SETUP_FINALLY"} \
                            and isinstance(ins.argval, int):
                        handler_idx = cfg.index_of(ins.argval)
                j = idx + 1
                guard = 0
                while j is not None and j < len(cfg.blocks) and guard < 2000:
                    guard += 1
                    if j == handler_idx or cfg.blocks[j].handler:
                        break
                    if cfg.blocks[j].loop_head or cfg.blocks[j].try_root:
                        break
                    emit(j, level + 1, depth + 1)
                    last = cfg.blocks[j].instructions[-1]
                    if _is_jump(last) or last.opname in _TERMINATORS:
                        nxt = [e for e in cfg.blocks[j].exits
                               if e is not None and e > j]
                        j = nxt[0] if nxt else None
                        if j is None:
                            break
                        if cfg.blocks[j].start < cfg.blocks[idx].start + 1:
                            break
                    else:
                        j += 1
                if j is not None and j < len(cfg.blocks) \
                        and (j == handler_idx or cfg.blocks[j].handler):
                    out.append(f"{pad(level)}except <handler> as exc:  # block {j}")
                    emit(j, level + 1, depth + 1)
                    idx = j + 1
                else:
                    out.append(f"{pad(level)}# except handler nested or 3.11+-style")
                    idx = j
                continue

            # --- conditional jump -> if/else --------------------------------
            last = block.instructions[-1]
            if _is_conditional_jump(last) and isinstance(last.argval, int):
                t = cfg.index_of(last.argval)
                expr = _cond_expr(block, names)
                cond = f"not ({expr})" if ("TRUE" in last.opname
                                           and "FALSE" not in last.opname) else expr
                emitted.add(idx)
                fall_ids: List[int] = []
                j = idx + 1
                guard = 0
                while j is not None and j < len(cfg.blocks) and guard < 2000:
                    guard += 1
                    if j == t:
                        break
                    if cfg.blocks[j].loop_head or cfg.blocks[j].try_root:
                        break
                    fall_ids.append(j)
                    last_j = cfg.blocks[j].instructions[-1]
                    if _is_jump(last_j) or last_j.opname in _TERMINATORS:
                        nxt = [e for e in cfg.blocks[j].exits
                               if e is not None and e > j]
                        j = nxt[0] if nxt else None
                        if j is None or j == t:
                            break
                        if cfg.blocks[j].start < cfg.blocks[idx].start + 1:
                            break
                    else:
                        j += 1
                out.append(f"{pad(level)}if {cond}:")
                emit_blocks(fall_ids, level + 1, depth + 1)
                if t is not None and t < len(cfg.blocks):
                    join = _ends_in_forward_jump(cfg, fall_ids)
                    if join is not None and join != t and join > t:
                        out.append(f"{pad(level)}else:")
                        emit_blocks(list(range(t, join)), level + 1, depth + 1)
                        idx = join
                    else:
                        out.append(f"{pad(level)}# else/goto -> block {t}")
                        idx = t
                    continue
                idx = j
                continue

            # --- straight-line block ----------------------------------------
            emitted.add(idx)
            flush_block(block, level)
            if block.ends_with == "jump" and block.exits:
                if block.exits[0] != idx + 1:
                    out.append(f"{pad(level)}# -> block {block.exits[0]}")
                idx = block.exits[0]
                continue
            if block.ends_with in {"return", "raise"}:
                return
            idx = idx + 1

    emit(0, 0, 0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


# --------------------------------------------------------------------------
# obfuscation detection
# --------------------------------------------------------------------------
def _walk_consts(code: CodeType):
    stack = [code]
    while stack:
        c = stack.pop()
        for const in c.co_consts:
            yield const
            if isinstance(const, CodeType):
                stack.append(const)


def detect_obfuscation(code: CodeType) -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    consts = list(_walk_consts(code))
    strings = [c for c in consts if isinstance(c, str)]
    if not strings:
        flags.append({
            "kind": "no-string-constants",
            "detail": "code carries no string constants (string-stripped pyc "
                      "or heavy obfuscation)",
        })
    huge = [c for c in consts
            if (isinstance(c, bytes) and len(c) > (1 << 22))
            or (isinstance(c, int) and (c.bit_length() + 7) // 8 > (1 << 22))]
    if huge:
        flags.append({
            "kind": "oversized-constants",
            "count": len(huge),
            "detail": f"{len(huge)} constants each exceed 4 MiB (payload blobs)",
        })
    names = set(code.co_names)
    dyn = [n for n in ("eval", "exec", "marshal", "base64", "zlib",
                       "builtins") if n in names]
    if "eval" in dyn or "exec" in dyn:
        flags.append({
            "kind": "dynamic-execution",
            "detail": f"module references {', '.join(dyn)} likely for "
                      f"runtime payload decoding",
        })
    return flags


def all_codes(code: CodeType) -> List[CodeType]:
    """Module code plus every nested code object, depth-first, deduped."""
    seen_ids: Set[int] = set()
    order: List[CodeType] = []

    def walk(c: CodeType) -> None:
        if id(c) in seen_ids:
            return
        seen_ids.add(id(c))
        order.append(c)
        for const in c.co_consts:
            if isinstance(const, CodeType):
                walk(const)

    walk(code)
    return order


def reconstruct_source(code: CodeType) -> Tuple[str, Dict[str, Any]]:
    parts: List[str] = []
    report: Dict[str, Any] = {
        "file": getattr(code, "co_filename", "<unknown>"),
        "magic_ok": True,
        "obfuscation": detect_obfuscation(code),
        "functions": [],
        "nested_code_objects": 0,
    }
    for chunk in all_codes(code):
        cfg = flow_reconstruct(chunk)
        usage = usage_stats(chunk)
        names = rename_mangled(list(chunk.co_varnames), usage)
        body = render_source(cfg, names=names)
        if chunk.co_name and chunk.co_name != "<module>":
            params = ", ".join(chunk.co_varnames[: chunk.co_argcount]) or ""
            parts.append(f"def {chunk.co_name}({params}):")
            if body.strip():
                parts.append("\n".join(INDENT + ln for ln in body.splitlines()))
            else:
                parts.append(INDENT + "pass  # reconstructed outline")
        elif body.strip():
            parts.append(body)
        else:
            parts.append("# empty code object")
        report["functions"].append({
            "name": chunk.co_name,
            "argc": chunk.co_argcount,
            "varnames": list(chunk.co_varnames),
            "rendered_lines": len(body.splitlines()),
        })
        report["nested_code_objects"] += 1
    return "\n".join(parts).strip() + "\n", report


def _sample_code_object() -> CodeType:
    src = (
        "def find(items, target):\n"
        "    for i in range(len(items)):\n"
        "        if items[i] == target:\n"
        "            return i\n"
        "    return -1\n"
        "marks = find([3, 1, 4, 1, 5], 4)\n"
        "print(marks)\n"
    )
    return compile(src, "<demo>", "exec")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="unpyc_assistant",
        description="Disassemble and reconstruct Python .pyc bytecode; "
                    "flag obfuscation heuristics.",
    )
    parser.add_argument("--pyc", help="path to the .pyc file to analyze")
    parser.add_argument("--out", default="", help="write reconstructed source here")
    parser.add_argument("--report", default="",
                        help="write the JSON diagnostics report here")
    parser.add_argument("--dis", action="store_true",
                        help="print raw disassembly first")
    parser.add_argument("--demo", action="store_true",
                        help="reconstruct a built-in compiled sample instead of --pyc")
    args = parser.parse_args(argv)

    if args.demo:
        code = _sample_code_object()
        label = "<demo>"
    elif args.pyc:
        try:
            code = load_pyc(Path(args.pyc))
        except (ValueError, OSError, MemoryError) as exc:
            print(f"unpyc_assistant: {exc}", file=sys.stderr)
            return 2
        label = args.pyc
    else:
        parser.error("--pyc is required (or pass --demo)")
        return 2

    if args.dis:
        print(f"# disassembly of {label}")
        print(disassemble(code))

    text, report = reconstruct_source(code)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    report["source_file"] = args.out or None
    payload = json.dumps(report, indent=2, sort_keys=True)
    print("# " + payload)
    if args.report:
        Path(args.report).write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Verify the runtime and the pyc's origin: `python -c "import importlib.util, sys; print(sys.version, importlib.util.MAGIC_NUMBER.hex())"`. The loader accepts only the running interpreter's magic plus raw-marshal fallbacks; cross-version `.pyc` needs the matching runtime or `uncompyle6` (see step 6).
2. Preflight the file: `file sample.pyc` (or `xxd sample.pyc | head`) to confirm the 4-byte magic and the header shape before loading.
3. Load and disassemble first: `python unpyc_assistant.py --pyc sample.pyc --dis`. Read the raw `dis` output to sanity-check the reconstructed control flow you are about to trust.
4. Produce the structured reconstruction: `python unpyc_assistant.py --pyc sample.pyc --out sample_recon.py --report sample_report.json`. The rendered source is a *structured outline*: loops/try/if framing is real, but expression details (attribute chains, keyword args, comprehensions) are approximated and annotated with block indices in comments.
5. Read the report's `obfuscation` array:
   - `no-string-constants` — the pyc had all text stripped (common in packed malware/obfuscated deployables); treat every reconstructed call accordingly.
   - `oversized-constants` — 4 MiB+ int/bytes blobs; inspect via `marshal` and un-pickling offline, never by executing them.
   - `dynamic-execution` — module references `eval`/`exec`/`marshal`/`base64`; flag the pyc as potentially self-decoding and refuse to run it in a privileged context.
   - Deeper checks: for suspected bytecode-level tampering, compare `code.co_code` length and `magic` against a clean build of the same source (`python -m compileall`) and diff the two `.pyc`s.
6. When byte-exact source is required and `uncompyle6` is available (matches the CPython version of the pyc), use the external pipeline:
   ```
   python -m pip install uncompyle6
   python -m uncompyle6 sample.pyc            # stdout
   python -m uncompyle6 -o out/ sample.pyc    # one .py per module
   ```
   Cross-check its output against this module's reconstruction; agreement on framing is strong evidence the reconstruction is faithful.
7. For the JavaScript/Node bytecode case, the same decomposition applies with the V8 disassembler flags (`node --print-bytecode` or `js2pyc`-style tooling); this skill's CFG math (basic blocks, back-edge loop heads, exception handler regions) is language-agnostic.
8. Iterate: render → compare with `--dis` output → adjust nothing in the module (it is intentionally heuristic) but record block-of-interest offsets in the ticket.

## 5. Edge Cases & Error Handling

- **Magic mismatch**: `load_pyc` raises `ValueError` naming both magics; never force-load foreign-version bytecode — `marshal` format alone can corrupt or mis-tag. Recompile with the writer's Python or use a matching toolchain.
- **Truncated / corrupt `.pyc`**: `EOSError`/`ValueError` from `marshal.loads` inside the loop fall through all offsets and produce a clear `ValueError`; truncated files never partially mutate state (loading is read-only).
- **Bare marshaled blobs**: files that are *just* a marshaled code object (no header) are recovered by the offset-`0` fallback.
- **`PEP 552` hash-based pycs**: header is still 16 bytes (4 magic + 4 flags + 8 hash), so `data[16:]` is correct; confirmed by matching `importlib.util.MAGIC_NUMBER`.
- **Python 3.11+ exception tables**: `SETUP_EXCEPT`/`POP_EXCEPT` no longer exist as raw opcodes; `flow_reconstruct` falls back to `co_exceptiontable`-agnostic bounds and the renderer emits a `# except handler: nested or 3.11+-style` comment rather than guessing a wrong `except`.
- **`FOR_ITER` variants and cache instructions**: `dis.get_instructions` hides caches by default; the block splitter tolerates variant opcodes because it keys on offset containment, not opcode identity.
- **Pathologically nested code objects**: `all_codes` dedupes by `id()` and `render_source` caps depth (60) and lines (12000); pathological payloads produce truncated-but-valid outlines with `#` comments, never an exception.
- **Recursion in `gc`-style back-links / malicious constants**: rendering only ever calls `repr` and `str` on constants; a `__repr__`-abusing object is not possible in raw marshal constants (marshaled objects are immutable primitives and code), so there is no `__repr__` re-entry risk.
- **Sandbox note**: `marshal.loads` can deserialize hostile graphs (e.g. deep recursion causing `MemoryError`); catch `MemoryError` explicitly (done) and run suspicious pycs inside a subprocess with `ulimit -v`/container limits.
- **Variable rename collisions**: `rename_mangled` guarantees uniqueness by suffixing (`index`, `index_2`, ...); names that already look semantic (`result`, `data`) pass through unchanged.
- **Imperfect hearsay**: the module explicitly does NOT claim byte-exact output; treat `uncompyle6` as the authoritative second opinion whenever framing disagreements matter.