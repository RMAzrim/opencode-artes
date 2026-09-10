# opencode-artes

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/opencode/opencode-artes/pulls)

A modular monorepo containing production-ready AI agent skills stored as structured Markdown files. Each skill is self-contained, versioned, and discoverable via a centralized `registry.json`.

## How It Works

AI agents consume `registry.json` at the project root to discover every available skill. The registry is a JSON array generated from the YAML frontmatter of each `.md` file in `./skills/`. Each entry contains `id`, `name`, `category`, `tags`, `author`, `version`, `description`, and the relative `file_path`. Agents can:

1. **List skills**: `npm run build` → reads `./skills/`, outputs `registry.json`
2. **Load a skill**: Navigate to `skills/<id>.md`, read frontmatter, render execution steps
3. **Validate a skill**: Run `npm test` or the `skills/skill-tester.md` meta-skill to audit compliance

## Repository Layout

```
opencode-artes/
├── .gitignore
├── LICENSE
├── package.json
├── registry.json          # auto-generated; do not edit manually
├── scripts/
│   └── build-registry.js  # generates registry.json from ./skills/
├── skills/
│   ├── accessibility-auditor.md
│   ├── tailwind-converter.md
│   ├── seo-metadata-builder.md
│   ├── ... (all skill .md files)
│   └── skill-tester.md    # meta-skill for testing other skills
└── README.md
```

## How to Use

### PRIMARY METHOD (Manual - Recommended)
The main and easiest way to use skills is to simply create a `./skills/` folder in your OpenCode workspace or project and drop any `.md` skill file inside it. The AI agent can immediately read the frontmatter and execution steps without any additional setup or build steps. This method is ideal for quick prototyping, per-project skill isolation, or when managing skills as standalone Markdown documents. As long as the file follows the required YAML frontmatter format and contains the 5 mandatory Markdown sections, the agent will recognize and execute it.

### SECONDARY METHOD (Automated Registry)
For large-scale skill indexing or monorepo-wide discovery, run `npm run build` from the project root. This executes `scripts/build-registry.js`, which scans all `.md` files directly inside `./skills/`, extracts their YAML frontmatter, and generates a consolidated `registry.json` at the project root. The registry enables:
- Programmatic skill listing and filtering by category/tags
- Automated validation via `npm test` (which runs the `skill-tester.md` meta-skill)
- Centralized skill metadata for dashboards, dashboards, or agent orchestration
After running `npm run build`, the `registry.json` file will be updated and ready for agent consumption.

## Skill Index Table (Placeholder)

| Category | Skill ID | Skill Name |
|----------|----------|------------|
| `database` | `sql-query-optimizer` | SQL Query Optimizer |
| `devops` | `dockerfile-builder` | Dockerfile Builder |
| `frontend` | `accessibility-auditor` | Accessibility Auditor |
| `ai-ops` | `prompt-evaluator` | Prompt Evaluator |
| `developer-experience` | `openapi-spec-writer` | OpenAPI Spec Writer |
| `testing` | `unit-test-generator` | Unit Test Generator |
| `core-coding` | `async-concurrency-handler` | Async Concurrency Handler |
| `backend` | `caching-strategy-implementer` | Caching Strategy Implementer |
| `api` | `graphql-schema-designer` | GraphQL Schema Designer |
| ... | ... | ... |