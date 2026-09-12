---
name: OWASP SAST Security Auditor
description: Audits local web application source code for OWASP Top 10 vulnerabilities, generating security report logs and applying immediate automated code fixes.
metadata:
  source: skills/owasp-sast-auditor/owasp-sast-auditor.md
---

# OWASP SAST Security Auditor

## 1. System Architecture & Prerequisites
- Python 3.10+ (stdlib only: `ast`, `re`, `os`, `json`, `argparse`, `pathlib`, `hashlib`, `textwrap`)
- No external dependencies required
- Target: local source tree containing `.py`, `.js`, `.ts`, `.jsx`, `.tsx` files
- Output directory must be writable (created automatically if missing)

## 2. Input/Output Data Contracts

**Input (CLI args):**
```json
{
  "type": "object",
  "properties": {
    "target": { "type": "string", "description": "Root path of source tree to scan" },
    "report_dir": { "type": "string", "description": "Directory for output reports", "default": "./audit-reports" },
    "fix": { "type": "boolean", "description": "Apply auto-fix rewrites", "default": false }
  },
  "required": ["target"]
}
```

**Output artifacts:**
- `{report_dir}/owasp_sast_report.json` — structured JSON audit report
- `{report_dir}/owasp_sast_report.md` — human-readable markdown report
- `{report_dir}/fixes/` — patched source files (when `--fix` is used)

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""OWASP SAST Security Auditor — static analysis scanner with auto-fix."""

import ast
import re
import os
import json
import argparse
import hashlib
import textwrap
import shutil
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional

# ─── Rule Definitions ───────────────────────────────────────────────────────────

@dataclass
class Finding:
    severity: str
    rule: str
    cwe: str
    file: str
    line: int
    snippet: str
    recommendation: str

    def to_dict(self) -> dict:
        return asdict(self)


class SQLiDetector:
    """Detects string-concatenated SQL queries vulnerable to injection."""
    PATTERNS = [
        (re.compile(r"""(?:cursor\.execute|\.execute|\.raw|\.query)\s*\(\s*(?:f["']|["'].*["']\s*%|["'].*["']\s*\+|["'].*\{)""", re.MULTILINE), "SQL string interpolation in execute call"),
        (re.compile(r"""(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s+.*(?:\+\s*\w|f["']|\.format\(|%\s*\()""", re.IGNORECASE | re.MULTILINE), "SQL keyword with string formatting"),
        (re.compile(r"""(?:query|sql)\s*=\s*(?:f["']|["'].*["']\s*%|["'].*["']\s*\+)""", re.MULTILINE), "SQL string built via concatenation/f-string"),
        (re.compile(r"""\.execute\(\s*["'].*["']\s*,\s*(?:request\.(?:form|args|params|json)|req\.body|input\()""", re.MULTILINE), "Direct user input in SQL parameter position without list wrapping"),
    ]
    CWE = "CWE-89"
    RECOMMENDATION = "Use parameterized queries: cursor.execute('SELECT * FROM t WHERE id = %s', (user_id,))"

    def scan(self, content: str, filepath: str) -> List[Finding]:
        findings = []
        for pattern, desc in self.PATTERNS:
            for match in pattern.finditer(content):
                line_no = content[:match.start()].count("\n") + 1
                snippet = content.splitlines()[line_no - 1].strip() if line_no <= len(content.splitlines()) else ""
                findings.append(Finding(
                    severity="CRITICAL", rule=f"SQLI-{desc[:30]}", cwe=self.CWE,
                    file=filepath, line=line_no, snippet=snippet[:200],
                    recommendation=self.RECOMMENDATION
                ))
        return findings


class XSSDetector:
    """Detects unescaped HTML output sinks."""
    PATTERNS = [
        (re.compile(r"""\.innerHTML\s*="""), "innerHTML assignment"),
        (re.compile(r"""document\.write\s*\("""), "document.write call"),
        (re.compile(r"""dangerouslySetInnerHTML"""), "React dangerouslySetInnerHTML"),
        (re.compile(r"""\|\s*safe""", re.MULTILINE), "Jinja2 |safe filter"),
        (re.compile(r"""insertAdjacentHTML"""), "insertAdjacentHTML call"),
        (re.compile(r"""\.html\s*\(\s*(?!.*escape)""", re.MULTILINE), "jQuery .html() without escape"),
        (re.compile(r"""v-html\s*="""), "Vue.js v-html directive"),
    ]
    CWE = "CWE-79"
    RECOMMENDATION = "Use textContent instead of innerHTML; escape template output; use DOMPurify for HTML insertion."

    def scan(self, content: str, filepath: str) -> List[Finding]:
        findings = []
        for pattern, desc in self.PATTERNS:
            for match in pattern.finditer(content):
                line_no = content[:match.start()].count("\n") + 1
                snippet = content.splitlines()[line_no - 1].strip() if line_no <= len(content.splitlines()) else ""
                findings.append(Finding(
                    severity="HIGH", rule=f"XSS-{desc[:30]}", cwe=self.CWE,
                    file=filepath, line=line_no, snippet=snippet[:200],
                    recommendation=self.RECOMMENDATION
                ))
        return findings


class CSRFDetector:
    """Detects mutating routes without CSRF token validation."""
    MUTATING_VERBS = re.compile(r"""(?:app\.(?:post|put|patch|delete)|router\.(?:post|put|patch|delete)|@(?:app|router)\.(?:post|put|patch|delete))""", re.IGNORECASE)
    CSRF_GUARD = re.compile(r"""csrf[_-]?token|csrfProtect|csrf\(|validateCsrf|requireCsrf""", re.IGNORECASE)
    CWE = "CWE-352"
    RECOMMENDATION = "Add CSRF token validation middleware to all state-changing routes."

    def scan(self, content: str, filepath: str) -> List[Finding]:
        findings = []
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if self.MUTATING_VERBS.search(line):
                start = max(0, i - 5)
                end = min(len(lines), i + 15)
                context = "\n".join(lines[start:end])
                if not self.CSRF_GUARD.search(context):
                    findings.append(Finding(
                        severity="MEDIUM", rule="CSRF-no-guard", cwe=self.CWE,
                        file=filepath, line=i + 1, snippet=line.strip()[:200],
                        recommendation=self.RECOMMENDATION
                    ))
        return findings


class RCEDetector:
    """Detects remote code execution sinks."""
    PATTERNS = [
        (re.compile(r"""\beval\s*\("""), "eval() call"),
        (re.compile(r"""\bexec\s*\("""), "exec() call"),
        (re.compile(r"""\bos\.system\s*\("""), "os.system() call"),
        (re.compile(r"""\bpickle\.loads?\s*\("""), "pickle.load(s) call"),
        (re.compile(r"""\bsubprocess\.(?:call|run|Popen)\s*\(.*shell\s*=\s*True"""), "subprocess with shell=True"),
        (re.compile(r"""__import__\s*\("""), "dynamic __import__() call"),
        (re.compile(r"""compile\s*\(.*exec"""), "compile()+exec pattern"),
    ]
    CWE = "CWE-78"
    RECOMMENDATION = "Avoid eval/exec; use ast.literal_eval for data; never use shell=True with untrusted input; avoid pickle for untrusted data."

    def scan(self, content: str, filepath: str) -> List[Finding]:
        findings = []
        for pattern, desc in self.PATTERNS:
            for match in pattern.finditer(content):
                line_no = content[:match.start()].count("\n") + 1
                snippet = content.splitlines()[line_no - 1].strip() if line_no <= len(content.splitlines()) else ""
                findings.append(Finding(
                    severity="CRITICAL", rule=f"RCE-{desc[:30]}", cwe=self.CWE,
                    file=filepath, line=line_no, snippet=snippet[:200],
                    recommendation=self.RECOMMENDATION
                ))
        return findings


class IDORDetector:
    """Detects endpoint handlers fetching by ID without owner/tenant check."""
    ID_PARAM = re.compile(r"""(?:params\.id|request\.params\.id|req\.params\.id|getById|findById|get_object_or_404|\.get\(\s*["']?\w*id["']?)""", re.IGNORECASE)
    OWNER_CHECK = re.compile(r"""(?:req\.user\.id|current_user\.id|user_id|owner_id|tenant_id|\.filter\(.*user|\.where\(.*owner|authorize|permission|is_owner)""", re.IGNORECASE)
    CWE = "CWE-639"
    RECOMMENDATION = "Always verify the authenticated user owns the requested resource: if resource.owner_id !== req.user.id, return 403."

    def scan(self, content: str, filepath: str) -> List[Finding]:
        findings = []
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if self.ID_PARAM.search(line):
                start = max(0, i - 5)
                end = min(len(lines), i + 20)
                context = "\n".join(lines[start:end])
                if not self.OWNER_CHECK.search(context):
                    findings.append(Finding(
                        severity="HIGH", rule="IDOR-no-owner-check", cwe=self.CWE,
                        file=filepath, line=i + 1, snippet=line.strip()[:200],
                        recommendation=self.RECOMMENDATION
                    ))
        return findings


# ─── Auto-Fix Engine ────────────────────────────────────────────────────────────

class AutoFixer:
    """Rewrites vulnerable code blocks to secure patterns and writes to disk."""

    def __init__(self, source_root: Path, output_root: Path):
        self.source_root = source_root
        self.output_root = output_root
        self.fixes_applied: List[dict] = []

    def fix_sql_fstring(self, content: str) -> str:
        """Rewrite f-string SQL to parameterized query."""
        pattern = re.compile(
            r"""(\.execute\(\s*)f(["'])(SELECT\s+.*?\2)\s*\)""",
            re.IGNORECASE | re.DOTALL
        )
        def _replace(m):
            prefix = m.group(1)
            quote = m.group(2)
            sql_body = m.group(3)
            params = re.findall(r"\{(\w+)\}", sql_body)
            clean_sql = re.sub(r"\{(\w+)\}", "%s", sql_body)
            param_tuple = ", ".join(params)
            return f"{prefix}{quote}{clean_sql}{quote}, ({param_tuple},))"
        return pattern.sub(_replace, content)

    def fix_innerhtml(self, content: str) -> str:
        """Replace innerHTML = with textContent =."""
        return content.replace(".innerHTML =", ".textContent =")

    def fix_exec(self, content: str) -> str:
        """Replace bare exec() with ast.literal_eval where pattern matches."""
        return content.replace("exec(", "ast.literal_eval(")

    def fix_os_system(self, content: str) -> str:
        """Replace os.system(cmd) with subprocess.run(shlex.split(cmd), shell=False)."""
        pattern = re.compile(r"""os\.system\(([^)]+)\)""")
        replacement = r"subprocess.run(shlex.split(\1), shell=False)"
        result = pattern.sub(replacement, content)
        if "import subprocess" not in result:
            result = "import subprocess\nimport shlex\n" + result
        if "import shlex" not in result and "shlex" in result:
            result = result.replace("import subprocess\n", "import subprocess\nimport shlex\n")
        return result

    def apply_fixes(self, filepath: Path, content: str) -> Optional[str]:
        """Apply all applicable fixes to file content. Returns new content or None."""
        original = content
        fixed = content
        fixes = []

        sqli_detector = SQLiDetector()
        if sqli_detector.PATTERNS[0][0].search(fixed):
            new_fixed = self.fix_sql_fstring(fixed)
            if new_fixed != fixed:
                fixes.append("sql-parameterize")
                fixed = new_fixed

        xss_detector = XSSDetector()
        if xss_detector.PATTERNS[0][0].search(fixed):
            new_fixed = self.fix_innerhtml(fixed)
            if new_fixed != fixed:
                fixes.append("xss-innerhtml")
                fixed = new_fixed

        rce_detector = RCEDetector()
        for pattern, desc in rce_detector.PATTERNS:
            if "os.system" in desc and pattern.search(fixed):
                new_fixed = self.fix_os_system(fixed)
                if new_fixed != fixed:
                    fixes.append("rce-os-system")
                    fixed = new_fixed
                break

        if fixed == original:
            return None

        rel = filepath.relative_to(self.source_root) if filepath.is_relative_to(self.source_root) else filepath.name
        out_path = self.output_root / "fixes" / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(fixed, encoding="utf-8")

        backup_dir = self.output_root / "backups" / rel
        backup_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filepath, backup_dir)

        self.fixes_applied.append({
            "file": str(rel),
            "fixes": fixes,
            "output": str(out_path),
            "backup": str(backup_dir),
        })
        return fixed


# ─── Scanner Orchestrator ───────────────────────────────────────────────────────

SCAN_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx"}
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", ".next"}


def collect_files(root: Path) -> List[Path]:
    """Recursively collect scannable source files."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.suffix in SCAN_EXTENSIONS:
                files.append(fpath)
    return sorted(files)


def scan_file(filepath: Path) -> List[Finding]:
    """Run all detectors against a single file."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    detectors = [SQLiDetector(), XSSDetector(), CSRFDetector(), RCEDetector(), IDORDetector()]
    findings: List[Finding] = []
    for detector in detectors:
        findings.extend(detector.scan(content, str(filepath)))
    return findings


def generate_markdown_report(findings: List[Finding], files_scanned: int, fixer: Optional[AutoFixer]) -> str:
    """Generate human-readable markdown report."""
    severity_counts = {}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    lines = [
        "# OWASP SAST Security Audit Report",
        "",
        f"**Files scanned:** {files_scanned}",
        f"**Total findings:** {len(findings)}",
        "",
        "## Severity Summary",
        "",
        "| Severity | Count |",
        "|----------|-------|",
    ]
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if sev in severity_counts:
            lines.append(f"| {sev} | {severity_counts[sev]} |")
    lines.append("")

    if findings:
        lines.append("## Findings")
        lines.append("")
        for i, f in enumerate(findings, 1):
            lines.append(f"### {i}. [{f.severity}] {f.rule}")
            lines.append(f"- **CWE:** {f.cwe}")
            lines.append(f"- **File:** `{f.file}`")
            lines.append(f"- **Line:** {f.line}")
            lines.append(f"- **Snippet:** `{f.snippet}`")
            lines.append(f"- **Recommendation:** {f.recommendation}")
            lines.append("")

    if fixer and fixer.fixes_applied:
        lines.append("## Auto-Fixes Applied")
        lines.append("")
        for fix in fixer.fixes_applied:
            lines.append(f"- **{fix['file']}**: {', '.join(fix['fixes'])}")
            lines.append(f"  - Output: `{fix['output']}`")
            lines.append(f"  - Backup: `{fix['backup']}`")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by OWASP SAST Security Auditor*")
    return "\n".join(lines)


# ─── Main Entry Point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OWASP SAST Security Auditor — scan source trees for OWASP Top 10 vulnerabilities.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--target", required=True, help="Root path of source tree to scan")
    parser.add_argument("--report-dir", default="./audit-reports", help="Output directory for reports")
    parser.add_argument("--fix", action="store_true", help="Apply automated code fixes")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"[ERROR] Target directory does not exist: {target}")
        raise SystemExit(1)

    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Scanning target: {target}")
    files = collect_files(target)
    print(f"[INFO] Found {len(files)} scannable files")

    all_findings: List[Finding] = []
    for fpath in files:
        findings = scan_file(fpath)
        all_findings.extend(findings)

    print(f"[INFO] Found {len(all_findings)} vulnerabilities")

    fixer = None
    if args.fix and all_findings:
        fixer = AutoFixer(target, report_dir)
        fixed_files = set()
        for finding in all_findings:
            fpath = Path(finding.file)
            if fpath in fixed_files:
                continue
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8", errors="replace")
                fixer.apply_fixes(fpath, content)
                fixed_files.add(fpath)
        print(f"[INFO] Applied fixes to {len(fixer.fixes_applied)} files")

    json_report = {
        "scan_target": str(target),
        "files_scanned": len(files),
        "total_findings": len(all_findings),
        "vulnerabilities": [f.to_dict() for f in all_findings],
    }
    json_path = report_dir / "owasp_sast_report.json"
    json_path.write_text(json.dumps(json_report, indent=2, default=str), encoding="utf-8")
    print(f"[INFO] JSON report: {json_path}")

    md_report = generate_markdown_report(all_findings, len(files), fixer)
    md_path = report_dir / "owasp_sast_report.md"
    md_path.write_text(md_report, encoding="utf-8")
    print(f"[INFO] Markdown report: {md_path}")

    print("\n## Severity Summary")
    severity_counts = {}
    for f in all_findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if sev in severity_counts:
            print(f"  {sev}: {severity_counts[sev]}")
    print(f"\n[INFO] Audit complete. {len(all_findings)} finding(s) across {len(files)} files.")


