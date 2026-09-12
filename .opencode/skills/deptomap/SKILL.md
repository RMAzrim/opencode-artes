---
name: deptomap
description: Builds a persistent dependency graph (`dep-graph.json`) by scanning `import`/`require`/`include` patterns across the codebase. Before any edit it lists the blast radius of consumers for the target symbol; after the edit it re-verifies no orphaned references exist.
metadata:
  source: skills/deptomap/deptomap.md
---

# Dep Map

## Prerequisites & Dependencies

- Python 3.10+ (for AST/scanning logic)
- Language-specific parsers optional; regex-based scanning sufficient for JS/TS/Python
- No external runtime dependencies

## Execution Steps

1. **Scan import patterns**: Detect `import`, `require`, `include`, or language-specific import syntax across all project files. Build a mapping of `symbol → [list of files consuming it]`.

2. **Write dep-graph.json**: Output a JSON structure:
   ```json
   {
     "symbols": {
       "moduleName": {
         "imports": ["dep1", "dep2"],
        "consumers": ["file1.py", "file2.ts"]
       }
     }
   }
   ```

3. **Before any edit**: Re-scan consumers of the symbol being modified. Emit a "blast radius" report listing every file that imports/requires/references the target. Ask for explicit confirmation if the blast radius exceeds a safe threshold (configurable, default 5 files).

4. **After any edit**: Re-scan the modified file and its downstream consumers. Check for:
   - Orphaned imports (symbol removed but still imported)
   - Broken reference chains
   - Stale type annotations

5. **Incremental mode**: Only re-scan files modified since last run, using file mtime comparison.

## Blast Radius Report Example

```
Symbol: utils.format
Consumers (3 files):
- src/presentation/user-profile.tsx:12
- src/logging/app.logger.ts:5
- scripts/deprecated/old-format.js:1 (deprecated path)

⚠️ Edit will affect 3 consumers. Proceed?
```

## Output Format

`dep-graph.json`:
```json
{
  "symbols": {
    "utils.format": {
      "imports": ["core.types", "db.models"],
      "consumers": ["api/routes.ts", "services/auth.service.ts"]
    }
  }
}
```

## Windows PowerShell Notes

- Use `python -m dep_map` to invoke the scanner from the skills directory
- File paths with spaces must be quoted with `"..."` in PowerShell
- Incremental scans use `for %f in (%file) do` style mtime comparison
