---
id: database-zero-downtime-migrator
file_path: skills/database-zero-downtime-migrator/database-zero-downtime-migrator.md
name: Database Zero-Downtime Migrator
category: database
tags: [database, migrations, zero-downtime, expand-contract, backfill]
author: opencode-core
version: 1.0.0
description: Generates Expand-and-Contract (Parallel Change) migration SQL as four ordered stage files plus a JSON manifest from a MigrationPlan, emitting Postgres or MySQL dialect output through a Python stdlib argparse module.
---

# Database Zero-Downtime Migrator

## 1. System Architecture & Prerequisites

The skill generates a **four-stage Expand-and-Contract (Parallel Change)**
migration for relational schemas so that application code and schema stay
compatible at every step. It is a *SQL emitter* — it never connects to a
database. The agent runs the generated files in order.

Stage pipeline:

1. **Expand** — add new (nullable) columns; nothing breaks, reads still work.
2. **Dual-Write** — a DB trigger (or the app layer) keeps new columns in sync
   with legacy columns on every insert/update.
3. **Backfill** — batch `UPDATE` loops fill historical rows, 1000 rows/chunk.
4. **Contract** — once verification reports zero mismatches and all reads use
   the new columns, drop the legacy columns (reversible only via re-expand).

Prerequisites:

- **Python 3.9+** with the standard library only (`argparse`, `dataclasses`,
  `enum`, `json`, `pathlib`, `datetime`). No external packages.
- **Target database client** to execute emitted SQL:
  - **PostgreSQL 11+** — generated code uses `CREATE OR REPLACE FUNCTION`,
    `EXECUTE FUNCTION`, `ADD COLUMN IF NOT EXISTS`, `DROP COLUMN IF EXISTS`,
    and `DO $$ ... $$` blocks.
  - **MySQL 8.0.19+** — generated code uses `ADD COLUMN IF NOT EXISTS`,
    `DROP COLUMN IF EXISTS`, derived-table subqueries for batched `UPDATE`,
    and `DELIMITER` client directives (must be run through the `mysql`
    client, not an API driver).
- No ORM, no migration framework, no network permissions required.

## 2. Input/Output Data Contracts

### Input: `MigrationPlan` (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MigrationPlan",
  "type": "object",
  "required": ["table", "add_cols", "source_cols", "pk"],
  "properties": {
    "table": { "type": "string", "description": "Physical table name" },
    "add_cols": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "sql_type"],
        "properties": {
          "name": { "type": "string" },
          "sql_type": { "type": "string", "example": "VARCHAR(255)" },
          "nullable": { "type": "boolean", "default": true },
          "default": { "type": ["string", "null"], "default": null },
          "comment": { "type": "string", "default": "" }
        }
      }
    },
    "source_cols": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Legacy columns that feed the new columns"
    },
    "pk": { "type": "string", "example": "id" },
    "dialect": { "enum": ["postgres", "mysql"], "default": "postgres" },
    "batch": { "type": "integer", "minimum": 1, "default": 1000 },
    "description": { "type": "string", "default": "" }
  }
}
```

### Output artifacts

| Path (relative to `--out`, default `migration/`) | Content |
| ------------------------------------------------- | ------- |
| `01_expand.sql`      | `ALTER TABLE ... ADD COLUMN` statements |
| `02_dual_write.sql`  | `CREATE OR REPLACE FUNCTION` + `CREATE TRIGGER` (or MySQL twin triggers) |
| `03_backfill.sql`    | Batched `UPDATE` loop, `batch` rows per chunk |
| `04_contract.sql`    | `ALTER TABLE ... DROP COLUMN IF EXISTS` |
| `05_verify.sql`      | Integration check: queries comparing old vs new columns |
| `manifest.json`      | Serialized plan, stage file map, verify SQL, generation timestamp |

Each `.sql` file is idempotent where the dialect permits (`IF EXISTS` /
`OR REPLACE`) and carries a header comment stating its stage and the
precondition required before it may run.

## 3. Production Reference Implementation

Save as `migrator.py` (module name `migrator`). Fully runnable, importable,
stdlib-only.

```python
#!/usr/bin/env python3
"""Zero-downtime migration SQL generator (Expand-and-Contract / Parallel Change).

Emits four ordered stage files plus a JSON manifest. Never touches the DB.
Usage:
    python migrator.py --plan plan.json --out migration
    python migrator.py --out migration          # demo 'users' plan
"""

from __future__ import annotations

import argparse
import datetime
import enum
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

