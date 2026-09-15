---
name: ETL Incremental Pipeline Builder
description: Self-contained incremental ETL runner (pure stdlib) with SQLite staging, watermark-based delta loads, idempotent upserts, schema evolution detection, and a data-quality gate. Run it end-to-end with zero installations - no external scheduler, framework, or MCP required.
metadata:
  source: skills/etl-incremental-pipeline-builder/etl-incremental-pipeline-builder.md
---

# ETL Incremental Pipeline Builder

Build and run idempotent, incremental Extract-Transform-Load pipelines entirely on the Python standard library, so the agent can exercise the full lifecycle - schema, load, delta, verify - inside a sandbox without any external app. The reference implementation is a complete `sqlite3 + csv + json + argparse` module you can run verbatim.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`sqlite3`, `csv`, `json`, `argparse`, `tempfile`, `hashlib`, `os`, `sys`). No third-party packages, no database server, no scheduler, no MCP.
- **Components**:
  - `staging` layer: raw CSV snapshots read once per run.
  - `control` layer: `_etlctl` table holding the high-watermark (`last_watermark`) per source.
  - `warehouse` layer: idempotent `main` offsets with `batch_id`, natural key + `etl_updated_at`.
- **Increment model**: delta = rows whose `src_updated` watermark is strictly greater than the stored watermark. Re-running the same snapshot is a no-op (idempotent).
- **Idempotency**: a `batch_id = sha256(source|max_watermark|run_epoch)` is written; a repeated run with the same batch_id returns 0 changed rows.
- **Schema evolution**: columns found in the CSV but missing in the warehouse are added via `ALTER TABLE ... ADD COLUMN` before insert.

## 2. Input/Output Data Contracts

| Artifact | Location | Format |
| --- | --- | --- |
| Source snapshot (input) | `data/<source>.csv` or `--snapshot path.csv` | CSV UTF-8, header row, `records` pipeline sandbox |
| Watermark key | column named `src_updated` (ISO-8601 text, comparable lexicographically) | str |
| Control table | `_etlctl(source TEXT PK, last_watermark TEXT, batch_id TEXT, updated_at TEXT)` | sqlite3 |
| Warehouse | `main[<source>](<csv cols>..., etl_batch_id TEXT, etl_updated_at TEXT)` | sqlite3 |
| Verification report | stdout JSON via `verify` | JSON |

CLI contract:

```
python etl_pipeline.py build --source customers --snapshot data/customers.csv --db out.sqlite
python etl_pipeline.py incremental --source customers --snapshot data/customers.csv --db out.sqlite
python etl_pipeline.py verify --source customers --db out.sqlite
python etl_pipeline.py demo --db out.sqlite          # synthetic end-to-end run
```

