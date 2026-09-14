# Release Notes v4.0.0 - 25 Must-Have Skills

**Published**: `2026-09-14`

---

## 🚀 What's New

### 🔥 25 Must-Have Skills showcase

v4.0.0 shines a spotlight on the 25 highest-impact skills from the 115-skill catalog — the ones most likely to make a difference on day one of any project, grouped into six practical areas:

**Frontend & UX (5)**
- `/nextjs-app-router-scaffolder` — Production-ready Next.js App Router scaffold with RSC/client separation.
- `/tailwind-responsive-darkmode-styler` — Responsive + dark-mode UI from raw JSX in one step.
- `/form-validation-schema-builder` — Type-safe forms with real-time validation and client-server schema sync.
- `/state-management-query-architect` — Zustand + TanStack Query — UI state vs server state done right.
- `/accessibility-auditor` — WCAG 2.1 audit + automatic ARIA code fixes.

**Backend & API (5)**
- `/express-fastapi-route-builder` — REST API + payload validation + Swagger specs in minutes.
- `/auth-session-oauth2-scaffolder` — Complete login: cookie sessions, JWT rotation, OAuth2 Google/GitHub.
- `/websocket-realtime-secure-engine` — Realtime WS/SSE with auth + reconnection controls.
- `/graphql-schema-dataloader-builder` — GraphQL without N+1 queries via DataLoader batching.
- `/mcp-tools-auto-bridge` — Turn any Python function into an MCP server for AI agent apps.

**Database & Data (4)**
- `/drizzle-prisma-orm-architect` — Schema + relations + zero-downtime migrations (Prisma/Drizzle).
- `/sql-query-optimizer` — Slow queries → index recommendations + join restructuring.
- `/db-migration-generator` — Safe migration scripts (Prisma/TypeORM/Alembic) from model changes.
- `/schema-drift-detector` — Catch silently out-of-sync migrations/ORM/types before queries break.

**DevOps & Cloud (4)**
- `/docker-multi-stage-stack-builder` — Lightweight production Docker images + Compose stack.
- `/github-actions-generator` — CI/CD workflows for test, build, and deploy.
- `/dockerfile-builder` — Efficient, secure, minimal multi-stage Dockerfiles.
- `/k8s-manifest-validator` — Validate Kubernetes YAML against best practices before `kubectl apply`.

**Testing & QA (3)**
- `/unit-test-generator` — Jest/Pytest/Go test suites with complete mocking.
- `/playwright-e2e-security-flow-tester` — E2E browser tests + client-side security boundary enforcement.
- `/lighthouse-web-vitals-optimizer` — Maximize Core Web Vitals scores and optimize bundle delivery.

**Security (4)**
- `/security-suite-orchestrator` ⭐ — **Flagship.** 8-stage audit chain → one consolidated report.
- `/owasp-sast-auditor` — OWASP Top 10 scan + automated code fixes.
- `/dependency-cve-audit-patcher` — Find & patch vulnerable dependencies before release.
- `/secrets-leak-detector` — Prevent API keys and tokens from leaking into git.

Every skill retains the same strict 5-section contract (System Architecture & Prerequisites, Input/Output Data Contracts, Production Reference Implementation, Execution Protocol & Step-by-Step Workflow, Edge Cases & Error Handling) with complete, runnable reference code.

---

## 📱 Where the showcase lives

- **README** — new `🔥 25 Must-Have Skills` section (with nav link), listing all 25 with what-each-does tables.
- **Live catalog** — a `🔥 25 Must-Have Skills` featured banner now sits at the top of the GitHub Pages catalog site, each skill linking straight to its category.

---

## 📖 Upgrade Guide

### For Existing Users

```bash
git pull origin main
npm run build   # regenerates registry.json + .opencode/skills (115 skills)
```

OpenCode loads skills at startup — **restart OpenCode** after pulling so the new catalog state is picked up. No skill IDs, paths, or invocation commands changed in this release; all 115 skills remain loadable via folder-derived slash commands (`/<id>`).

The 17-category taxonomy is unchanged.

---

## 📦 Version Details

- **Version:** `v4.0.0`
- **Release Date:** `2026-09-14`
- **Total Skills:** `115` (across 17 categories)
- **Showcase:** `25 Must-Have Skills`
- **Tag:** `v4.0.0` (annotated Git tag)
- **GitHub Release:** `v4.0.0 - 25 Must-Have Skills`

---

*Generated from `opencode-artes` repository. For questions or issues, please open an issue on the GitHub repository.*