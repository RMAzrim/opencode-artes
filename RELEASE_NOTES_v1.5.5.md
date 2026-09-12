# Release Notes v1.5.5 - Nested Skills Architecture & QC Audit Updates

**Published**: `2026-09-11`

---

## 🚀 What's New

### Migration to Nested Directory Architecture

All **58 skills** have been migrated from the flat `skills/` layout to the nested structure:

```
skills/
  <skill-id>/
    <skill-id>.md
```

**Before:** `skills/accessibility-auditor.md`  
**After:** `skills/accessibility-auditor/accessibility-auditor.md`

**Skills affected:** All 58 skills including:
- `mega-pipeline-deployer` — Full/Selective pipeline orchestration with data contracting
- `project-auto-builder` — Dynamic skill matching from registry + workspace analysis
- `looping-auto-fixer` — Iterative test-fix-retry loop (max 3 retries)
- `verify-orchestrator` — Evidence-gated verification completion
- `cmd-sanitizer` — Windows/PowerShell 5.1 command linting
- `context-bank` — Structured context snapshot for session continuity
- `deptomap` — Dependency graph with blast-radius analysis
- `spec-loop-closer` — Requirement-to-assertion mapping enforcement
- `regression-sentinel` — Smoke-test regression detection
- `memory-journal` — Cross-session decision rationale preservation
- `output-trust-check` — Truncation and encoding fidelity guard
- `subagent-evidence` — Citation-verified subagent summaries
- `schema-sync` — Live schema validation for integration workflows
- + 40+ other skills

**Per-File QC Audit Workflow:** Every skill file must now pass a mandatory Quality Control audit before PR merge:

- **Frontmatter Check:** Verify `id`, `name`, `category`, `tags`, `author`, `version`, `description` exist and are valid YAML
- **Path Alignment:** Verify `file_path` in YAML frontmatter strictly matches `skills/<skill-id>/<skill-id>.md`
- **Internal References QC:** Scan Markdown body for outdated cross-reference paths (e.g., `skills/other-skill.md` → `skills/other-skill/other-skill.md`)
- **Dry-Run Test:** Apply `scripts/build-registry.js` validation rules to ensure code blocks and execution steps remain logically sound

**Master Orchestrator Skills Added:**

- **`mega-pipeline-deployer`** — Flexible pipeline execution in Full Mode (all 7 steps sequentially) or Selective Mode (user-specified step subset). Performs data contracting/validation between active steps, skips inactive steps gracefully, and halts with exact error logging when an active step fails.

- **`project-auto-builder`** — Dynamic orchestrator that inspects `./registry.json`, analyzes the project workspace stack (Node.js, Python, Docker, etc.), automatically matches and orders optimal skills into an execution sequence, and generates a final readiness summary report.

- **`looping-auto-fixer`** — Iterative fixer that runs `unit-test-generator` → validates via `skill-tester` → if tests fail, feeds error logs to `memory-leak-debugger` or patches code → repeats up to 3 retry iterations → exits on `SUCCESS` or halts on `FAILED_AFTER_MAX_RETRIES`.

---

## 🛠️ Bug Fixes & Refactoring

- **Cross-reference path corrections:** Updated all internal `skills/X.md` references across skill documents to the new `skills/X/X.md` format
- **`scripts/build-registry.js`** scanning logic: Rewrote the Node.js script to recursively scan `./skills/*/*.md` and extract frontmatter from all validated skill files, outputting to `./registry.json`
- **Fixed `ERR_INVALID_PACKAGE_CONFIG` error:** Updated `package.json` to `"type": "module"` and resolved Node.js module resolution issues
- **Registry rebuild:** `registry.json` regenerated with 58 skills across 17 categories (ai-ops: 5, algorithms: 1, api: 2, backend: 5, cloud: 3, core-coding: 4, core-engine-hardening: 10, data-science: 2, database: 3, debugging: 1, developer-experience: 7, devops: 2, frontend: 5, orchestrator: 3, security: 2, software-architecture: 2, testing: 1, uncategorized: 4)
- **QC audit scripts added:** `scripts/clean_frontmatter.py`, `scripts/regenerate_v3.py`, `scripts/regenerate_robust.py`, `scripts/regenerate_registry.py`, `scripts/rewrite_frontmatter.py`, `scripts/fix_v2.py` (all for migration and QC purposes)

---

## 📖 Migration / Upgrade Guide

### For Existing Users

If you have been using `opencode-artes` skills previously, follow these steps to update to v1.5.5:

#### 1. Update Your Local Clone

```bash
git pull origin main
```

#### 2. Rebuild the Registry

```bash
npm run build
# or manually:
node scripts/build-registry.js
```

This will regenerate `registry.json` by recursively scanning the new `skills/*/*.md` directory structure.

#### 3. Update Skill File Paths

Your skill invocation paths must now follow the nested format:

**Old (no longer valid):**
```bash
opencode skill:run accessibility-auditor
# or referencing: skills/accessibility-auditor.md
```

**New (required):**
```bash
opencode skill:run accessibility-auditor
# The skill directory: skills/accessibility-auditor/accessibility-auditor.md
```

#### 4. Run the Per-File QC Audit

Before committing any skill modifications, run the mandatory QC checklist:

```bash
# 1. Frontmatter Check
python -c "
with open('skills/<skill-id>/<skill-id>.md') as f:
    content = f.read()
if not content.startswith('---'):
    print('FAIL: No YAML frontmatter')
    exit()
parts = content.split('---')
if len(parts) < 3:
    print('FAIL: Invalid frontmatter structure')
    exit()
ft = parts[1].strip()
for key in ['id', 'name', 'category', 'tags', 'author', 'version', 'description']:
    if key not in ft:
        print(f'FAIL: Missing frontmatter key: {key}')
        exit()
print('PASS: Frontmatter valid')
"

# 2. Path Alignment Check
grep -q 'file_path: skills/' skills/<skill-id>/<skill-id>.md && \
  grep -q "file_path: skills/<skill-id>/<skill-id>.md" skills/<skill-id>/<skill-id>.md && \
  echo 'PASS: file_path aligned' || echo 'FAIL: file_path mismatch'

# 3. Internal References QC
if grep -r 'skills/[^/]+\.md' skills/<skill-id>/<skill-id>.md | grep -v '<skill-id>\.md' > /dev/null; then
  echo 'FAIL: Stale cross-references found'
else
  echo 'PASS: No stale references'
fi

# 4. Dry-Run Test (optional but recommended)
npm run build && echo 'PASS: Registry builds successfully'
```

#### 5. Update Your IDE/Tooling

If you have IDE integrations, script hooks, or tooling that references skill file paths, update them to use the new `skills/<skill-id>/<skill-id>.md` pattern.

#### 6. Verify Skill Access

Test that your most-used skills still function correctly:

```bash
# Example: Run the verify-orchestrator skill
opencode skill:run verify-orchestrator

# Example: Run the cmd-sanitizer skill
opencode skill:run cmd-sanitizer "python build.py && python test.py"
```

---

## 📦 Version Details

- **Version:** `v1.5.5`
- **Release Date:** `2026-09-11`
- **Total Skills:** `58` (across 17 categories)
- **Commit:** `feat: release v1.5.5 - nested skills architecture & QC audit updates`
- **Tag:** `v1.5.5` (annotated Git tag)
- **GitHub Release:** `v1.5.5 - Nested Skills Architecture & QC Audit Updates`

---

*Generated from `opencode-artes` repository. For questions or issues, please open an issue on the GitHub repository.*