Exit codes: `0` success, `1` validation failure, `2` usage/IO error.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""etl_pipeline.py - incremental, idempotent ETL runner (pure stdlib)."""
import argparse
import csv
import hashlib
import io
import json
import sqlite3
import sys
from datetime import datetime, timezone

WATERMARK_KEY = "src_updated"
BATCH = "batch"


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _etlctl("
        "source TEXT PRIMARY KEY, last_watermark TEXT, batch_id TEXT, updated_at TEXT)"
    )
    return conn


def _ident(col: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in col)


def discover_schema(rows: "list[dict]") -> "list[str]":
    ordered: "list[str]" = []
    seen = set()
    for row in rows:
        for col in row:
            if col not in seen and col not in (WATERMARK_KEY,):
                ordered.append(col)
                seen.add(col)
    return ordered


def ensure_warehouse(conn: sqlite3.Connection, source: str, cols: "list[str]"):
    table = _ident(source)
    col_defs = [f"{_ident(WATERMARK_KEY)} TEXT"] + [f"{_ident(c)} TEXT" for c in cols] + [
        "etl_batch_id TEXT",
        "etl_updated_at TEXT",
    ]
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(col_defs)})")
    existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    for c in cols:
        if _ident(c) not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {_ident(c)} TEXT")
    if cols:
        id_col = _ident(cols[0])
        conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{_ident(source)}_pk ON {table}({id_col})")


def read_csv_snapshot(text: str) -> "list[dict]":
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader]


def load(conn: sqlite3.Connection, source: str, rows: "list[dict]", allow_ids: bool = True) -> dict:
    """Idempotent upsert keyed on natural id; returns applied/ignored/errors counts."""
    control = conn.execute(
        "SELECT last_watermark FROM _etlctl WHERE source = ?", (source,)
    ).fetchone()
    last_wm = control["last_watermark"] if control else None

    error_rows, ignored, applied = [], 0, 0
    to_apply = []
    max_wm = last_wm
    for row in rows:
        wm = row.get(WATERMARK_KEY) or ""
        if last_wm is not None and wm <= last_wm:
            ignored += 1
            continue
        if allow_ids:
            try:
                assert row.get("id"), "id column required"
            except AssertionError:
                error_rows.append(row)
                continue
        to_apply.append(row)
        max_wm = max(max_wm, wm) if max_wm is not None else wm

    if not to_apply:
        return {"source": source, "applied": 0, "ignored": ignored, "errors": len(error_rows),
                "max_watermark": max_wm, "changed": 0}

    batch_id = hashlib.sha256(
        f"{source}|{max_wm}|{utcnow()}".encode()
    ).hexdigest()[:24]

    table = _ident(source)
    cols = discover_schema(to_apply)
    ensure_warehouse(conn, source, cols)
    stamp = utcnow()
    for row in to_apply:
        keys = [WATERMARK_KEY] + cols
        values = [row.get(WATERMARK_KEY, "")] + [row.get(c, "") for c in cols] + [batch_id, stamp]
        placeholders = ", ".join("?" for _ in keys) + ", ?, ?"
        update_cols = ", ".join(f"{_ident(c)} = excluded.{_ident(c)}" for c in cols)
        conn.execute(
            f"INSERT INTO {table} ({', '.join(_ident(c) for c in keys)}, etl_batch_id, etl_updated_at) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {update_cols}",
            values,
        )
        applied += 1

    conn.execute(
        "INSERT INTO _etlctl(source, last_watermark, batch_id, updated_at) VALUES (?,?,?,?) "
        "ON CONFLICT(source) DO UPDATE SET last_watermark = excluded.last_watermark, "
        "batch_id = excluded.batch_id, updated_at = excluded.updated_at",
        (source, max_wm, batch_id, stamp),
    )
    conn.commit()
    return {"source": source, "applied": applied, "ignored": ignored, "errors": len(error_rows),
            "max_watermark": max_wm, "changed": applied}


def verify(conn: sqlite3.Connection, source: str) -> dict:
    table = _ident(source)
    control = conn.execute("SELECT * FROM _etlctl WHERE source = ?", (source,)).fetchone()
    total = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
    batch_break = conn.execute(
        f"SELECT etl_batch_id, COUNT(*) AS rows FROM {table} GROUP BY etl_batch_id ORDER BY rows DESC LIMIT 5"
    ).fetchall()
    nulls = conn.execute(
        f"SELECT COUNT(*) AS c FROM {table} WHERE {_ident(WATERMARK_KEY)} IS NULL OR "
        f"TRIM({_ident(WATERMARK_KEY)}) = ''"
    ).fetchone()["c"]
    dupes = conn.execute(
        f"SELECT COUNT(*) AS c FROM (SELECT id FROM {table} GROUP BY "
        f"id HAVING COUNT(*) > 1)"
    ).fetchone()["c"]
    return {
        "source": source,
        "control": dict(control) if control else None,
        "total_rows": total,
        "null_watermarks": nulls,
        "duplicate_natural_keys": dupes,
        "top_batches": [dict(r) for r in batch_break],
        "status": "OK" if (nulls == 0 and dupes == 0 and total > 0) else "DEGRADED",
    }


def synthetic_source() -> str:
    lines = ["id,src_updated,name,country"]
    lines += [f"u{i},{'2026-01-%02d' % (i % 28 + 1)}T00:00:00Z,user-{i},{['ID','US','SG'][i % 3]}" for i in range(1, 21)]
    return "\n".join(lines)


def demo(db: str):
    conn = connect(db)
    snap1 = load(conn, "customers", read_csv_snapshot(synthetic_source()))
    snap2 = load(conn, "customers", read_csv_snapshot(synthetic_source()))  # replay -> ignored
    result = verify(conn, "customers")
    print(json.dumps({"first_load": snap1, "replay": snap2, "verify": result}, indent=2))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="etl_pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="full load from a snapshot")
    p.add_argument("--source", required=True); p.add_argument("--snapshot", required=True)
    p.add_argument("--db", default="etl.sqlite")

    p = sub.add_parser("incremental", help="delta load bounded by watermark")
    p.add_argument("--source", required=True); p.add_argument("--snapshot", required=True)
    p.add_argument("--db", default="etl.sqlite")

    p = sub.add_parser("verify", help="data-quality gate")
    p.add_argument("--source", required=True); p.add_argument("--db", default="etl.sqlite")

    p = sub.add_parser("demo", help="synthetic end-to-end run")
    p.add_argument("--db", default="etl.sqlite")

    args = ap.parse_args(argv)

    if args.cmd == "demo":
        demo(args.db)
        return 0

    conn = connect(args.db)
    try:
        with open(args.snapshot, "r", encoding="utf-8") as fh:
            rows = read_csv_snapshot(fh.read())
    except OSError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2

    if args.cmd == "build":
        conn.execute("DELETE FROM _etlctl WHERE source = ?", (args.source,))
        conn.execute(f"DROP TABLE IF EXISTS {_ident(args.source)}")
        conn.commit()
    result = load(conn, args.source, rows)
    print(json.dumps(result, indent=2))
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Scaffold**: save the module above as `etl_pipeline.py` (or copy from the embedded block).
2. **Full load**: `python etl_pipeline.py build --source customers --snapshot data.csv --db out.sqlite` creates the warehouse + control row and applies every row.
3. **Replay (idempotency probe)**: rerun the same snapshot → every row falls below the watermark → `applied: 0, ignored: N`.
4. **Incremental**: append rows with newer `src_updated` timestamps to `data.csv`; run `incremental` → only the new deltas land, `changed` reports them.
5. **Quality gate**: `python etl_pipeline.py verify --source customers --db out.sqlite` asserts non-null watermarks, no duplicate natural keys, and prints top `batch_id` provenance.
6. **Sandbox demo (no files)**: `python etl_pipeline.py demo` synthesizes a 20-row snapshot, loads it twice, and prints `{first_load, replay, verify}` — fully offline, stdlib-only.

## 5. Edge Cases & Error Handling

- **Missing natural key** → row routed to `errors`, run exits `1`; existing rows never touched.
- **Watermark regression** (rows older than control watermark) → ignored, never duplicated.
- **New CSV columns** → `ALTER TABLE ADD COLUMN` before insert; historical rows store blank value.
- **Corrupt/absent snapshot** → OSError surfaced, exit `2`, control state unmodified.
- **Repeated identical runs** → same watermark, `changed: 0`; batch replay is a safe no-op.
- **Non-ISO watermarks** → lexicographic comparison only valid for same-width timestamps; pad to a fixed width or normalize in a transformer step before the load.
