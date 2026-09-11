---
id: spec-loop-closer
name: Spec Loop Closer
category: core-engine-hardening
tags: ["requirement-closure", "assertion-mapping", "gigo-prevention", "checkable-assertions"]
author: opencode-core
version: 1.0.0
description: Forces every user requirement through a 1:1 mapping to a checkable assertion (grep-able token, executable test, or numeric threshold) before implementation begins. Blocks "done" until each assertion has a machine-runnable check.
---
# Spec Loop Closer

## Prerequisites & Dependencies

- Python 3.10+ (for assertion mapping logic)
- Access to project source files and test directories
- No external runtime dependencies

## Execution Steps

1. **Materialize requirements**: Parse the user's original request/task description and extract each distinct requirement/acceptance criterion.

2. **Map to checkable assertions**: For each requirement, define a machine-verifiable check:
   - **Grep-able token**: A unique string that can be found with `grep` in the implemented code
   - **Executable test**: A pytest/unit test that passes/fails based on the requirement
   - **Numeric threshold**: A specific value that can be computed and compared (e.g., "response time < 200ms")
   - **Enum/constraint check**: A field that must match one of a set of allowed values

3. **Create assertion mapping table**: Produce a structured table listing:
   - Requirement ID (auto-generated or user-assigned)
   - Original requirement text
   - Assertion type (grep/test/threshold/enum)
   - Concrete check expression or test code
   - Status (mapped / pending / blocked)

4. **Block until all mapped**: Implementation must not report "done" until every requirement has a corresponding mapped assertion with a machine-runnable check.

5. **Post-implementation verification**: Run each assertion manually or via automation to confirm all pass before marking the task complete.

## Assertion Mapping Table Example

| ID | Requirement | Type | Check |
|----|-------------|------|-------|
| R1 | "User must be able to reset password via email" | grep | `grep -r "reset.password.email" --include="*.py" .`
| R2 | "API must return 401 for unauthenticated calls" | test | `pytest -k "auth" --tb=short`
| R3 | "Response time < 200ms under load" | threshold | `hey -n 100 -qps 10 https://api.example.com/ping | grep "mean.*200"` |

## Windows PowerShell Notes

- Use `Select-String` instead of `grep` for Windows pattern matching
- Numeric threshold checks should use `[regex]::Match()` for PowerShell parsing
- Assertion mapping table can be saved as `spec-assertions.json` for machine consumption
```