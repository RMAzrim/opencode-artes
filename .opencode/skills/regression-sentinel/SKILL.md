---
name: regression-sentinel
description: Before each new task in a long session, re-runs the last N passing checkpoints captured by verify-orchestrator as a smoke suite, catching regressions caused by recent edits before they compound.
metadata:
  source: skills/regression-sentinel/regression-sentinel.md
---

# Regression Sentinel

## Prerequisites & Dependencies

- Python 3.10+ (for checkpoint orchestration)
- Access to verification output from `verify-orchestrator` (exit codes, assertion outputs)
- No external runtime dependencies

## Execution Steps

1. **Capture checkpoints**: After each task completion where `verify-orchestrator` returns `VERIFIED`, persist the verification result as a checkpoint:
   - Task ID or description
   - Verification status (`VERIFIED`)
   - Exit code and output snippet
   - Timestamp

2. **Store checkpoints**: Write checkpoint data to `regression-checkpoints.json` at the repository root:
   ```json
   [
     {"task_id": "task-1", "status": "VERIFIED", "exit_code": 0, "output": "...", "timestamp": "2026-09-11T10:00:00Z"},
     {"task_id": "task-2", "status": "VERIFIED", "exit_code": 0, "output": "...", "timestamp": "2026-09-11T10:30:00Z"}
   ]
   ```

3. **Before each new task**: Read the latest N checkpoints (default N=5) from `regression-checkpoints.json` and execute the same verification commands as smoke tests.

4. **Classify results**:
   - All checkpoints pass → proceed with new task as normal
   - Any checkpoint fails → halt the new task and surface the regression with diff highlighting
   - No checkpoints exist → first task in session; skip smoke suite

5. **Regression report**: On detection, generate a diff report showing:
   - What changed between the last VERIFIED state and current state
   - Which checkpoint(s) failed and why
   - Recommended remediation steps

## Checkpoint Workflow Example

```
Task 1 completes → verify-orchestrator → VERIFIED → save checkpoint
Task 2 begins → regression-sentinel reads 1 checkpoint → runs same test → passes → proceed
Task 3 begins → regression-sentinel reads 2 checkpoints → one fails → halt, show diff
```

## Windows PowerShell Notes

- Checkpoints stored as `regression-checkpoints.json` with UTF8NoBOM encoding
- Smoke test commands extracted from prior `verify-orchestrator` output
- Use `Get-ChildItem` for mtime-based checkpoint pruning (remove older than N days)
