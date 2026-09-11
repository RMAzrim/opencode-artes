# Release Notes v1.5.0 - System Hardening & Skill Expansion

**Published**: 2026-09-11

## Total Skill Count: 43

The `opencode-artes` registry now contains **43 skills** across 13 categories.

---

## Categories & Breakdown

| Category | Skill Count | Representative Skills |
|----------|-------------|----------------------|
| **ai-ops** | 2 | rag-chunking-evaluator, structured-output-enforcer |
| **algorithms** | 1 | data-structure-optimizer |
| **api** | 2 | graphql-schema-designer, webhook-handler-generator |
| **backend** | 5 | caching-strategy-implementer, jwt-token-rotator, pagination-cursor-builder, rate-limiter-middleware, websocket-realtime-handler |
| **cloud** | 2 | terraform-module-builder, serverless-function-generator |
| **core-coding** | 4 | async-concurrency-handler, error-class-hierarchy-builder, regex-builder-explainer, regex-builder-parser |
| **core-engine-hardening** | 12 | cmd-sanitizer, verify-orchestrator, context-bank, deptomap, spec-loop-closer, regression-sentinel, memory-journal, output-trust-check, subagent-evidence, schema-sync, mega-pipeline-deployer, project-auto-builder, looping-auto-fixer |
| **database** | 0 | (no skills currently categorized under database) |
| **developer-experience** | 4 | cli-tool-scaffolder, mermaid-diagrammer, regex-builder-explainer, i18n-locale-extractor |
| **frontend** | 5 | accessibility-auditor, i18n-locale-extractor, seo-metadata-builder, tailwind-converter, type-definition-generator |
| **orchestrator** | 3 | mega-pipeline-deployer, project-auto-builder, looping-auto-fixer |
| **software-architecture** | 2 | design-pattern-implementer, dependency-injection-wire |

---

## Purpose Statement

### Core Engine Hardening (12 skills)
These 12 skills strengthen the AI agent's internal execution integrity. `cmd-sanitizer` detects and rewrites unsafe Windows/PowerShell 5.1 command patterns (bare `&&` chaining, UTF-16 pipe corruption, `$?` vs `$LASTEXITCODE` confusion, timeout-kill indeterminacy) before execution, preventing silent state corruption. `verify-orchestrator` auto-discovers project verification surfaces (test/lint/typecheck configs), runs the minimal verification suite, and gates every completion claim on machine-parsed exit codes and assertion output — returning `UNVERIFIED` rather than proceeding silently when discovery fails. `context-bank` materializes a structured CONTEXT_BANK.md + JSON file that captures verified file paths, decided invariants, active TODOs, and open risks, allowing subagents and repeated sessions to reload a lean current snapshot instead of decaying transcript memory. `deptomap` builds a persistent dependency graph with blast-radius analysis, listing consumers of any target symbol before edits and verifying no orphaned references exist after. `spec-loop-closer` forces every user requirement through a 1:1 mapping to a checkable assertion (grep-able token, executable test, or numeric threshold) before implementation begins. `regression-sentinel` re-runs passing checkpoints as a smoke suite before each new task, catching regressions caused by recent edits. `memory-journal` maintains a cross-session ledger of decisions and rationale, preventing re-litigation of settled choices. `output-trust-check` wraps every truncating tool call, refusing to decide on truncated data and flagging encoding anomalies (UTF-16 NULs, BOMs). `subagent-evidence` enforces a dispatch-time contract for explore agents: observations with `file:line` citations, inferences tagged `[INFERRED]`, and post-dispatch citation verification. `schema-sync` pings live tool schemas before workflows execute, diffs against cached schemas, and regenerates plans on mismatch. `mega-pipeline-deployer` orchestrates flexible pipeline workflows in Full Mode (all 7 steps sequentially) or Selective Mode (user-specified subset), with data contracting/validation between active steps and error halting. `project-auto-builder` dynamically inspects `./registry.json`, analyzes the project workspace stack (Node.js, Python, Docker), automatically matches and orders optimal skills into an execution sequence, and generates a readiness summary. `looping-auto-fixer` iteratively runs unit-test-generator → skill-tester → memory-leak-debugger/patching in a max-3-retry loop, exiting on SUCCESS or halting on FAILED_AFTER_MAX_RETRIES.

### Orchestrator (3 skills)
These 3 master orchestrator skills coordinate complex multi-skill workflows. `mega-pipeline-deployer` provides flexible pipeline execution with Full Mode (7 steps) or Selective Mode (user-specified steps), data contracting between active steps, and error halting. `project-auto-builder` auto-discovers skills from the registry, analyzes the project workspace, matches and orders skills dynamically, and produces a readiness report. `looping-auto-fixer` implements an iterative fix loop: generate tests, validate, analyze failures, patch code, repeat up to 3 times, exit on success or halt after max retries.