STAGES = ("expand", "dual_write", "backfill", "contract")


class Dialect(enum.Enum):
    """Identifier quoting + dialect-specific SQL flavors."""

    POSTGRES = "postgres"
    MYSQL = "mysql"

    def quote(self, ident: str) -> str:
        if self is Dialect.MYSQL:
            return "`" + ident.replace("`", "``") + "`"
        return '"' + ident.replace('"', '""') + '"'


@dataclass(frozen=True)
class AddColumn:
    name: str
    sql_type: str
    nullable: bool = True
    default: Optional[str] = None
    comment: str = ""


APP_LAYER_DUAL_WRITE = """\
-- APP-LAYER DUAL-WRITE (alternative to the triggers below; use one or the other)
-- Legacy write path (still fine during Expand):
--   INSERT INTO users (full_name) VALUES (%s);
-- New write path (writes BOTH columns):
--   INSERT INTO users (full_name, display_name) VALUES (%s, %s);
--   UPDATE users SET display_name = full_name WHERE id = %s;
-- The trigger below enforces the same invariant for any code path that has
-- not been upgraded yet, closing the dual-write gap at the database.
"""


@dataclass
class MigrationPlan:
    table: str
    add_cols: List[AddColumn] = field(default_factory=list)
    source_cols: List[str] = field(default_factory=list)
    pk: str = "id"
    dialect: Dialect = Dialect.POSTGRES
    batch: int = 1000
    description: str = ""

    def __post_init__(self) -> None:
        if not self.add_cols:
            raise ValueError("add_cols must contain at least one AddColumn")
        if not self.source_cols:
            raise ValueError("source_cols must name at least one legacy column")

    @property
    def new_cols(self) -> List[str]:
        return [c.name for c in self.add_cols]

    def to_dict(self) -> dict:
        return {
            "table": self.table,
            "add_cols": [asdict(c) for c in self.add_cols],
            "source_cols": list(self.source_cols),
            "pk": self.pk,
            "dialect": self.dialect.value,
            "batch": self.batch,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MigrationPlan":
        col_fields = set(AddColumn.__dataclass_fields__.keys())
        add_cols = [
            AddColumn(**{k: v for k, v in item.items() if k in col_fields})
            for item in data.get("add_cols", [])
        ]
        return cls(
            table=data["table"],
            add_cols=add_cols,
            source_cols=[str(s) for s in data.get("source_cols", [])],
            pk=data.get("pk", "id"),
            dialect=Dialect(data.get("dialect", "postgres")),
            batch=int(data.get("batch", 1000)),
            description=data.get("description", ""),
        )


def _col_pairs(new_cols: List[str], source_cols: List[str]) -> List[tuple]:
    """Pair each new column with the legacy column that feeds it.

    A single source column may feed several new ones (e.g. one raw JSONB
    source driving two typed columns); otherwise pairing is positional.
    """
    if len(source_cols) == 1 and len(new_cols) > 1:
        return [(nc, source_cols[0]) for nc in new_cols]
    if len(new_cols) != len(source_cols):
        raise ValueError(
            f"new/source column count mismatch: {len(new_cols)} vs {len(source_cols)}"
        )
    return list(zip(new_cols, source_cols))


def expand_sql(table: str, add_cols: List[AddColumn],
               dialect: Dialect = Dialect.POSTGRES) -> str:
    q = dialect.quote
    stmts = [
        "-- Stage 1 EXPAND: additive, nullable columns. Safe on live traffic."
    ]
    for c in add_cols:
        parts = [q(c.name), c.sql_type, "NULL" if c.nullable else "NOT NULL"]
        if c.default:
            parts.append("DEFAULT " + c.default)
        sql = "ALTER TABLE {} ADD COLUMN IF NOT EXISTS {};".format(
            q(table), " ".join(parts)
        )
        stmts.append(sql)
        if c.comment:
            stmts.append(
                f"COMMENT ON COLUMN {q(table)}.{q(c.name)} IS '{c.comment}';"
                if dialect is Dialect.POSTGRES
                else f"-- note: {c.comment}"
            )
    return "\n".join(stmts) + "\n"


def dual_write_trigger_sql(table: str, new_cols: List[str],
                           source_cols: List[str],
                           dialect: Dialect = Dialect.POSTGRES) -> str:
    q = dialect.quote
    pairs = _col_pairs(new_cols, source_cols)
    fn_name = f"sync_{table}_new_cols"
    trg_name = f"trg_{table}_dual_write"
    source_list = ", ".join(dict.fromkeys(sc for _, sc in pairs))

    if dialect is Dialect.POSTGRES:
        assignments = "\n".join(
            f"    NEW.{q(nc)} := NEW.{q(sc)};" for nc, sc in pairs
        )
        body = f"""\
-- Stage 2 DUAL-WRITE: trigger keeps new columns mirroring legacy columns.
-- Prerequisite: stage 1 (Expand) already applied.

CREATE OR REPLACE FUNCTION {q(fn_name)}() RETURNS trigger AS $$
BEGIN
{assignments}
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS {q(trg_name)} ON {q(table)};
CREATE TRIGGER {q(trg_name)}
    BEFORE INSERT OR UPDATE OF {source_list} ON {q(table)}
    FOR EACH ROW
    EXECUTE FUNCTION {q(fn_name)}();
"""
        return APP_LAYER_DUAL_WRITE + body

    assignments = "\n".join(f"    SET NEW.{q(nc)} = NEW.{q(sc)};" for nc, sc in pairs)
    body = f"""\
-- Stage 2 DUAL-WRITE: twin BEFORE triggers (MySQL has no column list on UPDATE).
-- Prerequisite: stage 1 (Expand) already applied.

DELIMITER $$

CREATE TRIGGER {q(trg_name + "_insert")}
BEFORE INSERT ON {q(table)}
FOR EACH ROW
BEGIN
{assignments}
END$$

CREATE TRIGGER {q(trg_name + "_update")}
BEFORE UPDATE ON {q(table)}
FOR EACH ROW
BEGIN
{assignments}
END$$

DELIMITER ;
"""
    return APP_LAYER_DUAL_WRITE + body


def backfill_sql(table: str, new_cols: List[str], pk: str, batch: int = 1000,
                 source_cols: Optional[List[str]] = None,
                 dialect: Dialect = Dialect.POSTGRES) -> str:
    if source_cols is None:
        source_cols = new_cols
    if batch < 1:
        raise ValueError("batch must be >= 1")
    q = dialect.quote
    t, p = q(table), q(pk)
    assign = ", ".join(f"{q(nc)} = {q(sc)}" for nc, sc in _col_pairs(new_cols, source_cols))
    null_clause = " AND ".join(f"{q(c)} IS NULL" for c in new_cols)

    if dialect is Dialect.POSTGRES:
        return f"""\
-- Stage 3 BACKFILL: fill historical rows in {batch}-row chunks until done.
-- Prerequisite: stage 2 (Dual-Write) already applied.
-- Idempotent: rows where the new column is already set are skipped.

DO $$
DECLARE
    _rows INT;
BEGIN
    LOOP
        UPDATE {t}
        SET {assign}
        WHERE {p} IN (
            SELECT {p}
            FROM (
                SELECT {p}
                FROM {t}
                WHERE {null_clause}
                ORDER BY {p}
                LIMIT {batch}
            ) AS _batch
        );
        GET DIAGNOSTICS _rows = ROW_COUNT;
        EXIT WHEN _rows = 0;
    END LOOP;
END $$;
"""

    return f"""\
-- Stage 3 BACKFILL: REPEAT-loop stored procedure, {batch} rows per chunk.
-- Prerequisite: stage 2 (Dual-Write) already applied.
-- NOTE: DELIMITER is a mysql-client directive; run this file through the
-- 'mysql' client, not through an API driver.

DELIMITER $$

DROP PROCEDURE IF EXISTS backfill_{table} $$

CREATE PROCEDURE backfill_{table}()
BEGIN
    REPEAT
        UPDATE {t}
        SET {assign}
        WHERE {p} IN (
            SELECT {p}
            FROM (
                SELECT {p}
                FROM {t}
                WHERE {null_clause}
                ORDER BY {p}
                LIMIT {batch}
            ) AS _batch
        );
    UNTIL ROW_COUNT() = 0 END REPEAT;
END $$

DELIMITER ;

CALL backfill_{table}();
DROP PROCEDURE backfill_{table};
"""


def contract_sql(table: str, legacy_cols: List[str],
                 dialect: Dialect = Dialect.POSTGRES) -> str:
    q = dialect.quote
    drops = "\n".join(
        f"ALTER TABLE {q(table)} DROP COLUMN IF EXISTS {q(c)};" for c in legacy_cols
    )
    return f"""\
-- Stage 4 CONTRACT: drop legacy columns.
-- PRECONDITION: 05_verify.sql returned 0 mismatches AND application reads
-- have been switched to the new columns. IRREVERSIBLE without re-running
-- the Expand stage, so gate it behind the verify query.

{drops}
"""


def integration_check_sql(table: str, new_cols: List[str],
                          legacy_cols: List[str],
                          dialect: Dialect = Dialect.POSTGRES) -> str:
    q = dialect.quote
    conditions = []
    for nc, sc in _col_pairs(new_cols, legacy_cols):
        if dialect is Dialect.POSTGRES:
            conditions.append(
                f"(COALESCE({q(nc)}::text, '') <> COALESCE({q(sc)}::text, ''))"
            )
        else:
            conditions.append(
                f"(COALESCE({q(nc)}, '') <> COALESCE({q(sc)}, ''))"
            )
        conditions.append(f"({q(nc)} IS NULL AND {q(sc)} IS NOT NULL)")
    where = "\n    OR ".join(conditions)
    return f"""\
-- Integration check: 0 rows means old and new views agree, backfill is whole,
-- and the Contract stage may run after reads switch to new columns.

SELECT COUNT(*) AS mismatches
FROM {q(table)}
WHERE {where};
"""


def plan_to_sql(plan: MigrationPlan) -> Dict[str, List[str]]:
    """Render a whole plan to ordered SQL stages.

    Returns {"expand": [...], "dual_write": [...], "backfill": [...],
    "contract": [...]}, plus "integration_check" for the verify file.
    """
    legacy = plan.source_cols
    new = plan.new_cols
    if not legacy or not new:
        raise ValueError("MigrationPlan needs both add_cols and source_cols")
    return {
        "expand": [expand_sql(plan.table, plan.add_cols, plan.dialect)],
        "dual_write": [dual_write_trigger_sql(plan.table, new, legacy, plan.dialect)],
        "backfill": [
            backfill_sql(plan.table, new, plan.pk, plan.batch, legacy, plan.dialect)
        ],
        "contract": [contract_sql(plan.table, legacy, plan.dialect)],
        "integration_check": [
            integration_check_sql(plan.table, new, legacy, plan.dialect)
        ],
    }


def _stage_header(stage: str, plan: MigrationPlan) -> str:
    return (
        f"-- ==============================================\n"
        f"-- Stage: {stage} | table: {plan.table} | dialect: {plan.dialect.value}\n"
        f"-- Generated by database-zero-downtime-migrator\n"
        f"-- ==============================================\n"
    )


def _demo_plan() -> MigrationPlan:
    return MigrationPlan(
        table="users",
        add_cols=[
            AddColumn(
                name="display_name",
                sql_type="VARCHAR(255)",
                nullable=True,
                comment="mirror of full_name to be read by the new path",
            )
        ],
        source_cols=["full_name"],
        pk="id",
        dialect=Dialect.POSTGRES,
        batch=1000,
        description="demo: split full_name into display_name",
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="migrator",
        description="Generate Expand-and-Contract zero-downtime migration SQL.",
    )
    parser.add_argument(
        "--plan", metavar="JSON_FILE",
        help="MigrationPlan JSON; omit to use the built-in demo plan",
    )
    parser.add_argument(
        "--out", default="migration",
        help="output directory (default: migration)",
    )
    args = parser.parse_args(argv)

    if args.plan:
        with open(args.plan, encoding="utf-8") as fh:
            plan = MigrationPlan.from_dict(json.load(fh))
    else:
        plan = _demo_plan()

    sql = plan_to_sql(plan)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    stage_files: Dict[str, Path] = {}
    for i, stage in enumerate(STAGES, start=1):
        path = out / f"{i:02d}_{stage}.sql"
        content = _stage_header(stage, plan) + "".join(sql[stage]) + "\n"
        path.write_text(content, encoding="utf-8")
        stage_files[stage] = path

    verify_path = out / "05_verify.sql"
    verify_path.write_text(
        _stage_header("verify", plan) + "".join(sql["integration_check"]),
        encoding="utf-8",
    )

    manifest = {
        "skill": "database-zero-downtime-migrator",
        "version": "1.0.0",
        "stages": list(STAGES),
        "stage_files": {k: p.name for k, p in stage_files.items()},
        "verify_file": verify_path.name,
        "verify_sql": "".join(sql["integration_check"]).strip(),
        "plan": plan.to_dict(),
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "run_order": (
            "1) 01_expand.sql   2) 02_dual_write.sql   3) 03_backfill.sql   "
            "4) 05_verify.sql until 0 mismatches -> switch reads to new cols "
            "-> 5) 04_contract.sql"
        ),
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )

    print(f"Wrote {len(stage_files) + 2} artifacts to {out}")
    for stage, path in stage_files.items():
        print(f"  - {path.name} ({stage})")
    print(f"  - {verify_path.name} (verify)")
    print(f"  - manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Importable API summary:

```python
from migrator import (
    AddColumn,
    Dialect,
    MigrationPlan,
    expand_sql,
    plan_to_sql,
    backfill_sql,
    dual_write_trigger_sql,
    contract_sql,
    integration_check_sql,
)

plan = MigrationPlan(
    table="users",
    add_cols=[AddColumn(name="display_name", sql_type="VARCHAR(255)")],
    source_cols=["full_name"],
    pk="id",
    dialect=Dialect.POSTGRES,
)
sql_by_stage = plan_to_sql(plan)  # -> dict[str, list[str]] over the 4 stages + integration_check
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Survey the schema.** Read the live DDL and identify the legacy
   column(s) to split/move and the exact data type the new column needs.
2. **Author the plan.** Either write a `MigrationPlan` JSON file or use the
   demo plan. Keep `add_cols` **nullable** during expansion — a NOT NULL
   column cannot be added without a default on a live, large table.
3. **Generate.** Run `python migrator.py --plan plan.json --out migration`
   (or write your own `main` via `plan_to_sql`). Inspect the manifest for
   dialect, batch size, and run order.
4. **Expand.** Apply `01_expand.sql`. Confirm `\d <table>` (psql) or
   `SHOW CREATE TABLE <table>` shows the new column as NULL.
5. **Dual-Write.** Apply `02_dual_write.sql`. If your app layer already
   writes both columns, skip the triggers and keep only the app path — never
   run both without ensuring they agree.
6. **Backfill.** Apply `03_backfill.sql`. Watch for long locks on huge
   tables; in that case lower `batch` and schedule off-peak.
7. **Verify.** Run `05_verify.sql` repeatedly. It must return `0` before any
   Contraction. If mismatches persist, fix the trigger/app dual-write first.
8. **Cut over reads.** Deploy app code reading only the new columns; the
   legacy columns are now write-orphaned.
9. **Contract.** After observing a full read+write cycle (recommend ≥ one
   release), apply `04_contract.sql`. Update the manifest to mark the skill
   complete.

## 5. Edge Cases & Error Handling

- **Trigger syntax errors on MySQL** — MySQL has no `UPDATE OF <col>` clause
  and no `DO` blocks; the generated twin triggers and `DELIMITER` procedure
  are the only portable path. Always run MySQL scripts through the `mysql`
  client so `DELIMITER` is honored.
- **Pre-existing non-NULL data** — the backfill loop skips rows where the new
  column is already set. If rows were pre-populated with the *wrong* values,
  the verify query surfaces them (`<>` comparison) instead of overwriting.
- **MySQL 5.7 lacks `IF EXISTS`** — fall back to plain `ADD COLUMN` /
  `DROP COLUMN` and tolerate transient errors; or document a manual check.
- **Locking/long-running backfill** — keep `batch` modest (default 1000),
  rely on `ORDER BY pk LIMIT` so each chunk is index-driven, and run during a
  low-traffic window. On Postgres, prefer smaller batches over `LOCK TABLE`.
- **`COMMIT` inside PL/pgSQL** — cannot be issued inside a `DO` block; the
  generated code leaves per-statement autocommit, which is correct here.
- **Count mismatch between new/source columns** — `_col_pairs` raises a clear
  `ValueError` before any file is written; re-check the plan JSON.
- **Reserved words / mixed-case identifiers** — all identifiers are quoted
  per dialect (backtick vs double-quote), so reserved names survive.
- **Rollback after Contract** — dropping is irreversible without re-running
  Expand. Gate `04_contract.sql` behind the verify query and a tagged backup
  (`pg_dump -t <table>` on Postgres, `mysqldump` on MySQL).
- **Stage ordering mistakes** — the manifest's `run_order` is the agent's
  checklist; if `03_backfill.sql` runs before the trigger, new writes made
  between stage 2 and 3 are already mirrored, but anything written between
  stage 1 and 2 is caught by the verify query (`05_verify.sql` shows the
  exact drift) and corrected by a backfill re-run. If a stage fails, fix and
  re-run the failed file — every generator emits idempotent statements
  (`IF EXISTS`, `OR REPLACE`).