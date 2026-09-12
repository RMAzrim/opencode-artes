---
id: project-auto-builder
file_path: skills/project-auto-builder/project-auto-builder.md
name: Project Auto Builder
category: orchestrator
tags: [orchestrator, workflow, automation, multi-skill, registry, dynamic]
author: opencode-core
version: 1.0.0
description: Dynamic orchestrator that inspects ./registry.json, analyzes the project workspace stack (Node.js, Python, Docker, etc.), automatically matches and orders optimal skills into an execution sequence, runs the selected skills, and generates a final readiness summary report.
---

# Project Auto Builder

## Prerequisites & Dependencies

- Access to `./skills/` flat directory containing all skill `.md` files
- Access to `./registry.json` at repository root for skill indexing and metadata
- Python 3.10+ runtime for orchestration logic and JSON processing
- `jq` for JSON parsing and skill metadata extraction
- `inquirer` or equivalent for interactive workspace stack detection (optional, defaults to automated detection)
- Node.js/Python version managers for runtime detection (nvm, pyenv, etc.)

## Execution Steps

### 1. Registry Inspection
- Read `./registry.json` at the repository root
- Parse the full skill catalog: extract each skill's `id`, `name`, `category`, `tags`, and `description`
- Build an in-memory index of all available skills, grouped by category and tagged for quick lookup
- Validate registry JSON schema integrity — if malformed, halt and report: "Registry corrupted: cannot proceed with auto-build"
- Output: `registry-index.json` — a condensed map of `{id: {name, category, tags, description}}`

### 2. Workspace Analysis
- Scan the project directory for language/runtime markers:
  - **Node.js**: presence of `package.json`, `node_modules`, `tsconfig.json`
  - **Python**: presence of `requirements.txt`, `pyproject.toml`, `setup.py`, `.python-version`
  - **Docker**: presence of `Dockerfile`, `docker-compose.yml`, `.dockerignore`
  - **Mixed stacks**: detect multiple language runtimes in parallel
- Determine the primary project type and secondary language/runtime artifacts
- Capture available tooling versions (node version, python version, docker availability)
- Output: `workspace-profile.json` — `{primary_stack: "node|python|docker|mixed", versions: {...}, markers: [...]}`

### 3. Dynamic Matching
- Cross-reference the `workspace-profile.json` against the `registry-index.json`
- Scoring algorithm: for each skill, compute a match score based on:
  - Tag overlap between skill tags and detected stack markers
  - Category relevance (e.g., `backend` skills for server-side stacks, `data-science` for Python data workloads)
  - Explicit stack mentions in skill description
- Sort skills by match score (descending) to produce an optimal execution order
- Allow user overrides: permit the user to promote/demote specific skills via `--prioritize` / `--demote` CLI flags
- Output: `skill-order.json` — ordered list of skill IDs with match scores: `[{id, score, reason}]`

### 4. Execution Report
- Execute skills in the order determined by `skill-order.json`
- For each skill:
  - Invoke the skill's primary functionality (or a representative summary if the skill has no executable main function)
  - Capture exit code, stdout, stderr, and generated artifacts
  - Track pass/fail status per skill
- After all skills execute, generate a comprehensive `readiness-summary.md` report including:
  - Which skills were selected and their match scores
  - Execution results per skill (pass/fail, key outputs)
  - Overall project readiness status
  - Recommendations for next steps (e.g., "run verify-orchestrator", "missing: Dockerfile")
- Output: `readiness-summary.md` — human-readable markdown report

### 5. Fallback Behavior
If no skills match the detected workspace stack:
- List all skills with their match scores (even low ones)
- Prompt the user: "No high-match skills found. Proceed with lowest-match skill or manual selection?"
- If user chooses manual selection, present the ranked list and allow ID-based selection
- If user chooses lowest-match, execute the top-1 ranked skill with reduced expectations flag

### CLI Interface
```
project-auto-builder [--list] [--prioritize <comma-separated-ids>] [--demote <comma-separated-ids>]
  --list                 List all available skills from registry
  --prioritize           Promote specific skill IDs to top of execution order
  --demote               Demote specific skill IDs to bottom of execution order
```

### Example Workflow
```bash
# Auto-build for a Node.js project
project-auto-builder

# Internal execution flow:
1. Read ./registry.json → index 40 skills
2. Scan workspace → detect Node.js stack, v18.17.0
3. Match skills → rank by tag overlap: ["rate-limiter-middleware"(92%), "websocket-realtime-handler"(88%), ...]
4. Execute in order → capture artifacts
5. Generate readiness-summary.md

# Output sample (readiness-summary.md)
# Project Auto Builder Report
## Stack Detected: Node.js v18.17.0
## Selected Skills (3 of 5 top-matched):
1. **rate-limiter-middleware** (match: 92%) — ✅ Executed, middleware scaffold generated at ./skills/output/rate-limiter-middleware/
2. **websocket-realtime-handler** (match: 88%) — ✅ Executed, WS handler skeleton at ./skills/output/websocket-realtime-handler/
3. **cli-tool-scaffolder** (match: 81%) — ✅ Executed, CLI tool at ./skills/output/cli-tool-scaffolder/
## Overall Readiness: 85% — All top-matched skills executed successfully.
## Recommendations: Consider running verify-orchestrator to validate integration.
```