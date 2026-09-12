---
name: Looping Auto Fixer
description: Iterative fixer that runs unit-test-generator → validates via skill-tester → if tests fail, feeds error logs to memory-leak-debugger or patches code → repeats up to 3 retry iterations → exits on SUCCESS or halts on FAILED_AFTER_MAX_RETRIES.
metadata:
  source: skills/looping-auto-fixer/looping-auto-fixer.md
---

# Looping Auto Fixer

## Prerequisites & Dependencies

- Access to `./skills/unit-test-generator/unit-test-generator.md` for test generation
- Access to `./skills/skill-tester.md` for test validation
- Access to `./skills/memory-leak-debugger/memory-leak-debugger.md` for error log analysis and code patching
- Python 3.10+ runtime for orchestration loop and test orchestration
- `pytest` (or equivalent test framework) for test execution
- `jq` for JSON parsing of test results and error summaries
- Working git environment for diff generation and patch application (optional, for code patching)

## Execution Cycle

### Phase 1: Test Generation & Validation
1. **Run unit-test-generator**: Execute the unit-test-generator skill to produce a comprehensive test suite targeting the current codebase. Capture the generated test file path(s).
2. **Run skill-tester**: Execute `skill-tester` against the generated test suite. This validates the tests compile/run correctly and returns:
   - `pass`: Tests pass immediately
   - `fail`: Tests fail with error summary (captured stdout/stderr)
   - `error`: Infrastructure failure (e.g., test runner not available)
3. **Initial Assessment**:
   - If `pass` → mark cycle complete, exit with success
   - If `fail` → proceed to Phase 2 auto-fix loop
   - If `error` → halt with error log and exit code 1

### Phase 2: Auto-Fix Loop
Maximum of **3 retry iterations** (configurable via `--max-retries 3`):

**Iteration N (1 ≤ N ≤ 3)**:
1. **Feed error logs to memory-leak-debugger**: Pass the test failure error summary (captured stdout/stderr from skill-tester) to the memory-leak-debugger skill. This skill analyzes the errors and suggests:
   - Potential memory leak sources
   - Syntax or runtime errors
   - Missing imports or type mismatches
   - Algorithmic bugs highlighted in the error traces
2. **Generate patch**: Based on memory-leak-debugger output, automatically produce a fix:
   - If the skill has a code-patching sub-routine, apply the patch to the affected source files
   - If patching is not autonomously safe, generate a patch file (`fix.patch`) and apply via `git apply fix.patch`
   - If neither is feasible, surface the suggested fixes to the user for manual application
3. **Re-run skill-tester**: Execute `skill-tester` again against the (possibly patched) codebase and generated tests.
4. **Assess result**:
   - If `pass` → exit loop immediately, mark success, proceed to Phase 3
   - If `fail` → log iteration result, decrement remaining retries, continue to next iteration
   - If `error` → treat as failure, decrement remaining retries, continue

### Phase 3: Exit Conditions
- **SUCCESS**: If any iteration produces `pass` from skill-tester → exit Looping Auto Fixer with exit code 0 and success summary
- **FAILED_AFTER_MAX_RETRIES**: If all 3 iterations complete without `pass` → halt with comprehensive failure report

### Failure Report (on max retries exhausted)
```json
{
  "status": "FAILED_AFTER_MAX_RETRIES",
  "max_iterations": 3,
  "iterations": [
    {"iteration": 1, "skill_tester_result": "fail", "errors": "<captured_errors>"},
    {"iteration": 2, "skill_tester_result": "fail", "errors": "<captured_errors>"},
    {"iteration": 3, "skill_tester_result": "fail", "errors": "<captured_errors>"}
  ],
  "final_error_summary": "<aggregated_all_error_logs>",
  "suggested_next_steps": [
    "Run memory-leak-debugger manually on the error logs",
    "Apply fixes from generated patch files",
    "Review test-generated output from unit-test-generator",
    "Manual code review recommended"
  ]
}
```

### CLI Interface
```
looping-auto-fixer [--max-retries <N>] [--skill-tester-args <args>] [--patch-strategy <auto|manual|hybrid>]
  --max-retries          Maximum retry iterations (default: 3)
  --skill-tester-args    Additional arguments to pass to skill-tester
  --patch-strategy       Fix strategy: auto (apply patches automatically), manual (surface fixes only), hybrid (auto-apply safe fixes, surface risky ones)
```

### Workflow Diagram
```
┌─────────────────────┐
│  Run unit-test-generator  │
└───────┬───────▲───────┘
        │       │
        ▼       │  tests pass?
┌─────────────────────┐
│   Run skill-tester   │── YES ──────► Exit (SUCCESS)
└───────┬───────▼───────┘
        │       │
        │       │  NO
        ▼       │
┌─────────────────────┐
│  Auto-Fix Loop     │── MAX(3) retries ──► FAILED_AFTER_MAX_RETRIES
│  (memory-leak-debugger │
│   → patch → test)    │
└─────────────────────┘
```

### Example Execution
```bash
# Default: 3 retry iterations, auto-patch strategy
looping-auto-fixer

# Output (iteration 1):
[Looping Auto Fixer] Iteration 1/3
[unit-test-generator] Generated 12 test cases
[skill-tester] Running tests...
[skill-tester] Result: 5 failed, 7 passed
[memory-leak-debugger] Analyzing errors...
[looping-auto-fixer] Patch generated: fix.patch (auto-applied)
[looping-auto-fixer] Re-running skill-tester...

# Output (iteration 2):
[Looping Auto Fixer] Iteration 2/3
[skill-tester] Running tests...
[skill-tester] Result: All tests pass! ✅
[looping-auto-fixer] Exit (SUCCESS)
```
