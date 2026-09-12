---
name: db-migration-generator
description: Generate database schema migration scripts (Prisma/TypeORM/Alembic) based on model changes.
metadata:
  source: skills/db-migration-generator/db-migration-generator.md
---

# DB Migration Generator

## Prerequisites & Dependencies
- Node.js 18+ with `prisma` or `typeorm`, or Python 3.10+ with `alembic`, matching the project ORM
- Existing ORM setup: `schema.prisma`, TypeORM `DataSource` config, or `alembic.ini` plus `env.py`
- `DATABASE_URL` pointing to a dev database that mirrors the current production schema

## Execution Steps
1. Sync the dev database to the last applied migration so the diff is computed against the true current state.
2. Apply model changes (edit `schema.prisma`, TypeORM entities, or SQLAlchemy models).
3. Auto-generate a descriptively named migration using the ORM diff engine (e.g., `add_user_email_index`).
4. Read the generated SQL before applying: flag destructive operations (column drops, type changes, table locks on large tables) for manual review.
5. Apply the migration to the dev database and verify the resulting schema (`prisma db pull`, `alembic current`, or information_schema inspection).
6. Test the rollback path (`alembic downgrade -1`, TypeORM `migration:revert`) and document any irreversible steps for ops sign-off.

```bash
# Prisma
npx prisma migrate dev --name add_user_email_index
npx prisma migrate status

# TypeORM
npx typeorm migration:generate -d src/data-source.ts src/migrations/AddUserEmailIndex
npx typeorm migration:run -d src/data-source.ts

# Alembic
alembic revision --autogenerate -m "add user email index"
alembic upgrade head
alembic downgrade -1
```

