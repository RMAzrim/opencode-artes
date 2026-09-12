---
id: output-trust-check
file_path: skills/output-trust-check/output-trust-check.md
name: Output Trust Check
category: core-engine-hardening
tags: [trust-but-verify, truncation, encoding, faithfulness, output-parsing]
author: opencode-core
version: 1.5.0
description: "Wraps every truncating tool call: when output is truncated/byte-capped, refuses to decide on the truncated portion and automatically requests the tail window or a targeted grep. Flags encoding anomalies (UTF-16 NULs, BOMs) as suspect."
---

# Output Trust Check

## Prerequisites & Dependencies

- Python 3.10+ (for output parsing and truncation detection)
- Access to all tool output channels (bash, PowerShell, tool API responses)
- No external runtime dependencies

## Execution Steps

1. **Detect truncation**: After any tool call that returns output, check for these truncation indicators:
   - Bash: `output truncated` message, `$?` non-zero due to SIGPIPE
   - PowerShell: Output wrapped in `...`, `WriteWarning` about buffer size
   - API responses: `truncated` flag, `has_more` = false, partial content returned

2. **Refuse decision on truncated data**: If truncation is detected, immediately:
   - Mark the output segment as `UNTRUSTED`
   - Do not incorporate the truncated portion into any decision, invariant, or completion claim
   - Automatically request the tail window or a targeted follow-up

3. **Request tail or targeted follow-up**: After flagging truncation, one of:
   - Re-run the tool with increased `limit` or `offset` parameters
   - Apply a targeted `grep`/`Select-String` to the source data for the missing portion
   - Request a specific file range or line number range

4. **Flag encoding anomalies**: Inspect output for:
   - UTF-16 BOM (`\xFF\xFE` or `\xFE\xFF`) at start
   - NUL bytes (`\x00`) embedded in text strings
   - Mixed encoding markers (e.g., CP1252 vs UTF-8 sequences)
   - On detection, annotate output with `encoding-suspect: true` and re-parse as UTF-8 after stripping BOM/NUL

5. **Output trust flag**: Return a structured trust metadata object alongside any output:
   ```json
   {
     "output": "<captured text>",
     "trusted": <boolean>,
     "truncated": <boolean>,
     "encoding_suspect": <boolean>,
     "note": "<human-readable explanation if untrusted>"
   }
   ```

## Trust Workflow Example

```
Tool call: rg "pattern" . --max-count 5
Normal output: matches found
→ Trusted: true, Truncated: false

Tool call: head -n 10 large-file.log
Output: first 10 lines, then "output truncated (use -n 50)"
→ Trusted: false, Truncated: true
→ Agent requests: "Please provide the next 10 lines starting at line 11"
```

## Windows PowerShell Notes

- Truncation detection: check `$MaximumOutput` and `Write-Warning` about buffer limits
- Encoding inspection: use `[System.Text.Encoding]::UTF8.GetBytes()` to detect BOM/NUL corruption
- Auto-request pattern: `Get-Content -Path file.txt -Skip N -Tail 10` for tail windows