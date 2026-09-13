---
name: Mega Pipeline Deployer
description: Flexible orchestration engine that executes pipeline workflows in Full Mode (all 7 steps sequentially) or Selective Mode (user-specified step subset). Performs data contracting and validation between active steps, skips inactive steps gracefully without breaking the chain, and halts execution with exact error logging when an active step fails.
metadata:
  source: skills/mega-pipeline-deployer/mega-pipeline-deployer.md
---

# Mega Pipeline Deployer

## Prerequisites & Dependencies

- Access to `./skills/` flat directory containing all skill `.md` files
- Access to `./registry.json` at repository root for skill indexing and metadata
- Python 3.10+ runtime for pipeline orchestration logic
- `jq` for JSON parsing and schema validation of inter-step artifacts
- `make` or equivalent for step invocation and dependency tracking

## Execution Steps

The Mega Pipeline Deployer supports two execution modes:

### 1. Full Mode (Default)
Executes all 7 steps sequentially in the following order:
1. **Step 1 - Skill Discovery**: Scan `./registry.json` to index available orchestrator skills and validate prerequisite dependencies.
2. **Step 2 - Workspace Analysis**: Scan the project directory (Node.js, Python, Docker, or mixed stack) to determine runtime environment and available tooling.
3. **Step 3 - Skill Matching**: Automatically select and order skills based on project type detection and user-specified requirements.
4. **Step 4 - Data Contracting**: Between each active step, validate output artifacts against expected schemas. If validation fails, log the discrepancy and halt before proceeding to the next step.
5. **Step 5 - Controlled Execution**: Execute selected skills in order, capturing stdout/stderr, exit codes, and generated artifacts.
6. **Step 6 - Artifact Consolidation**: Merge all generated outputs into a unified readiness report, resolving any naming conflicts or duplicate artifacts.
7. **Step 7 - Final Readiness Summary**: Produce a comprehensive summary including: which skills ran, which passed/failed, validation results, and artifact locations.

### 2. Selective Mode
Executes only user-specified steps while skipping inactive steps gracefully. Usage: `mega-pipeline-deployer --steps "1,3,5"` to run steps 1, 3, and 5 only. Skipped steps are noted in the final report without breaking the chain. Data contracting validation still applies between *active* steps only.

### Data Contracting & Validation
Between any two active steps, the pipeline performs:
- **Schema Validation**: Verify the outgoing artifact from Step N matches the expected input schema for Step N+1
- **Type Checking**: Ensure data types are consistent across step boundaries
- **Conflict Detection**: Flag any naming conflicts, duplicate keys, or schema mismatches
- **Graceful Skip**: If Step N fails (and is marked as inactive/skippable), the pipeline logs the failure and proceeds to Step N+1, documenting the gap in the final report

### Error Halting
If an **active** step fails execution:
1. Capture the exact error message, exit code, and stack trace (if available)
2. Log the failure with full context: step number, skill name, input parameters
3. Immediately halt pipeline execution — subsequent steps are NOT run
4. Generate a partial readiness report documenting all steps completed up to the failure point
5. Return exit code 1 with a structured error payload:
   ```json
   {
     "status": "FAILED",
     "failed_step": <number>,
     "skill": "<skill_name>",
     "error": "<exact_error_message>",
     "artifacts_completed": <list_of_artifacts_generated_before_failure>
   }
   ```

### Output Format
At the conclusion of pipeline execution (success or partial), produces a structured JSON output:
```json
{
  "status": "SUCCESS|PARTIAL|FAILED",
  "mode": "FULL|SELECTIVE",
  "steps_executed": <number>,
  "steps_passed": <number>,
  "steps_failed": <number>,
  "artifacts": [
    {"step": <n>, "name": "<artifact_name>", "path": "<file_path>"}
  ],
  "validation": {
    "inter_step_valid": <boolean>,
    "schema_errors": <list_of_schema_violation_descriptions>
  },
  "summary": "<human_readable_readiness_summary>"
}
```

### Selective Execution Example
```bash
# Run only steps 1, 3, and 5 in selective mode
mega-pipeline-deployer --steps "1,3,5"

# Output will note steps 2, 4, 6, 7 as skipped
# Validation still applies between active steps 1→3 and 3→5
```