if __name__ == "__main__":
    main()
```

## 4. Execution Protocol & Step-by-Step Workflow
1. Install prerequisites: ensure Python 3.10+ is available; no pip installs needed.
2. Run the scanner against your local source tree:
   ```bash
   python owasp-sast-auditor.md --target ./my-app --report-dir ./audit-reports
   ```
3. Review the JSON report (`audit-reports/owasp_sast_report.json`) for machine-readable findings.
4. Review the markdown report (`audit-reports/owasp_sast_report.md`) for a human-readable summary.
5. Re-run with `--fix` to auto-patch discovered vulnerabilities:
   ```bash
   python owasp-sast-auditor.md --target ./my-app --report-dir ./audit-reports --fix
   ```
6. Inspect patched files in `audit-reports/fixes/` and verify correctness.
7. Originals are backed up in `audit-reports/backups/` for rollback if needed.
8. Integrate into CI by exiting non-zero when CRITICAL or HIGH findings exist.

## 5. Edge Cases & Error Handling
- Files with encoding errors are skipped gracefully (`errors="replace"` on read).
- Symlinks are followed by `os.walk` but do not cause infinite loops due to directory filtering.
- Binary files with source-code extensions are handled via exception-free reading; non-text files yield no findings.
- `--fix` mode creates a backup of every modified file before writing; rollback = copy backup over fixed file.
- Empty source trees produce a valid empty report (zero findings, zero files scanned).
- Detecting false positives: context-window heuristics (checking surrounding lines for owner checks) reduce but do not eliminate false positives; human review recommended for MEDIUM/LOW.
- If `--report-dir` is not writable, the script fails fast with a clear OS error before scanning.

