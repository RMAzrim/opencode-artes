---
id: subagent-evidence
name: Subagent Evidence
category: core-engine-hardening
tags: [subagent-compression, evidence-citation, inference-tagging, citation-verification, lossy-audit]
author: opencode-core
version: 1.5.0
description: Dispatch-time contract for explore agents: return only observations each with a `file:line` citation and raw excerpt; inference must be explicitly tagged `[INFERRED]`. Post-dispatch, I sample-cite — verify ≥2 citations per summary myself before trusting conclusions.
---

# Subagent Evidence

## Prerequisites & Dependencies

- Access to explore agent dispatch workflow
- Power to post-process agent summaries before acceptance
- No external runtime dependencies

## Dispatch-Time Contract

When dispatching an explore agent, enforce the following contract:

1. **Observation-only return**: The agent returns raw observations, never inferred conclusions.

2. **Each observation must include**:
   - `file:line` citation — exact file path and line number where the observation originates
   - `excerpt` — the raw text snippet (1-3 sentences) from that location
   - `tag` — one of: `[OBSERVED]`, `[INFERRED]`, `[HEURISTIC]`

3. **Inference tagging requirement**: Any conclusion drawn by the agent must be explicitly tagged `[INFERRED]` and accompanied by at least 2 supporting observations with `file:line` citations.

4. **No bare claims**: Statements without `file:line` citations are rejected at dispatch time.

## Post-Dispatch Verification

After receiving an agent summary:

1. **Sample-cite**: For each substantive claim in the summary, locate and verify at least 2 `file:line` citations from the original observations.

2. **Flag unsupported conclusions**: Claims with fewer than 2 verified citations are marked `[UNVERIFIED]` in the chat.

3. **Reject inference without evidence**: Any `[INFERRED]` claim without 2 supporting observations is discarded and re-reported to the user.

## Verification Workflow Example

```
Agent summary: "The codebase uses Factory pattern extensively"
→ I verify: 2+ citations showing Factory pattern usage
→ Result: Claim accepted with [VERIFIED] tag

Agent summary: "Component X is unused"
→ I check: only 1 citation found for "unused"
→ Result: Claim marked [UNVERIFIED], re-reported to user
```

## Windows PowerShell Notes

- Citation format: `C:\path\to\file.py:42` or relative paths as appropriate
- Excerpt extraction: use `sed -n '42p' "C:\path\to\file.py"` to pull exact line
- Tag markup: wrap inferences in `[INFERRED]` brackets explicitly in the summary text