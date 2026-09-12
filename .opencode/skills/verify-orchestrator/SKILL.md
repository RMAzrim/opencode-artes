---
name: Verify Orchestrator
description: Auto-discovers project verification surface (test/lint/typecheck configs), runs the minimal verification suite, and gates every completion claim on machine-parsed exit codes and assertion output. Returns UNVERIFIED rather than silent on discovery failure.
metadata:
  source: skills/verify-orchestrator/verify-orchestrator.md
---

# Verify Orchestrator

## Prerequisites & Dependencies

- Python 3.10+ (or Node.js for config parsing)
- Ability to read `package.json`, `pyproject.toml`, `Makefile`, CI configs (`.github/workflows/*.yml`, `.gitlab-ci.yml`)
- Access to test runner binaries: `pytest`, `ruff`, `tsc`, `eslint`, `npm test`, etc.
- `subprocess` or equivalent for spawning processes and capturing exit codes

## Execution Steps

1. **Discover configuration**: Scan the working directory for verification configs in priority order:
   - `package.json` → check for `test`, `lint`, `typecheck` scripts
   - `pyproject.toml` → check for `pytest`, `ruff`, `mypy` configurations
   - `Makefile` → check for `test`, `lint`, `typecheck` targets
   - `.github/workflows/*.yml` / `.gitlab-ci.yml` → extract test commands
   - `README.md` → check for verification instructions
   - Fallback: `npm test` / `pytest` discovery if no config found

2. **Select minimal verification command**: From discovered configs, choose the smallest, fastest-running command suite that covers the primary validation surface (e.g., `pytest -x --tb=short`, `ruff check --select=E`, `npm run lint`, `tsc --noEmit`).

3. **Execute verification**: Run the selected command in a subprocess with a short timeout (default 60s). Capture:
   - Exit code (`$LASTEXITCODE` on Windows, `process.exitCode` on node)
   - `stdout` and `stderr` for assertion output
   - Any signal termination (TIMEOUT → INDETERMINATE)

4. **Parse and classify result**:
   - Exit code 0 → `VERIFIED`
   - Exit code non-zero with assertion/syntax errors in output → `FAILED`
   - Exit code non-zero, no assertions → `INDETERMINATE` (partial mutation risk)
   - Command not found / discovery failure → `UNVERIFIED`

5. **Gate completion**: A completion claim is only marked `DONE` when verification returns `VERIFIED`. If `UNVERIFIED` or `INDETERMINATE`, the agent must explicitly surface the gap and halt the completion claim rather than proceeding silently.

## Output Format

```json
{
  "status": "VERIFIED|FAILED|INDETERMINATE|UNVERIFIED",
  "exit_code": <number>,
  "output": "<captured stdout+stderr>",
  "verified": <boolean>,
  "note": "<optional human-readable note on INDETERMINATE/UNVERIFIED>"
}
```

## Windows PowerShell Notes

- Use `cmd /c` or PowerShell `&` operator to invoke commands; avoid bare `&&` chaining (unsupported in PS 5.1)
- Always capture `$LASTEXITCODE` after each command, as `$?` reflects the previous command's success, not the current one
- If a timeout kills the process, treat as `INDETERMINATE` and require a manual re-run or targeted check before proceeding
