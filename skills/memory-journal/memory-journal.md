---
id: memory-journal
file_path: skills/memory-journal/memory-journal.md
name: Memory Journal
category: core-engine-hardening
tags: [cross-session-memory, decision-log, session-diff, persistent-state, rationale-preservation]
author: opencode-core
version: 1.5.0
description: "Cross-session ledger at `~/.opencode/memory/*.md`: appends decisions/rejections/root-causes during a session; on session start, diffs against the live transcript so the agent stops re-litigating settled decisions."
---

# Memory Journal

## Prerequisites & Dependencies

- Python 3.10+ (for journal file I/O and diff logic)
- Access to `~/.opencode/memory/` directory (created on first use)
- No external runtime dependencies

## Execution Steps

1. **Initialize journal directory**: On first use, create `~/.opencode/memory/` if it doesn't exist.

2. **Append during session**: After each significant decision (adopted approach, rejected alternative, root cause identified), append a journal entry to `~/.opencode/memory/decisions.md`:
   ```markdown
   ## Decision: YYYY-MM-DD HH:MM - [tag]
   
   **Chose**: X over Y
   
   **Rationale**: Z caused prior failure
   
   **Rejected**: Y (considered but decided against)
   
   **Session**: current-session-id
   ```

3. **Session start diff**: On session initialization, run `memory-journal diff` to compare journal entries against the live transcript:
   - Surface any decisions already recorded in the journal that the current transcript is re-litigating
   - Flag any transcript references that conflict with journal entries as potentially stale
   - Output a "settled decisions" summary for the agent's awareness

4. **Cross-session reference**: Before making a decision with prior-art impact, query `~/.opencode/memory/decisions.md` for relevant tags or timestamps to avoid contradicting prior rationale.

5. **Periodic consolidation**: Run `memory-journal compact` to merge adjacent entries with identical tags, remove entries older than N months, and preserve the most recent rationale per decision topic.

## Journal Entry Example

```markdown
## Decision: 2026-09-11 14:32 - [verification]

**Chose**: verify-orchestrator for all completion claims

**Rationale**: Silent "done" without evidence is the highest-cost failure mode (audit finding E)

**Rejected**: Proceeding on absence of counterevidence

**Session**: opencode-session-2026-09-11
```

## Windows PowerShell Notes

- Journal directory: `$env:HOMEPATH\.opencode\memory`
- Use `Set-Content -Path ... -Encoding UTF8` when writing entries (`UTF8NoBOM` is PowerShell 7+ only; PS 5.1 writes a BOM otherwise)
- Diff command: `diff -u <(grep -i "decision" transcript.md) <(cat ~/.opencode/memory/decisions.md)`