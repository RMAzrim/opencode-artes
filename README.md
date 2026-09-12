# opencode-artes 🚀

**The ONLY repository you will need to power up your OpenCode AI agent.**

*One repo to rule them all – the single ecosystem your OpenCode agent needs.*

<div align="center">
  <a href="https://github.com/RMAzrim/opencode-artes">
    <img src="https://img.shields.io/github/stars/RMAzrim/opencode-artes?style=for-the-badge&logo=github&logoColor=white" alt="Star">
  </a>
</div>

## 🎯 The Value Hook

Why browse dozens of scattered repositories when **all** the skills your OpenCode agent could ever need are housed right here?

- **frontend** – UI magic, accessibility, Tailwind, SEO, i18n.
- **backend** – APIs, GraphQL, caching, rate limiting, JWT rotation.
- **devops** – Dockerfiles, Kubernetes, CI/CD, Terraform modules.
- **testing** – unit tests, integration, property‑based testing.
- **ai-ops** – prompt evaluation, context compression, tool‑schema building.
- **core-coding** – design patterns, async concurrency, data structures, memory debugging.
- **orchestrator** – pipeline deployment, auto‑building, iterative fix loops.
- **core-engine-hardening** – command sanitization, verification, context banking, dependency mapping, requirement closure, regression detection, memory journaling, output trust, subagent evidence, schema validation, mega-pipeline deployment, project auto‑building, looping auto‑fix.

Each skill is a fully‑documented, production‑ready Markdown file with front‑matter, execution steps, edge‑case handling and validation criteria. Drop‑in ready. No bloat. Instant power.

## 📁 Nested Skill Directory Structure

Skills follow a flat namespace under `skills/`, organized into skill‑specific subdirectories:

```
skills/
  mega-pipeline-deployer/
    mega-pipeline-deployer.md
  project-auto-builder/
    project-auto-builder.md
  looping-auto-fixer/
    looping-auto-fixer.md
  accessibility-auditor/
    accessibility-auditor.md
  ... (all other skills)
```

**Each skill resides at `skills/<skill-id>/<skill-id>.md`** — the `file_path` in YAML frontmatter must match this pattern exactly.

### Per‑File QC Requirement

Before submitting a PR, every skill file must pass a quality control audit:

- **Frontmatter Check**: Verify `id`, `name`, `category`, `tags`, `author`, `version`, and `description` exist and are valid YAML.
- **Path Alignment**: Verify that `file_path` in the YAML frontmatter strictly matches `skills/<skill-id>/<skill-id>.md`.
- **Internal References QC**: Scan the Markdown body and update any outdated cross‑reference paths pointing to other skills (e.g., change `skills/other-skill.md` to `skills/other-skill/other-skill.md`).
- **Dry‑Run Test**: Apply `scripts/build-registry.js` validation rules to ensure code blocks and execution steps remain logically sound.
- **QC Status**: Log `[PASS]` or `[FAIL + Reason]` for this specific file before merging.

## 🚀 Get Started in 10 Seconds

1. `git clone https://github.com/RMAzrim/opencode-artes.git`
2. `cd opencode-artes`
3. `npm run build` ← generates `registry.json` **and** the OpenCode-discoverable `.opencode/skills/<id>/SKILL.md` files by recursively scanning `skills/*/*.md`
4. Start OpenCode from this directory (`opencode run '<your request>' --dir .`) – all skills are auto-discovered as slash-commands (e.g. `/accessibility-auditor`) and natural-language triggers via their description. No other configuration needed.

> **Note:** OpenCode loads skills at startup. Restart OpenCode after running `npm run build` (or after pulling new versions of this repo) so the new/updated skills are picked up.

### 📁 Source of Truth

Canonical skill files live at `skills/<skill-id>/<skill-id>.md` (with the full YAML frontmatter: `id`, `file_path`, `name`, `category`, `tags`, `author`, `version`, `description`). OpenCode itself reads the generated `.opencode/skills/<skill-id>/SKILL.md` copies, whose frontmatter is rewritten to OpenCode's format (`name` must equal the folder name; `description` drives auto-triggering). The generated copies are regenerated from the canonical files on every `npm run build` — **edit the canonical file, never the generated copy**, then rebuild.

👉 **Star ⭐ the repo** and never look for another skill repository again.

## 📦 Quick Overview

| Category | Skill Count | Representative Skills |
|----------|-------------|----------------------|
| **ai-ops** | 5 | prompt-evaluator, context-compressor, rag-chunking-evaluator, structured-output-enforcer, tool-schema-builder |
| **algorithms** | 1 | data-structure-optimizer |
| **api** | 2 | graphql-schema-designer, webhook-handler-generator |
| **backend** | 5 | caching-strategy-implementer, jwt-token-rotator, pagination-cursor-builder, rate-limiter-middleware, websocket-realtime-handler |
| **cloud** | 3 | terraform-module-builder, serverless-function-generator, k8s-manifest-validator |
| **core-coding** | 4 | async-concurrency-handler, error-class-hierarchy-builder, regex-builder-explainer, regex-builder-parser |
| **core-engine-hardening** | 10 | cmd-sanitizer, verify-orchestrator, context-bank, deptomap, spec-loop-closer, regression-sentinel, memory-journal, output-trust-check, subagent-evidence, schema-sync |
| **database** | 3 | sql-query-optimizer, db-migration-generator, tool-schema-builder |
| **developer-experience** | 7 | cli-tool-scaffolder, mermaid-diagrammer, regex-builder-explainer, i18n-locale-extractor, prompt-evaluator, openapi-spec-writer, cron-schedule-parser |
| **frontend** | 5 | accessibility-auditor, i18n-locale-extractor, seo-metadata-builder, tailwind-converter, type-definition-generator |
| **orchestrator** | 3 | mega-pipeline-deployer, project-auto-builder, looping-auto-fixer |
| **security** | 2 | secrets-leak-detector, jwt-token-rotator |
| **software-architecture** | 2 | design-pattern-implementer, dependency-injection-wire |
| **testing** | 1 | unit-test-generator |

---

## 🔧 Available Scripts

| Script | Description |
|--------|-------------|
| `npm run build` | Regenerates `registry.json` and `syncs .opencode/skills/<id>/SKILL.md` by scanning `./skills/*/*.md` |
| `npm run sync-skills` | Alias of `npm run build` – regenerates the OpenCode `.opencode/skills/` copies |
| `npm test` | Runs build and confirms registry generation |

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines, including the mandatory pre‑PR QC step for every skill file.

## 🙏 Acknowledgments

Built with ❤️ for the OpenCode agent community.