### Frontend (5 skills)
Skills for building and maintaining user-facing code and design. `accessibility-auditor` audits HTML/JSX against WCAG 2.1 guidelines and provides accessible ARIA fixes. `seo-metadata-builder` generates complete HTML meta tags, Open Graph, Twitter Cards, and JSON-LD structured data. `tailwind-converter` converts raw CSS or inline styles into clean, idiomatic Tailwind CSS utility classes. `i18n-locale-extractor` extracts hardcoded UI text strings into structured internationalization JSON translation files. `type-definition-generator` converts untyped JavaScript, Python dicts, or raw JSON payloads into strict TypeScript interfaces or Type Hint annotations.

### Backend (5 skills)
Skills for server-side infrastructure and services. The five backend skills cover caching (Cache-Aside, Write-Through, TTL-based LRU), authentication (JWT token rotation with refresh token rotation and revocation blacklisting), cursor/keyset pagination for database queries, API rate-limiting (Token Bucket, Sliding Window), and WebSocket connection lifecycles with heartbeat, reconnect logic, and event broadcasting — essential for building production-grade server applications.

### Core Coding (4 skills)
Skills focused on implementation-level code quality and algorithmic optimization. `async-concurrency-handler` implements async/await workflows, promise pools, worker threads, or goroutines while preventing race conditions. `error-class-hierarchy-builder` creates domain-specific custom exception classes with standardized error codes, HTTP statuses, and metadata payloads. `data-structure-optimizer` analyzes algorithm time/space complexity (Big O) and refactors logic using optimal data structures (Heaps, Tries, Hash Maps). `regex-builder-parser` constructs ReDoS-safe regular expressions and string parser logic for complex input extraction.

### AI-Ops (2 skills)
Skills for LLM workflow orchestration and output reliability. `rag-chunking-evaluator` analyzes document structures to recommend optimal chunking strategies and overlap ratios for RAG pipelines. `structured-output-enforcer` converts unstructured LLM output into validated JSON adhering to strict Zod or JSON Schema rules, with optional TypeScript type generation for end-to-end type safety.

### Software Architecture (2 skills)
Skills for system design and module interaction. `design-pattern-implementer` refactors code to apply object-oriented design patterns (Factory, Strategy, Observer, Decorator, Adapter) cleanly. `dependency-injection-wire` decouples code modules using Inversion of Control (IoC) containers and explicit interface abstractions.

### Developer Experience (4 skills)
Skills that improve the agent's operational tooling. `cli-tool-scaffolder` scaffolds interactive CLI tools with argument parsing, flags, spinners, and help menus. `mermaid-diagrammer` converts code logic, database structures, or system architectures into valid Mermaid.js visual diagrams. `regex-builder-explainer` constructs complex regular expressions based on pattern requirements with step-by-step logic breakdown. `i18n-locale-extractor` (also listed under frontend) extracts hardcoded UI text into structured translation JSON.

### Algorithms (1 skill)
Foundational algorithmic skills. `data-structure-optimizer` analyzes algorithm complexity and refactors using optimal structures.

### API (2 skills)
Skills for API design and integration. `graphql-schema-designer` designs GraphQL type definitions, query/mutation schemas, and resolver boilerplate code. `webhook-handler-generator` drafts secure webhook receiver endpoints with cryptographic signature verification (Stripe, GitHub, Midtrans).

### Cloud (2 skills)
Skills for infrastructure-as-code and serverless deployment. `terraform-module-builder` drafts modular, reusable Infrastructure-as-Code Terraform modules for cloud infrastructure. `serverless-function-generator` scaffolds lightweight serverless handlers for Cloudflare Workers or AWS Lambda with standard CORS and error handling.

### Database
(No skills currently categorized under database; the skills in this repository focus on application-layer operations rather than direct DB management.)

---

## Upgrade Path

This release (`v1.5.0`) adds **13 new skills** across 3 categories:

### Core Engine Hardening (10 new skills)
1. **`verify-orchestrator`** — Evidence-gated verification completion
2. **`cmd-sanitizer`** — Windows/PowerShell 5.1 command linting and guard insertion
3. **`context-bank`** — Structured context snapshot for session continuity
4. **`deptomap`** — Dependency graph with blast-radius analysis
5. **`spec-loop-closer`** — Requirement-to-assertion mapping enforcement
6. **`regression-sentinel`** — Smoke-test regression detection between tasks
7. **`memory-journal`** — Cross-session decision rationale preservation
8. **`output-trust-check`** — Truncation and encoding fidelity guard
9. **`subagent-evidence`** — Citation-verified subagent summaries
10. **`schema-sync`** — Live schema validation for integration workflows

### Orchestrator (3 new skills)
11. **`mega-pipeline-deployer`** — Flexible pipeline orchestration with Full/Selective modes
12. **`project-auto-builder`** — Dynamic skill matching and execution sequencing
13. **`looping-auto-fixer`** — Iterative test-fix-retry loop with 3-iteration threshold

All existing skills remain at `1.0.0`; the package version bump to `1.5.0` signals the addition of foundational hardening and orchestration capabilities that reduce silent-failure risk and enable autonomous multi-skill workflows across all subsequent agent operations.

---

*Generated from `registry.json` on 2026-09-11.*