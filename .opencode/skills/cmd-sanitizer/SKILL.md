---
name: cmd-sanitizer
description: "Static linter over command strings before execution. Detects and rewrites unsafe Win32/PowerShell 5.1 patterns: bare && chaining, unquoted spaced paths, $? vs $LASTEXITCODE confusion, UTF-16 pipe corruption, and timeout-kill indeterminacy. Emits sanitized command + guard boilerplate."
metadata:
  source: skills/cmd-sanitizer/cmd-sanitizer.md
---

# Cmd Sanitizer

## Prerequisites & Dependencies

- Python 3.10+ (for regex-based linting and rewriting)
- No external runtime dependencies; pure-Python regex patterns

## Execution Steps

1. **Input**: Provide a raw command string that would be passed to the Windows/PowerShell 5.1 shell.

2. **Pattern detection** (applied in order, first match wins):
   - **A. Bare `&&` chaining**: Detect `cmd1 && cmd2` patterns. Rewrite as `cmd1; if ($?) { cmd2 }` using PowerShell 5.1-compatible `;`-chaining with `$?` guard.
   - **B. `$?` vs `$LASTEXITCODE` confusion**: If the string references `$?` after a native executable invocation, insert `$LASTEXITCODE` capture before the `$?` check and emit a warning.
   - **C. Unquoted paths with spaces**: Detect `cmd "path with spaces"` or `cmd path with spaces` (unquoted). Rewrite with double quotes: `"cmd path with spaces"`.
   - **D. UTF-16 pipe risk**: If the command pipes output to a file or another command via `|`, wrap the pipe target in `[System.Text.Encoding]::UTF8.GetString([System.Text.Encoding]::UTF8.GetBytes($input)]` to force UTF-8 round-trip, or explicitly set `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`.
   - **E. Timeout-kill indeterminacy**: If a `timeout` or `-Timeout` flag is present, emit a mandatory guard: after the timeout fires, re-run the command without timeout or verify post-execution state, and tag the result as `INDETERMINATE` until manual confirmation.

3. **Rewriting / guard insertion**: After pattern detection, produce a sanitized command string that:
   - Replaces bare `&&` with `; if ($?) { ... }`
   - Quotes any unquoted paths containing spaces
   - Prepends `$LASTEXITCODE = & cmd` before any `$?` usage
   - Appends UTF-8 encoding guard for pipe sequences
   - Appends `Indeterminate: true` marker if timeout flags are detected, with a required manual re-confirmation step

4. **Output**: Return a structured object:
   ```json
   {
     "original": "<original command string>",
     "sanitized": "<rewritten command with guards>",
     "warnings": ["<list of detected patterns>"],
     "requires_manual_confirm": <boolean>
   }
   ```

## Windows PowerShell 5.1 Specific Rules

| Pattern | Detection Regex | Rewrite Rule |
|---------|----------------|--------------|
| Bare `&&` chaining | `/&&(?!\s)/g` | Replace with `; if ($?) {` and append `}` |
| `$?` after exec | /\$\?\s*[|>]/g | Prepend `$LASTEXITCODE = & ` before the invoking command |
| Unquoted spaced paths | `(\b\w+\s+\w+)(?!\s*")` (outside already-quoted context) | Wrap matched path in `"` |
| UTF-16 pipe risk | `\|[^|]*\(` | Insert `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` after the pipe |
| Timeout kill tag | `-Timeout\s+\d+` / `timeout\s+\d+` | Set `requires_manual_confirm = true` and append `Indeterminate: true` note |

## Example

**Input**:
```
python build.py && python test.py
```

**Output**:
```json
{
  "original": "python build.py && python test.py",
  "sanitized": "python build.py; if ($?) { python test.py }",
  "warnings": ["Bare && chaining detected - rewritten with $? guard"],
  "requires_manual_confirm": false
}
```

**Input**:
```
node scripts/lint.js | out-file results.txt
```

**Output**:
```json
{
  "original": "node scripts/lint.js | out-file results.txt",
  "sanitized": "node scripts/lint.js | out-file results.txt; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
  "warnings": ["UTF-16 pipe risk detected - UTF-8 encoding guard appended"],
  "requires_manual_confirm": false
}
```

**Input**:
```
timeout 30 python heavy-task.py
```

**Output**:
```json
{
  "original": "timeout 30 python heavy-task.py",
  "sanitized": "timeout 30 python heavy-task.py",
  "warnings": ["Timeout flag detected - result marked INDETERMINATE until manual re-confirmation"],
  "requires_manual_confirm": true
}
```
