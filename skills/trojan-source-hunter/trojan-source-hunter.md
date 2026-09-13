---
id: trojan-source-hunter
file_path: skills/trojan-source-hunter/trojan-source-hunter.md
name: Trojan Source Hunter
category: security
tags: [unicode, bidi, trojan-source, cwe-1007, cwe-138, security-scan]
author: opencode-core
version: 1.0.0
description: Scan source files for invisible Unicode/Bidirectional trojan-source characters that silently alter code logic flow without being visible to reviewers.
---

# Trojan Source Hunter

## 1. System Architecture & Prerequisites

Trojan Source (CWE-1007 / CWE-138) abuses Unicode Bidi control characters and
confusable glyphs to make code *read* differently from how it *compiles* — the
invisible `U+202E` etc. can reorder `if`/`return` logic and slip past human
review. This scanner flags such characters plus zero-width and confusable
patterns in every source file. Runtime: Python 3.8+ stdlib only.

Known dangerous codepoints:

- `U+202A..U+202E` — bidi embedding/override (LRM, RLM, LRE, RLE, PDF, LRO, RLO)
- `U+2066..U+2069` — bidi isolates (LRI, RLI, FSI, PDI)
- `U+00AD` soft hyphen, `U+200B` zero-width space, `U+200C/U+200D` ZWJ/ZWNJ,
  `U+2060` word joiner, `U+FEFF` BOM, `U+180E` Mongolian vowel separator
- Homoglyph confusion set, e.g. Cyrillic `а` (U+0430) vs Latin `a` (U+0061)

## 2. Input/Output Data Contracts

Input: a directory (recursively scanned) or a single file. Honors a
`.trojanignore` file with gitignore-ish patterns.

Output: `trojan-audit.json`:

```json
{ "scanned": 120, "files_clean": 118, "findings": [ { "file": "src/auth.ts", "line": 7, "col": 3, "codepoint": "U+202E", "label": "right-to-left override", "preview": "return check(\\u202E...)" } ] }
```

Exit code: `0` = clean, `1` = findings.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""trojan_source_hunter.py — scan a tree for invisible Unicode / bidi tricks."""
import json, os, sys
from pathlib import Path

BIDI = {
    0x202A: "left-to-right embedding (LRE)", 0x202B: "right-to-left embedding (RLE)",
    0x202C: "pop directional formatting (PDF)", 0x202D: "left-to-right override (LRO)",
    0x202E: "right-to-left override (RLO)", 0x2066: "left-to-right isolate (LRI)",
    0x2067: "right-to-left isolate (RLI)", 0x2068: "first strong isolate (FSI)",
    0x2069: "pop directional isolate (PDI)",
}
INVISIBLE = {
    0x00AD: "soft hyphen", 0x200B: "zero-width space", 0x200C: "zero-width non-joiner",
    0x200D: "zero-width joiner", 0x2060: "word joiner", 0xFEFF: "zero-width no-break space",
    0x180E: "mongolian vowel separator", 0x034F: "combining grapheme joiner",
}
# Lowercase homoglyph pairs that are legal code letters but script-shifted.
CONFUSABLES = { 0x0430: (0x0061, "cyrillic small a"), 0x0441: (0x0063, "cyrillic small es"),
                0x0455: (0x0073, "cyrillic small dze"), 0x03BF: (0x006F, "greek omicron"),
                0x0435: (0x0065, "cyrillic small ie") }

def preview(line: str, col: int) -> str:
    lo = max(0, col - 12); hi = min(len(line), col + 12)
    return line[lo:hi].encode("unicode_escape").decode()

def scan_file(path: Path) -> list:
    findings = []
    try:
        data = path.read_bytes()
    except OSError:
        return findings
    # Skip binary files quickly (NUL bytes in first 8KB heuristic).
    if b"\x00" in data[:8192]:
        return findings
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return findings
    for ln, line in enumerate(text.splitlines(), 1):
        for col, ch in enumerate(line):
            cp = ord(ch)
            if cp in BIDI:
                findings.append({"file": str(path), "line": ln, "col": col, "codepoint": hex(cp),
                                 "label": BIDI[cp], "severity": "critical", "preview": preview(line, col)})
            elif cp in INVISIBLE:
                findings.append({"file": str(path), "line": ln, "col": col, "codepoint": hex(cp),
                                 "label": INVISIBLE[cp], "severity": "warning", "preview": preview(line, col)})
            elif cp in CONFUSABLES and ln > 0:
                findings.append({"file": str(path), "line": ln, "col": col, "codepoint": hex(cp),
                                 "label": f"confusable {CONFUSABLES[cp][1]}", "severity": "warning",
                                 "preview": preview(line, col)})
    return findings

def load_ignore(root: Path):
    patterns = []
    gi = root / ".trojanignore"
    if gi.exists():
        patterns = [p for p in gi.read_text().splitlines() if p and not p.startswith("#")]
    return patterns

def main():
    target = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    ignores = load_ignore(target if target.is_dir() else target.parent)
    files = list(target.rglob("*")) if target.is_dir() else [target]
    findings, scanned = [], 0
    for p in files:
        if not p.is_file():
            continue
        if any(p.match(pat) or str(p).startswith(str(target) + os.sep + pat) for pat in ignores):
            continue
        scanned += 1
        findings.extend(scan_file(p))
    report = {"scanned": scanned, "files_clean": scanned - len({f["file"] for f in findings}), "findings": findings}
    out = os.environ.get("TROJAN_OUT", "trojan-audit.json")
    Path(out).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    sys.exit(1 if findings else 0)

if __name__ == "__main__":
    main()
```

## 4. Execution Protocol & Step-by-Step Workflow

1. `python trojan_source_hunter.py .` against the repository root.
2. Review `severity: critical` findings first — any bidi control character in
   code should be treated as a security incident, not a typo.
3. For confusables: confirm whether the identifier is intentional
   internationalized text; in *code identifiers* it is almost always an attack.
4. Fix by deleting invisibles / retyping the identifier linearly, then re-run
   to confirm a clean exit code.
5. Adopt it as a CI gate on PRs (`-F trojan-audit.json` artifact) so the check
   travels with the codebase.

## 5. Edge Cases & Error Handling

- Binary files and files with non-UTF-8 encoding are skipped to avoid false
  positives on images, fonts, and lockfiles.
- `.trojanignore` lets you exempt `node_modules`, vendor trees, and .git.
- Zero-width space (U+200B) is a *warning*, since legitimate usage exists in
  long Japanese/Chinese string literals — but still surface it for review.
- Bidi characters are always `critical`: there is no legitimate need for an RLO
  inside source code.
- The scanner reports column offsets for editor navigation without modifying
  files — remediation stays a human, reviewable edit.