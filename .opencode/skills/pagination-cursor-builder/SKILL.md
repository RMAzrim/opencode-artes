---
name: pagination-cursor-builder
description: Build cursor-based and keyset pagination handlers for database queries and API endpoints.
metadata:
  source: skills/pagination-cursor-builder/pagination-cursor-builder.md
---

# Pagination Cursor Builder

## Prerequisites & Dependencies
- SQL database (PostgreSQL, MySQL, SQLite) or NoSQL (MongoDB) with indexed columns
- Language runtime: Node.js 18+, Python 3.10+, or Go 1.21+
- Indexed monotonically increasing column (usually `id` or `created_at`)

## Execution Steps
1. Identify a stable, unique, indexed column for the cursor (prefer auto-increment `id` or `created_at` with UTC timestamp)
2. Design the API endpoint: `GET /items?cursor=last_seen_id&limit=20`
3. In the query, filter with `WHERE id > last_cursor ORDER BY id ASC LIMIT limit` (keyset pagination)
4. Return the first item's cursor to the client for the next page, and a `hasMore` flag when fewer items than `limit` are returned
5. Avoid `OFFSET` for large tables; keyset pagination maintains O(1) performance regardless of page depth
6. Support backward pagination optionally: `WHERE id < last_cursor ORDER BY id DESC LIMIT limit`
7. Validate cursor format, sanitize input, and document the pagination contract for API consumers

```sql
-- Keyset pagination (forward)
SELECT id, title, created_at
FROM articles
WHERE id > 12345   -- cursor = last seen id
ORDER BY id ASC
LIMIT 20;

-- Response: include new cursor = (SELECT MAX(id) FROM returned rows)
```
