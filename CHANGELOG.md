# Changelog

All notable changes to **opencode-artes** are documented here. This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org).

## [2.6.0] — latest
### Added
- **Live GitHub Pages catalog site** at <https://rmazrim.github.io/opencode-artes/> (set as repo homepage): searchable grid of all 97 skills across 17 categories, per-skill GitHub links, and install instructions. The HTTP catalog at `…/skills/` serves the generated OpenCode skills for one-line install.
- **Promo kit** — `docs/PROMO.md` with post-ready copy for X/Twitter, LinkedIn, Reddit and dev.to.
- `CITATION.cff` (v1.2.0, scholarly citation), `FUNDING.yml` (Sponsor button), `.gitattributes` (LF normalization), and `assets/terminal.svg` demo.
- README: "See it in action" terminal demo, "Support & share" section, and a live **star-history** chart.

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

[2.6.0]: https://github.com/RMAzrim/opencode-artes/releases/tag/v2.6.0
[2.5.0]: https://github.com/RMAzrim/opencode-artes/releases/tag/v2.5.0
[2.0.0]: https://github.com/RMAzrim/opencode-artes/releases/tag/v2.0.0
[1.5.5]: https://github.com/RMAzrim/opencode-artes/releases/tag/v1.5.5