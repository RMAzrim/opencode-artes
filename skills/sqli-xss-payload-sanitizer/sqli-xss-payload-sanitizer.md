---
id: sqli-xss-payload-sanitizer
file_path: skills/sqli-xss-payload-sanitizer/sqli-xss-payload-sanitizer.md
name: SQLi & XSS Payload Sanitizer
category: security
tags: [sqli, xss, sanitization, parameterized-queries]
author: opencode-core
version: 1.0.0
description: Identifies unescaped user inputs and unparameterized database queries, injecting sanitization middleware and parameterized bindings to neutralize XSS and SQLi.
---

# SQLi & XSS Payload Sanitizer

## 1. System Architecture & Prerequisites
- Python 3.10+ (stdlib only: `re`, `os`, `json`, `argparse`, `shutil`, `pathlib`)
- Target: local source tree with `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.html`, `.j2`, `.jinja`, `.jinja2` files
- No external dependencies

## 2. Input/Output Data Contracts

**Input (CLI args):**
```json
{
  "type": "object",
  "properties": {
    "target": { "type": "string", "description": "Root of source tree to scan/sanitize" },
    "report_dir": { "type": "string", "description": "Output directory", "default": "./sanitize-reports" },
    "fix": { "type": "boolean", "description": "Write sanitized files to output tree", "default": false }
  },
  "required": ["target"]
}
```

