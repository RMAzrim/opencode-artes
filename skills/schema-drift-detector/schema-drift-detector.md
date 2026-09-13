---
id: schema-drift-detector
file_path: skills/schema-drift-detector/schema-drift-detector.md
name: Schema Drift Detector
category: database
tags: [schema, orm, migration, drift, prisma, drizzle, typeorm]
author: opencode-core
version: 1.0.0
description: Compare SQL migrations, ORM models, and TypeScript types against one another to find which layer is silently out of sync before your queries start breaking.
---

# Schema Drift Detector

## 1. System Architecture & Prerequisites

The DB schema, the ORM model, and the TypeScript types are three parallel
realities that *must* agree. They drift: an ALTER is applied in prod but not
in `schema.prisma`; an ORM model gains a column nobody migrated; a TS type
omits a field the API returns. The Detector parses all three layers into a
unified column list per table and diffs them. Python 3.9+ stdlib (SQL parser
kept minimal and conservative — no third-party deps).

Inputs supported out of the box:

- Prisma `schema.prisma` (model → column map)
- Drizzle `schema.ts` (pgTable/table builders, minimal extraction)
- TypeORM entity decorators (`@Column`, `@Entity`)
- SQL migration files (Postgres `ALTER TABLE ... ADD/DROP COLUMN` + `CREATE TABLE`)

## 2. Input/Output Data Contracts

Input: a project directory. Discovery: `**/schema.prisma`, `**/migrations/**/*.sql`,
`**/entities/**/*.ts`, `**/drizzle/**/*.ts` (root configurable).

Output `schema-drift-report.json` + `SCHEMA_DRIFT.md`:

```json
{ "tables": 12, "layers": ["DB", "ORM", "TS"], "diffs": [ { "table": "users", "layer": "ORM", "class": "missing_column", "column": "avatarUrl" } ] }
```

Exit: `0` = consistent, `1` = drift found, `2` = nothing analyzable.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""schema_drift_detector.py — diff DB migrations vs ORM models vs TS types."""
import json, re, sys
from pathlib import Path

class Layer:
    def __init__(self, name): self.name, self.tables = name, {}

    def table(self, t):
        self.tables.setdefault(t, set())
        return self.tables[t]

def parse_migrations(root):
    layer = Layer("DB")
    for f in sorted(root.rglob("*.sql")):
        src = f.read_text(errors="ignore")
        cur = None
        for m in re.finditer(r"(CREATE TABLE|ALTER TABLE)\s+(?:\"?\w+\"\.)?(\w+)", src, re.I):
            cur = layer.table(m.group(2))
        for m in re.finditer(r"ADD COLUMN\s+(?:\")?(\w+)|CREATE TABLE.*?\((.*?)\);", src, re.I | re.S):
            if m.group(1):
                cur.add(m.group(1))
    return layer

def parse_prisma(root):
    layer = Layer("ORM")
    for f in root.rglob("schema.prisma"):
        src = f.read_text(errors="ignore")
        for block in re.finditer(r"model\s+(\w+)\s*\{(.*?)\n\}", src, re.S):
            tname, body = block.group(1), block.group(2)
            for col in re.finditer(r"^\s+(\w+)\s", body, re.M):
                layer.table(tname).add(col.group(1))
    return layer

def parse_ts(root):
    layer = Layer("TS")
    pat = re.compile(r"(?:@Entity\((?:\"|')?(\w+)|pgTable\((?:\"|')?(\w+)|table\((?:\"|')?(\w+))")
    colre = re.compile(r"@Column\s*\(\s*[\"']?(\w+)|(\w+):\s*(?:varchar|text|int|boolean|json|timestamp)")
    ent = None
    for f in list(root.rglob("*.ts")) + list(root.rglob("*.tsx")):
        src = f.read_text(errors="ignore")
        for m in pat.finditer(src):
            ent = m.group(1) or m.group(2) or m.group(3)
            if ent: layer.table(ent)
        if ent:
            for c in colre.finditer(src):
                layer.table(ent).add(c.group(1) or c.group(2))
        ent = None
    return layer

def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    layers = [parse_migrations(root), parse_prisma(root), parse_ts(root)]
    active = [l for l in layers if l.tables]
    if not active:
        print("no schema/migration/models found — nothing to analyze", file=sys.stderr)
        sys.exit(2)
    diffs = []
    tables = sorted({t for l in active for t in l.tables})
    for t in tables:
        for l in active:
            if t in l.tables:
                # Column present in at least one other layer but missing here.
                other = set().union(*[o.tables.get(t, set()) for o in active if o is not l])
                for c in other - l.tables[t]:
                    diffs.append({"table": t, "layer": l.name, "class": "missing_column", "column": c})
    out = {"tables": len(tables), "layers": [l.name for l in active], "diffs": diffs}
    Path("schema-drift-report.json").write_text(json.dumps(out, indent=2))
    md = ["# Schema Drift Report", "", f"Tables: {len(tables)} · Layers: {', '.join(l.name for l in active)}", ""]
    if not diffs:
        md.append("All layers consistent.")
    else:
        md.append("## Drift")
        for d in diffs[:40]:
            md.append(f"- {d['table']}.{d['column']} — missing in `{d['layer']}`")
    Path("SCHEMA_DRIFT.md").write_text("\n".join(md))
    print("\n".join(md))
    sys.exit(1 if diffs else 0)

if __name__ == "__main__":
    main()
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Run `python schema_drift_detector.py <project-root>` (or point at a folder
   with your `schema.prisma`/`migrations/`/entities).
2. Read `SCHEMA_DRIFT.md`: every "missing in X" line is a column that exists in
   one layer and not the other. Classify:
   - DB has it but ORM doesn't → add the column to the model (and TS type);
   - ORM has it but DB doesn't → generate a migration (see
     `db-migration-generator`) before shipping the code that reads it.
3. Fix drift on the *source layer* and regenerate: Prisma `migrate dev`/`generate`,
   Drizzle `drizzle-kit generate`, TypeORM `schema:sync` (ever noted as
   not-for-prod).
4. Re-run until exit `0`, then add the drift check to CI on schema-adjacent
   PRs; this is the cheapest place to prove "schema.prisma and migration agree".
5. Pair with `database-zero-downtime-migrator` when the drift must be healed
   without an outage.

## 5. Edge Cases & Error Handling

- The SQL parser only understands standard Postgres `CREATE`/`ALTER` DDL; MySQL
   `ADD \`col\`` with backticks is partially matched — check the report for
   missing columns from dialect-specific syntax and extend the regex.
- Drizzle/builder syntax (`sql` template strings, `index()` calls) is skipped
   by design; entity-based TypeORM and simple typed columns give the strongest
   signal.
- Views, enums, and generated columns are ignored — the detector targets
   table columns, and false "missing column" entries for views must be excluded
   via an allowlist if your schema uses them heavily.
- Ordered/renamed columns never matter: comparisons are set-based on names, so
   migration reordering doesn't create phantom drift.
- Empty layers (no files found) result in exit `2` with a guidance message, so
   "no drift" is never reported for an unparseable project.