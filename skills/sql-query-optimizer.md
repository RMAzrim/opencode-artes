---
id: sql-query-optimizer
file_path: skills/sql-query-optimizer.md
name: SQL Query Optimizer
category: database
tags: [sql, performance-tuning, indexing, explain-plan, query-rewriting]
author: opencode-core
version: 1.0.0
description: Analyze slow SQL queries, recommend indexes, and restructure join clauses.
---

# SQL Query Optimizer

## Prerequisites & Dependencies
- PostgreSQL 13+ / MySQL 8+ / MariaDB 10.6+ (or SQLite 3.30+) instance with query access
- Client tooling: `psql` or `mysql` CLI; `pg_stat_statements` enabled (recommended) for PostgreSQL workload profiling
- `DATABASE_URL` (or engine-specific credentials) with privileges to run `EXPLAIN` and create indexes on the target schema

## Execution Steps
1. Capture the slow query and its execution context: bind parameter values, call frequency, and current latency from query logs or APM traces.
2. Generate the actual execution plan: `EXPLAIN (ANALYZE, BUFFERS)` on PostgreSQL, `EXPLAIN ANALYZE FORMAT=JSON` on MySQL; save the plan output.
3. Locate the costliest plan nodes: sequential scans on large tables, nested-loop joins over unindexed columns, sorts/hashes spilling to disk, implicit type casts.
4. Propose indexes that match filter (`WHERE`), join (`ON`), and sort (`ORDER BY`) columns; prefer composite indexes with equality columns first and covering (`INCLUDE`) columns for hot read paths.
5. Restructure the query: replace correlated subqueries with `JOIN`/`EXISTS`, push predicates as early as possible, drop `SELECT *`, and pre-aggregate where feasible.
6. Apply recommended indexes in the development environment, re-run `EXPLAIN ANALYZE`, and record before/after timings and buffer hits.
7. Benchmark under production-like data volume, confirm no write-path regressions, then schedule production index creation with `CONCURRENTLY`/online DDL.

```sql
-- Baseline plan
EXPLAIN (ANALYZE, BUFFERS)
SELECT o.id, c.email, SUM(li.qty * li.price) AS total
FROM orders o
JOIN customers c ON c.id = o.customer_id
JOIN line_items li ON li.order_id = o.id
WHERE o.status = 'paid' AND o.created_at >= NOW() - INTERVAL '30 days'
GROUP BY o.id, c.email;

-- Recommended indexes (verify selectivity before applying)
CREATE INDEX CONCURRENTLY idx_orders_status_created
  ON orders (status, created_at DESC);
CREATE INDEX CONCURRENTLY idx_line_items_order
  ON line_items (order_id) INCLUDE (qty, price);

-- Rewrite: filter early, EXISTS instead of IN-subquery
SELECT o.id, c.email
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE o.status = 'paid'
  AND o.created_at >= NOW() - INTERVAL '30 days'
  AND EXISTS (SELECT 1 FROM line_items li WHERE li.order_id = o.id);
```
