# Release Notes v3.5.0 - 18 Production-Grade Skills & Deep QC Audit

**Published**: `2026-09-13`

---

## 🚀 What's New

### 18 new production-grade skills (registry 97 → 115)

Every new skill ships the same strict 5-section contract (System Architecture & Prerequisites, Input/Output Data Contracts, Production Reference Implementation, Execution Protocol & Step-by-Step Workflow, Edge Cases & Error Handling) with complete, runnable reference code and no placeholders.

**backend** (+2)
- `error-code-consistency-auditor` — Audit every error class, message, and HTTP mapping across the codebase for duplication, contradictory status codes, and undocumented errors.
- `middleware-order-validator` — Audit middleware registration order in Express/FastAPI apps against safety rules (auth before authz, rate-limit before routes, error handlers last) and emit fixes.

**core-coding** (+2)
- `refactor-safety-harness` — Record golden outputs of current behavior before a refactor, then diff outputs after to prove behavior is unchanged.
- `startup-cold-boot-optimizer` — Profile application cold-start, identify heavy imports and work in the boot hot path, and produce a targeted lazy-load optimization plan plus proven timings.

**database** (+1)
- `schema-drift-detector` — Compare SQL migrations, ORM models, and TypeScript types against one another to find which layer is silently out of sync before queries start breaking.

**debugging** (+1)
- `postmortem-autobiographer` — Turn an incident description or production stack trace into a structured postmortem with timeline, 5-whys, and trackable action items — ready for team review.

**developer-experience** (+4)
- `env-config-sleuth` — Cross-reference environment variables referenced by code against definitions in `.env` files, CI workflows, and docs to find missing, misspelled, and orphaned configuration keys.
- `monorepo-package-cleaner` — Audit a monorepo workspace for dependency cycles, mismatched shared versions, and cross-boundary imports, then emit a prioritized cleanup plan.
- `pr-logic-reviewer` — Review a pull-request diff for logic bugs (boundary conditions, null safety, state and edge semantics) — not style — and emit a bug-first review report.
- `timezone-trap-cron-debugger` — Simulate thousands of scheduled job runs across timezones and DST transitions to provably detect misfires, skips, and duplicate executions hidden in cron schedules.

**devops** (+3)
- `codegen-drift-watchdog` — Detect when generated output (Prisma client, tRPC router types, OpenAPI clients) is stale versus its source schema, then auto-regenerate or fail CI with a precise list.
- `dependency-fitness-scorecard` — Score every third-party dependency on maintenance activity, release cadence, issue health, and size so upgrade decisions are data-driven instead of fear-driven.
- `performance-budget-bouncer` — Enforce performance budgets in CI and reject pull requests that exceed size, weight, or timing thresholds with a machine-readable flagging report.

**security** (+2)
- `license-clash-mediator` — Build a dependency-license graph and flag copyleft/permissive conflicts plus missing license metadata before they become legal incidents.
- `trojan-source-hunter` — Scan source files for invisible Unicode/Bidirectional trojan-source characters that silently alter code logic flow without being visible to reviewers.

**testing** (+3)
- `flaky-test-jury` — Analyze repeated CI test logs, classify flaky tests by root-cause category, and emit stabilization patches plus a verdict report before they erode team trust.
- `golden-snapshot-migrator` — Capture golden snapshots before a major library or dependency migration and diff after to keep the external behavior contract intact.
- `shadow-traffic-replayer` — Replay recorded production HTTP traffic against a new build and diff responses to surface API regressions without writing a single test.

---

## 🛠️ Deep QC Audit & Bug Fixes

All 18 new skills passed a runtime smoke + syntax QC pass before release (`node --check` / `py_compile` on every code block, all 7/7 runtime smoke tests PASS). The audit caught and fixed real bugs:

- **`pr-logic-reviewer`** — hunk-boundary regex used a PCRE-only `\Z` anchor that never matched in JavaScript, so the tool silently reported `0 hits` on every diff. Rewritten with a JS-safe boundary pattern; verified a real boundary probe is now detected.
- **`timezone-trap-cron-debugger`** — naive per-minute/year simulation across all timezones ran for hours. Reworked to streaming per-wall-minute evaluation with a default set of common zones, `--all` opt-in, an explicit empty-zone guard (exit 2), and a documented `Intl` timezone list.
- **`monorepo-package-cleaner`** — dependency-cycle walker crashed (`c.path.join` on a boolean) and contained a deep-import scan that could throw on unreadable files. Fixed the path join and made deep-import handling safe/optional.
- **`codegen-drift-watchdog`** — removed a no-op loop and added detection for newly created files by regeneration.
- **`error-code-consistency-auditor`** — renamed a variable that shadowed `undefined`.
- **`schema-drift-detector`** — removed dead code.
- **`golden-snapshot-migrator`** — conflict-normalization now genuinely sorts keys before diffing.

Registry and generated copies (`registry.json`, `.opencode/skills/<id>/SKILL.md`) rebuilt and CI-verified: `115 skills`, build + frontmatter contract green.

---

## 📖 Upgrade Guide

### For Existing Users

```bash
git pull origin main
npm run build   # regenerates registry.json + .opencode/skills (115 skills)
```

OpenCode loads skills at startup — **restart OpenCode** after pulling so the 18 new skills are picked up. No existing skill paths or invocation IDs changed in this release; all 115 skills remain loadable via folder-derived slash commands (`/<id>`).

Custom tags/categories unchanged — the 17-category taxonomy is preserved.

---

## 📦 Version Details

- **Version:** `v3.5.0`
- **Release Date:** `2026-09-13`
- **Total Skills:** `115` (across 17 categories)
- **Registry Delta:** `97 → 115` (+18)
- **Tag:** `v3.5.0` (annotated Git tag)
- **GitHub Release:** `v3.5.0 - 18 Production-Grade Skills & Deep QC Audit`

---

*Generated from `opencode-artes` repository. For questions or issues, please open an issue on the GitHub repository.*