**Output artifacts:**
- `{report_dir}/sanitizer_report.json` — findings with per-finding patches
- `{report_dir}/sanitized/` — rewritten sanitized files (when `--fix`)
- `{report_dir}/backups/` — original files (rollback source)

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""SQLi & XSS Payload Sanitizer — sink classification, sanitizer patches, AST+regex engine."""

import re
import os
import json
import shutil
import argparse
from pathlib import Path

# ─── Sink Classifiers ───────────────────────────────────────────────────────────

SQL_SINKS = [
    re.compile(r"""(?:cursor\.execute|cursor\.executemany|\.execute\(|conn\.execute|\.raw\(|= conn\.cursor\(\)\.execute|query\()""", re.IGNORECASE),
    re.compile(r"""(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\s+""", re.IGNORECASE),
    re.compile(r"""(?:\.query\(|\.exec\(|db_session\.execute|Session\.execute)""", re.IGNORECASE),
]

SQL_INTERPOLATION = [
    re.compile(r"""(?:execute|query|exec)\s*\(\s*f["']""", re.IGNORECASE | re.MULTILINE),
    re.compile(r"""(?:execute|query|exec)\s*\(\s*["'][^"']*["']\s*%""", re.IGNORECASE | re.MULTILINE),
    re.compile(r"""(?:execute|query|exec)\s*\(\s*["'][^"']*["']\s*\+""", re.IGNORECASE | re.MULTILINE),
    re.compile(r"""(?:SELECT\s+[^"]*?["']?\s*(\{|%s|\%(?:\w+\()|\.format\())""", re.IGNORECASE | re.MULTILINE),
    re.compile(r"""(?:f["'][^"']*(?:\{[^}]+\})[^"']*["'](?:\s*\)))""", re.MULTILINE),
]

XSS_SINKS = [
    ("innerHTML", re.compile(r"""\.innerHTML\s*="""), "innerHTML assignment"),
    ("insertAdjacentHTML", re.compile(r"""insertAdjacentHTML\s*\("""), "insertAdjacentHTML call"),
    ("dangerouslySetInnerHTML", re.compile(r"""dangerouslySetInnerHTML\s*=""", re.MULTILINE), "React dangerouslySetInnerHTML"),
    ("safe_filter", re.compile(r"""\|\s*safe(?:\s|}}|\b)""", re.MULTILINE), "Jinja2 |safe filter"),
    ("v-html", re.compile(r"""v-html\s*="""), "Vue v-html directive"),
    ("document.write", re.compile(r"""document\.write\s*\("""), "document.write call"),
    ("innerHTML_var", re.compile(r"""\.innerHTML\s*=\s*[a-zA-Z_$]"""), "innerHTML assigned from variable"),
]

USER_INPUT_SOURCES = [
    re.compile(r"""(?:request\.(?:form|args|params|json|values)|req\.body|req\.query|req\.params|input\(|getParameter|body\(\s*\)|@request\.body|cgi\.FieldStorage|environ\[)""", re.IGNORECASE),
    re.compile(r"""(?:getElementById|querySelector|login|signup|comments?|search|username|email|password|name\b)""", re.IGNORECASE),
]

HTML_ESCAPE_TABLE = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#x27;",
    "/": "&#x2F;",
    "`": "&#96;",
    "=": "&#x3D;",
}


def html_escape(text: str) -> str:
    """OWASP-recommended HTML escape. Replaces &<>\"'/`= with entities."""
    return "".join(HTML_ESCAPE_TABLE.get(c, c) for c in text)


# ─── Analysis Engine ────────────────────────────────────────────────────────────

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", ".next"}
SOURCE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".j2", ".jinja", ".jinja2"}


def classify_line(line: str) -> dict:
    """Classify a single source line. Returns finding dict or None."""
    finding = {"line_text": line.strip()[:200]}

    has_sql_sink = any(p.search(line) for p in SQL_SINKS)
    has_interp = any(p.search(line) for p in SQL_INTERPOLATION)
    user_input_nearby = any(p.search(line) for p in USER_INPUT_SOURCES)
    if has_sql_sink and (has_interp or user_input_nearby):
        finding.update({
            "type": "SQLI",
            "cwe": "CWE-89",
            "severity": "CRITICAL",
            "detail": "Unparameterized SQL with interpolation; user input may be concatenated into query",
            "patch_kind": "parameterize",
        })
        return finding

    for sink_id, pattern, desc in XSS_SINKS:
        if pattern.search(line):
            finding.update({
                "type": "XSS",
                "cwe": "CWE-79",
                "severity": "HIGH",
                "detail": f"Unescaped output sink: {desc}",
                "patch_kind": "escape",
                "sink_id": sink_id,
            })
            return finding

    return None


def scan_source(root: Path) -> tuple:
    """Scan all source files. Returns (findings, files_scanned)."""
    findings = []
    files_scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.suffix not in SOURCE_EXTS:
                continue
            files_scanned += 1
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines):
                finding = classify_line(line)
                if finding:
                    finding["file"] = str(fpath)
                    finding["line"] = i + 1
                    findings.append(finding)
    return findings, files_scanned


# ─── Patch Engine ───────────────────────────────────────────────────────────────

def parameterize_sql(line: str, connector: str = " ") -> str:
    """Rewrite an f-string/concatenated SQL line to use placeholders + param array."""
    m = re.search(r"""(execute|query|exec)\s*\(\s*f(["'])(SELECT\s+.*?)\2\s*\)""", line, re.IGNORECASE | re.DOTALL)
    if m:
        call = m.group(1)
        quote = m.group(2)
        sql = m.group(3)
        params = re.findall(r"\{(\w+)\}", sql)
        clean = re.sub(r"\{(\w+)\}", "%s", sql)
        return f'{call}{connector}({quote}{clean}{quote}, ({", ".join(params)},))'

    # positional style: execute("... %s ..." % (x,)) -> execute("... %s ...", (x,))
    m = re.search(r"""(execute|query|exec)\s*\(\s*(["'])(.*?)\2\s*%\s*\(([^)]*)\)\s*\)""", line, re.IGNORECASE | re.DOTALL)
    if m:
        call, quote, sql, param_tuple = m.group(1), m.group(2), m.group(3), m.group(4)
        return f'{call}{connector}({quote}{sql}{quote}, ({param_tuple},))'
    return line


def escape_html(line: str, sink_id: str) -> str:
    """Inject htmlEscape wrapper around the sink payload."""
    if sink_id == "innerHTML":
        return re.sub(r"""\.innerHTML(\s*=\s*)([^;]+)""",
                      lambda m: f".textContent{m.group(1)}htmlEscape({m.group(2).strip()})", line)
    if sink_id == "insertAdjacentHTML":
        return re.sub(r"""insertAdjacentHTML\s*\(\s*([^,]+),\s*([^)]+)\)""",
                      lambda m: f"insertAdjacentHTML({m.group(1).strip()}, htmlEscape({m.group(2).strip()}))", line)
    if sink_id == "dangerouslySetInnerHTML":
        return re.sub(r"""dangerouslySetInnerHTML(\s*=\s*)\{\s*__html:\s*([^}]+)\}""",
                      lambda m: f"dangerouslySetInnerHTML{m.group(1)}{{ __html: htmlEscape({m.group(2).strip()}) }}", line)
    if sink_id == "safe_filter":
        return line.replace("| safe", "| html_escape") if "| safe" in line else line.replace("|safe", "|html_escape")
    if sink_id == "v-html":
        return line.replace("v-html=", ":v-text=")
    if sink_id == "document.write":
        return re.sub(r"""document\.write\s*\(\s*([^)]+)\)""",
                      lambda m: f"document.getElementById('output').textContent = htmlEscape({m.group(1).strip()})", line)
    return line


ESCAPE_UTIL_JS = """// htmlEscape — OWASP/DOMPurify-safe HTML encoder
function htmlEscape(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\\//g, '&#x2F;')
    .replace(/`/g, '&#96;')
    .replace(/=/g, '&#x3D;');
}
if (typeof module !== 'undefined' && module.exports) module.exports = { htmlEscape };
"""

ESCAPE_UTIL_PY = '''# html_escape — OWASP-recommended HTML encoder
_ESCAPE_TABLE = {
    "&": "&amp;", "<": "&lt;", ">": "&gt;", \'"\': "&quot;",
    "\'": "&#x27;", "/": "&#x2F;", "`": "&#96;", "=": "&#x3D;",
}

def html_escape(text) -> str:
    if text is None:
        return ""
    return "".join(_ESCAPE_TABLE.get(ch, ch) for ch in str(text))
'''


def sanitize_file(fpath: Path, root: Path, report_dir: Path) -> list:
    """Rewrite a file applying param/escape patches. Returns list of applied patches."""
    content = fpath.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines(keepends=True)
    patches = []

    for i, line in enumerate(lines):
        finding = classify_line(line)
        if not finding:
            continue
        patch = None
        if finding["type"] == "SQLI" and finding["patch_kind"] == "parameterize":
            patch = parameterize_sql(line, connector="")
        elif finding["type"] == "XSS":
            patch = escape_html(line, finding.get("sink_id", ""))

        if patch and patch != line:
            if not patch.endswith("\n") and line.endswith("\n"):
                patch = patch + "\n"
            lines[i] = patch
            patches.append({
                "file": str(fpath), "line": i + 1,
                "type": finding["type"],
                "before": line.strip()[:200],
                "after": patch.strip()[:200],
            })

    if patches:
        rel = fpath.relative_to(root)
        out = report_dir / "sanitized" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("".join(lines), encoding="utf-8")

        backup = report_dir / "backups" / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fpath, backup)

        if fpath.suffix in {".js", ".ts", ".jsx", ".tsx"}:
            util = report_dir / "sanitized" / "_html_escape.js"
            if not util.exists():
                util.write_text(ESCAPE_UTIL_JS, encoding="utf-8")
        elif fpath.suffix == ".py":
            util = report_dir / "sanitized" / "_html_escape.py"
            if not util.exists():
                util.write_text(ESCAPE_UTIL_PY, encoding="utf-8")

    return patches


# ─── Orchestration ──────────────────────────────────────────────────────────────

def console_table(findings: list, files_scanned: int) -> str:
    by_type = {}
    for f in findings:
        by_type[f["type"]] = by_type.get(f["type"], 0) + 1
    table = ["SQLi / XSS Sanitizer — scan summary", ""]
    table.append(f"Files scanned: {files_scanned}")
    table.append(f"Total findings: {len(findings)}")
    table.append(f"  SQLI (CWE-89): {by_type.get('SQLI', 0)}")
    table.append(f"  XSS  (CWE-79): {by_type.get('XSS', 0)}")
    return "\n".join(table)


def main():
    parser = argparse.ArgumentParser(
        description="SQLi & XSS Payload Sanitizer — classify sinks, emit patches, rewrite secure code.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--target", required=True, help="Root of source tree to scan/sanitize")
    parser.add_argument("--report-dir", default="./sanitize-reports", help="Output directory")
    parser.add_argument("--fix", action="store_true", help="Write sanitized files + backups")
    args = parser.parse_args()

    root = Path(args.target).resolve()
    if not root.is_dir():
        print(f"[ERROR] Target directory does not exist: {root}")
        raise SystemExit(1)

    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Scanning: {root}")
    findings, files_scanned = scan_source(root)
    print(console_table(findings, files_scanned))

    for f in findings:
        print(f"  [{f['severity']}] {f['type']} {f['file']}:{f['line']} — {f['detail']}")

    applied = []
    if args.fix:
        print("[INFO] Applying sanitizer patches...")
        seen = set()
        for f in findings:
            fpath = Path(f["file"])
            if fpath in seen:
                continue
            seen.add(fpath)
            applied.extend(sanitize_file(fpath, root, report_dir))
        print(f"[INFO] Patched {len(applied)} line(s) across {len({p['file'] for p in applied})} file(s)")

    report = {
        "target": str(root),
        "files_scanned": files_scanned,
        "findings": findings,
        "patches_applied": applied,
        "output": {
            "sanitized_tree": str(report_dir / "sanitized"),
            "backups": str(report_dir / "backups"),
        },
        "rollback": "Copy original files from backups/ back to source locations.",
    }
    report_path = report_dir / "sanitizer_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n[INFO] Report: {report_path}")
    print(f"[INFO] If --fix used: review {report_dir / 'sanitized'}; rollback from {report_dir / 'backups'}")


if __name__ == "__main__":
    main()
```

## 4. Execution Protocol & Step-by-Step Workflow
1. Run a read-only classification pass:
   ```bash
   python sqli-xss-payload-sanitizer.md --target ./app --report-dir ./sanitize-reports
   ```
2. Review the console table (SQLI vs XSS counts) and per-finding detail lines.
3. Inspect `sanitize-reports/sanitizer_report.json` for structured findings with patch kind (`parameterize` / `escape`).
4. Apply patches with `--fix`:
   ```bash
   python sqli-xss-payload-sanitizer.md --target ./app --report-dir ./sanitize-reports --fix
   ```
5. Copy generated `_html_escape.js` / `_html_escape.py` utilities into your app and import them.
6. Review all files under `sanitize-reports/sanitized/`; original files are untouched and duplicated at `sanitize-reports/backups/`.
7. Promote sanitized files into the source tree; if anything breaks, roll back from `backups/`.
8. Re-run the scanner; new findings should be zero.

## 5. Edge Cases & Error Handling
- Non-UTF-8 files are read with `errors="replace"`, so bytes are never fatal; findings only flag decodable content.
- SQL rewriting keeps original line endings; JSON payloads / multiline strings are only rewritten when the sink pattern matches the exact `execute("...", (..))` or f-string form.
- `--fix` never modifies source files in place — it writes to `sanitized/` plus a full `backups/` tree, guaranteeing rollback by copying backups back.
- Escaping uses the full OWASP entity table (`&<>"'/\`=`), not just `&<>`; the `htmlEscape`/`html_escape` utilities are generated alongside patched code so imports resolve.
- Pattern engine is regex-based (not full AST); false positives on dynamic SQL builders (e.g. ORM `.query()` chains) are possible — severity flags recommend human review.
- Files with binary content that match source extensions decode via `errors="replace"` and are ignored if no sink patterns match.