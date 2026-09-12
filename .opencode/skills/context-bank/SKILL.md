---
name: Context Bank
description: Materializes a structured CONTEXT_BANK.md + JSON file that captures verified file paths, decided invariants, active TODOs, and open risks, allowing subagents and repeated sessions to reload a lean current snapshot instead of decaying transcript memory.
metadata:
  source: skills/context-bank/context-bank.md
---

# Context Bank

## Prerequisites & Dependencies

- Python 3.10+ (for JSON/Markdown materialization)
- No external runtime dependencies; pure-Python file I/O

## Execution Steps

1. **Scan transcript ground truth**: Before any major edit or session pause, extract the following from the current conversation:
   - Verified file paths (absolute, with `file:line` references confirmed)
   - Decided invariants (design decisions, rejected approaches with rationale)
   - Active TODOs and their status
   - Open risks or indeterminate states

2. **Write CONTEXT_BANK.md**: Create/overwrite `CONTEXT_BANK.md` at the repository root with structured sections:
   - `# Verified File Paths`
   - `# Decided Invariants`
   - `# Active TODOs`
   - `# Open Risks`
   - `# Session Decisions`

3. **Write context-bank.json**: Serialize the same data to `context-bank.json` for machine consumption by subagents.

4. **On reload**: Prioritize `CONTEXT_BANK.md` contents over the decaying transcript when resuming work. Flag any transcript references that conflict with the bank as potentially stale.

5. **Periodic compaction**: Run `context-bank compact` to collapse older entries (older than N turns) while preserving decision rationale and file:line anchors.

## Output Format

`CONTEXT_BANK.md`:
```markdown
# Context Bank (auto-generated)

## Verified File Paths
- `path/to/file.py:42` — verified import pattern
- `path/to/other.ts:11` — confirmed type contract

## Decided Invariants
- **Decision**: Use X over Y
- **Rationale**: Y caused [specific failure] in prior session
- **Rejected**: [any alternative considered]

## Active TODOs
- [ ] TODO description — owner, due

## Open Risks
- Risk: X may break under Y conditions
- Status: being investigated

## Session Decisions
- 2026-09-11: Agreed to use verify-orchestrator for all completion claims
```

`context-bank.json`:
```json
{
  "verified_paths": ["path/to/file.py:42"],
  "invariants": {"decision": "Use X over Y", "rationale": "Y caused failure"},
  "todos": [{"text": "TODO description", "owner": "agent", "status": "open"}],
  "risks": [{"description": "Risk: X may break under Y", "status": "open"}],
  "decisions": ["2026-09-11: Agreed to use verify-orchestrator"]
}
```

## Windows PowerShell Notes

- Use `Set-Content` with `-Encoding UTF8NoBOM` when writing `CONTEXT_BANK.md` to avoid BOM contamination
- Verify file paths use forward slashes or escaped backslashes in PowerShell quotes
