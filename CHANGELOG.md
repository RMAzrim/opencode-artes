# Changelog

All notable changes to **opencode-artes** are documented here. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org).

## [3.0.0] — latest
### Added
- **18 new production-grade skills** (registry `97 → 115`):
  - Backend (+2): `error-code-consistency-auditor`, `middleware-order-validator`
  - Core-coding (+2): `refactor-safety-harness`, `startup-cold-boot-optimizer`
  - Database (+1): `schema-drift-detector`
  - Debugging (+1): `postmortem-autobiographer`
  - Developer-experience (+4): `env-config-sleuth`, `monorepo-package-cleaner`, `pr-logic-reviewer`, `timezone-trap-cron-debugger`
  - Devops (+3): `codegen-drift-watchdog`, `dependency-fitness-scorecard`, `performance-budget-bouncer`
  - Security (+2): `license-clash-mediator`, `trojan-source-hunter`
  - Testing (+3): `flaky-test-jury`, `golden-snapshot-migrator`, `shadow-traffic-replayer`
- `RELEASE_NOTES_v3.0.0.md` and README/live-catalog/assets updated to the 115-skill release.

### Changed
- Deep QC audit of all 18 new skills (runtime smoke + syntax checks); 7 real bugs fixed — see `RELEASE_NOTES_v3.0.0.md` for the full fix list (pr-logic-reviewer hunk regex, timezone-trap-cron-debugger performance, monorepo-package-cleaner crash, and more).
- Skill count now reads **115 skills** across 17 categories at runtime (registry-driven).
- Package version `2.6.0 → 3.0.0`.

## [2.6.0]
### Added
- **Live GitHub Pages catalog site** at <https://rmazrim.github.io/opencode-artes/> (set as repo homepage): searchable grid of all 97 skills across 17 categories, per-skill GitHub links, and install instructions. The HTTP catalog at `…/skills/` serves the generated OpenCode skills for one-line install.
- **Promo kit** — `docs/PROMO.md` with post-ready copy for X/Twitter, LinkedIn, Reddit and dev.to.
- `CITATION.cff` (v1.2.0, scholarly citation), `FUNDING.yml` (Sponsor button), `.gitattributes` (LF normalization), and `assets/terminal.svg` demo.
- README: "See it in action" terminal demo and a "Support & share" section.

### Changed
- Package version `2.5.0 → 2.6.0` (visibility release).

## [2.5.0]
### Added
- **4 suite orchestrators** (category `orchestrator`): `security-suite-orchestrator` (8-stage audit chain → `SECURITY_AUDIT_REPORT.md`), `frontend-suite-orchestrator`, `backend-suite-orchestrator`, `infra-qa-suite-orchestrator` — each supports `full_run` / `include_steps` / `skip_steps`, predecessor gating, fail-fast and consolidated per-step reports.
- **20 production web & security skills** across 4 domains:
  - Frontend (4): `nextjs-app-router-scaffolder`, `tailwind-responsive-darkmode-styler`, `state-management-query-architect`, `form-validation-schema-builder`
  - Backend (4): `express-fastapi-route-builder`, `graphql-schema-dataloader-builder`, `auth-session-oauth2-scaffolder`, `websocket-realtime-secure-engine`
  - Infra/QA (5): `drizzle-prisma-orm-architect`, `redis-pubsub-cache-manager`, `docker-multi-stage-stack-builder`, `playwright-e2e-security-flow-tester`, `lighthouse-web-vitals-optimizer`
  - Security (7): `owasp-sast-auditor`, `jwt-security-cracker-tester`, `bola-idor-vulnerability-scanner`, `sqli-xss-payload-sanitizer`, `cors-csp-headers-hardener`, `rate-limit-bruteforce-shield`, `dependency-cve-audit-patcher`
- **Reposilite hygiene, CI & GitHub presence**: `scripts/ci-verify.js` (frontmatter/BOM/registry/generated-copies contract check) + `verify` GitHub Actions workflow, issue & PR templates, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, GitHub Topics, SEO description, README overhaul, and a live GitHub Pages catalog site at <https://rmazrim.github.io/opencode-artes/>.
- Repo-local git identity (`RMAzrim`) so future commits count on the contribution graph.

### Changed
- Skill count now reads **97 skills** across 17 categories at runtime (registry-driven).
- Package version `2.0.0 → 2.5.0`.

## [2.0.0] — 2025
### Added
- **15 production skills across 4 categories**, plus 3 orchestrator master skills — total **73 skills**, full English function catalog in README.
- `.opencode/skills/<id>/SKILL.md` layout conformed to the upstream OpenCode skill docs.

### Changed
- Release, description and catalog flow centralized in `npm run build` / `npm run update-description`.

## [1.5.5] — 2025
### Changed
- Nested skills architecture `skills/<skill-id>/<skill-id>.md` (canonical source of truth) with generated discovery copies in `.opencode/skills/`.
- QC audit updates to keep all frontmatter valid and BOM-free.

## [1.5.0] — 2025
### Added
- 3 orchestrator master skills and core engine hardening skills.

## [1.0.0] — initial release
### Added
- 58 skills with docs and MIT license.

[3.0.0]: https://github.com/RMAzrim/opencode-artes/releases/tag/v3.0.0
[2.6.0]: https://github.com/RMAzrim/opencode-artes/releases/tag/v2.6.0
[2.5.0]: https://github.com/RMAzrim/opencode-artes/releases/tag/v2.5.0
[2.0.0]: https://github.com/RMAzrim/opencode-artes/releases/tag/v2.0.0
[1.5.5]: https://github.com/RMAzrim/opencode-artes/releases/tag/v1.5.5