# Release Notes v1.5.0 - System Hardening & Skill Expansion

**Published**: 2026-09-11

## Total Skill Count: 40

The `opencode-artes` registry now contains **40 skills** across 12 categories.

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
| **core-engine-hardening** | 2 | cmd-sanitizer, verify-orchestrator |
| **data-science** | 2 | pandas-data-cleaner, chart-config-generator |
| **debugging** | 1 | memory-leak-debugger |
| **developer-experience** | 4 | cli-tool-scaffolder, mermaid-diagrammer, regex-builder-explainer (duplicate category), i18n-locale-extractor |
| **frontend** | 5 | accessibility-auditor, i18n-locale-extractor, seo-metadata-builder, tailwind-converter, type-definition-generator |
| **software-architecture** | 2 | design-pattern-implementer, dependency-injection-wire |

---

## Purpose Statement

### Core Engine Hardening
These skills strengthen the AI agent's internal execution integrity. `cmd-sanitizer` detects and rewrites unsafe Windows/PowerShell 5.1 command patterns (bare `&&` chaining, UTF-16 pipe corruption, `$?` vs `$LASTEXITCODE` confusion, timeout-kill indeterminacy) before execution, preventing silent state corruption. `verify-orchestrator` auto-discovers project verification surfaces (test/lint/typecheck configs), runs the minimal verification suite, and gates every completion claim on machine-parsed exit codes and assertion output — returning `UNVERIFIED` rather than proceeding silently when discovery fails. Together, they form the foundation for reliable, evidence-gated agent workflows.

### Frontend
Skills for building and maintaining user-facing code and design. `accessibility-auditor` audits HTML/JSX against WCAG 2.1 guidelines and provides accessible ARIA fixes. `seo-metadata-builder` generates complete HTML meta tags, Open Graph, Twitter Cards, and JSON-LD structured data. `tailwind-converter` converts raw CSS or inline styles into clean, idiomatic Tailwind CSS utility classes. `i18n-locale-extractor` extracts hardcoded UI text strings into structured internationalization JSON translation files. `type-definition-generator` converts untyped JavaScript, Python dicts, or raw JSON payloads into strict TypeScript interfaces or Type Hint annotations.

### Backend
Skills for server-side infrastructure and services. The five backend skills cover caching (Cache-Aside, Write-Through, TTL-based LRU), authentication (JWT token rotation with refresh token rotation and revocation blacklisting), cursor/keyset pagination for database queries, API rate-limiting (Token Bucket, Sliding Window), and WebSocket connection lifecycles with heartbeat, reconnect logic, and event broadcasting — essential for building production-grade server applications.

### Core Coding
Skills focused on implementation-level code quality and algorithmic optimization. `async-concurrency-handler` implements async/await workflows, promise pools, worker threads, or goroutines while preventing race conditions. `error-class-hierarchy-builder` creates domain-specific custom exception classes with standardized error codes, HTTP statuses, and metadata payloads. `data-structure-optimizer` analyzes algorithm time/space complexity (Big O) and refactors logic using optimal data structures (Heaps, Tries, Hash Maps). `regex-builder-parser` constructs ReDoS-safe regular expressions and string parser logic for complex input extraction.

### AI-Ops
Skills for LLM workflow orchestration and output reliability. `rag-chunking-evaluator` analyzes document structures to recommend optimal chunking strategies and overlap ratios for RAG pipelines. `structured-output-enforcer` converts unstructured LLM output into validated JSON adhering to strict Zod or JSON Schema rules, with optional TypeScript type generation for end-to-end type safety.

### Software Architecture
Skills for system design and module interaction. `design-pattern-implementer` refactors code to apply object-oriented design patterns (Factory, Strategy, Observer, Decorator, Adapter) cleanly. `dependency-injection-wire` decouples code modules using Inversion of Control (IoC) containers and explicit interface abstractions.

### Algorithms
Foundational algorithmic skills. `data-structure-optimizer` (also listed under core-coding) analyzes algorithm complexity and refactors using optimal structures.

### Developer Experience
Skills that improve the agent's operational tooling. `cli-tool-scaffolder` scaffolds interactive CLI tools with argument parsing, flags, spinners, and help menus. `mermaid-diagrammer` converts code logic, database structures, or system architectures into valid Mermaid.js visual diagrams. `regex-builder-explainer` constructs complex regular expressions based on pattern requirements with step-by-step logic breakdown. `i18n-locale-extractor` (also listed under frontend) extracts hardcoded UI text into structured translation JSON.

### Database
(No skills currently categorized under database; the skills in this repository focus on application-layer operations rather than direct DB management.)

### Cloud
Skills for infrastructure-as-code and serverless deployment. `terraform-module-builder` drafts modular, reusable Infrastructure-as-Code Terraform modules for cloud infrastructure. `serverless-function-generator` scaffolds lightweight serverless handlers for Cloudflare Workers or AWS Lambda with standard CORS and error handling.

### Debugging
Skills for runtime issue resolution. `memory-leak-debugger` identifies and resolves unmanaged memory leaks, event listener leaks, and circular references across runtimes.

---

## Upgrade Path

This release (`v1.5.0`) adds **10 new skills** across 2 categories to core engine hardening:

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

---

*Generated from `registry.json` on 2026-09-11.*