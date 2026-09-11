---
id: schema-sync
name: schema-sync
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: schema-sync
name: Schema Sync
category: core-engine-hardening
tags: [api-schema, integration-drift, schema-diff, toolkit-sync, live-validation]
author: opencode-core
version: 1.5.0
description: Before multi-step toolkit workflows, pings the live tool (via schema-style endpoints / search tools) and diffs against my cached schema; on mismatch, rewrites the workflow plan, never the cached assumptions silently.
---

# Schema Sync

## Prerequisites & Dependencies

- Access to external toolkit APIs (Composio, Canva, ClickHouse, etc.)
- Python 3.10+ (for schema diffing and HTTP requests)
- No external runtime dependencies beyond standard library (urllib, json)

## Execution Steps

1. **Identify workflow**: Determine which multi-step toolkit workflow is about to execute (e.g., "create design from brand template", "generate presentation", "autofill design").

2. **Ping live schema**: Query the live tool for its current schema definition:
   - For Composio: call `COMPOSIO_GET_TOOL_SCHEMAS` with the toolkit slug
   - For Canva: call `canva_get_brand_template_dataset` with the template ID
   - For ClickHouse: query information schema tables
   - Capture the live schema's field names, types, required/optional flags

3. **Diff against cached schema**: Compare the live schema against my internally cached schema (last refreshed at `schema-sync last-run`):
   - **Added fields**: New fields not in my cache → flag as `schema-updated`
   - **Removed fields**: Fields in my cache but not live → flag as `schema-deprecated`
   - **Type changes**: Type mismatches (string→number, etc.) → flag as `schema-broken`
   - **Required flag changes**: Optional→required or vice versa → flag as `schema-breaking`

4. **Rewrite workflow plan on mismatch**: If any diff is detected (added, removed, type change, required-flag change):
   - Halt the current workflow plan
   - Regenerate the workflow using the live schema
   - Surface a diff report to the user showing what changed
   - Update my internal cached schema to the live version

5. **No mismatch → proceed silently**: If diff is empty, proceed with the existing workflow plan without user interruption.

## Schema Diff Report Example

```
Schema Sync Report (Composio GMAIL)
==============================
Last synced: 2026-09-11T09:00:00Z

✅ Added fields (2):
- "reply_body" (string, optional)
- "thread_id" (string, required)

⚠️ Removed fields (1):
- "old_attachment_flag" (string, optional) — deprecated in v2 API

🔧 Type changes (1):
- "priority": was "low|medium|high" (string), now "1-5" (string) — non-breaking

❌ Required flag change:
- "to": was optional, now required — BREAKING; workflow regenerated

Action: Workflow plan regenerated using live schema. Cached schema updated.
```

## Workflow Guard Example

**Before schema-sync**: I'd build a Canva design generation workflow using my cached schema, which might assume certain autofill fields exist. If Canva API changed those fields, my workflow would silently fail at runtime.

**After schema-sync**: Before each Canva workflow, I ping the live dataset schema, diff it, and either auto-update my plan or alert the user to the changes — never proceeding with stale assumptions.

## Windows PowerShell Notes

- API ping via `Invoke-RestMethod` with proper auth headers
- Schema diff comparison: use `Compare-Object` PowerShell cmdlet
- Cached schema stored at `~\.opencode\schema-cache.json` with UTC timestamp
- On mismatch, re-download and overwrite cache automatically