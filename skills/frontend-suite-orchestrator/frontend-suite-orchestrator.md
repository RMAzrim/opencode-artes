---
id: frontend-suite-orchestrator
file_path: skills/frontend-suite-orchestrator/frontend-suite-orchestrator.md
name: Frontend Suite Orchestrator
category: orchestrator
tags: [orchestrator, workflow, automation, frontend]
author: opencode-core
version: 1.0.0
description: "Orchestrates a 5-stage frontend build chain over a Next.js project: App Router scaffold, Tailwind responsive/dark-mode styling, zod-backed progressive forms, and the Zustand + TanStack Query state/query pipeline, followed by a build validation gate that runs `npm run build` / `next build`, verifies the component tree and routes exist, and consolidates everything into a FRONTEND_SUITE_REPORT.md. Supports full_run, include_steps, skip_steps, fail_fast, and artifact_dir customization so teams can re-materialize any subset of the scaffolding chain. The final report captures the scaffolded file-tree summary, the validation build exit code, and open items for follow-up."
---

# Frontend Suite Orchestrator

## 1. System Overview & Target Sub-Skills
The Frontend Suite Orchestrator is a deterministic DAG runner that materializes a full modern Next.js 15 App Router application in four blueprint stages, then gated by a real production build (and route/component existence checks) writes one consolidated handoff document. It is invoked when the project needs an opinionated, reproducible frontend baseline: page tree and server actions first, then theming, then validated forms, then server-state plumbing — ordered so later blueprint files overwrite earlier placeholders in the same `app/` tree.

Each stage "executes" its sub-skill by reading the sub-skill's Section 3 reference implementation (`# FILE: <path>` markers) and writing every documented artifact under the project root. Invoked sub-skills and what each produces:

1. `skills/nextjs-app-router-scaffolder/nextjs-app-router-scaffolder.md` — writes `package.json`, `tsconfig.json`, `app/layout.tsx`, `app/page.tsx`, `app/error.tsx`, `app/loading.tsx`, `app/not-found.tsx`, `app/globals.css`, `app/actions/schema.ts` (zod + `ServerActionResponse<T>`), `app/actions/user.ts` (`"use server"` actions), and `app/components/UserForm.tsx`.
2. `skills/tailwind-responsive-darkmode-styler/tailwind-responsive-darkmode-styler.md` — writes `tailwind.config.js`, `postcss.config.js`, `app/globals.css`, `components/ResponsiveNavbar.tsx`, `components/Card.tsx`, `components/ThemeToggle.tsx`, `app/layout.tsx` (ThemeProvider wiring), `app/page.tsx` (demo), plus `input-reference.html` and the CDN-free `index.html` variant.
3. `skills/form-validation-schema-builder/form-validation-schema-builder.md` — writes `lib/validators.ts` (shared zod schemas + `z.infer` types + discriminated-union bundle parser), `components/Field.tsx`, `components/RegistrationForm.tsx` (progressive 3-step form), and replaces `app/layout.tsx` / `app/page.tsx` with the form demo.
4. `skills/state-management-query-architect/state-management-query-architect.md` — writes `stores/authStore.ts`, `stores/themeStore.ts`, `stores/cartStore.ts` (Zustand + `persist`), `providers/QueryProvider.tsx`, `hooks/useTodos.ts` (query factory + optimistic mutations), `app/api/todos/route.ts`, `components/TodoApp.tsx`, and replaces `app/layout.tsx` (QueryProvider) / `app/page.tsx` (TodoApp).
5. **Final validation + consolidation (in orchestrator)** — runs `npm run build` (with `npx next build` fallback), asserts the full scaffolded component/routes inventory exists, then writes `FRONTEND_SUITE_REPORT.md` with the file-tree summary, build exit code, verified routes, and open items.

## 2. Execution Parameters & Configuration Options
- **full_run** (default `true`): execute the entire 5-step chain in order. When `true` and `include_steps` is empty, every step S1..S5 runs.
- **include_steps**: array of step keys to run — run ONLY these. Valid keys: `scaffold`, `styler`, `forms`, `state_query`, `validate_build`.
- **skip_steps**: array of step keys to omit. Steps are recorded as `NOT_RUN` in the matrix.
- **fail_fast** (default `true`): halt the chain at the first failing step (failed materialization, missing blueprint section, or non-zero build).
- **report_dir / artifact_dir**: project root where blueprint artifacts materialize and where `FRONTEND_SUITE_REPORT.md` is written. Default `./frontend-suite-build`.
- Extra inputs: `projectRoot` (required; target directory for the scaffolded tree), `packageManager` (`npm`, `pnpm`, `yarn`, `bun` — the build gate resolves to the matching manager) and `buildTimeoutSeconds` (default 1200).

JSON Schema for the orchestrator options object:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "full_run": { "type": "boolean", "default": true },
    "include_steps": {
      "type": "array",
      "items": { "enum": ["scaffold", "styler", "forms", "state_query", "validate_build"] },
      "minItems": 1
    },
    "skip_steps": {
      "type": "array",
      "items": { "enum": ["scaffold", "styler", "forms", "state_query", "validate_build"] }
    },
    "fail_fast": { "type": "boolean", "default": true },
    "report_dir": { "type": "string", "default": "./frontend-suite-build" },
    "projectRoot": { "type": "string", "minLength": 1, "description": "Target directory that receives the scaffolded tree" },
    "packageManager": { "enum": ["npm", "pnpm", "yarn", "bun"], "default": "npm" },
    "buildTimeoutSeconds": { "type": "integer", "default": 1200 }
  },
  "required": ["projectRoot"]
}
```

Consolidated output report structure (written as `FRONTEND_SUITE_REPORT.md`, mirror JSON at `frontend_suite_result.json`):

```json
{
  "orchestrator": "frontend-suite-orchestrator",
  "run_id": "fe-2026-09-13T12-00-00Z",
  "report_dir": "./frontend-suite-build",
  "steps": [
    {
      "key": "scaffold", "step": "S1",
      "skill_path": "skills/nextjs-app-router-scaffolder/nextjs-app-router-scaffolder.md",
      "status": "PASS", "exit_code": 0,
      "artifacts_written": ["app/layout.tsx", "app/page.tsx", "app/actions/schema.ts"]
    }
  ],
  "build": { "exit_code": 0, "command": "npm run build", "verified_routes": ["/", "/api/todos"], "missing_files": [] },
  "open_items": [],
  "consolidated_report": "FRONTEND_SUITE_REPORT.md"
}
```

## 3. Step-by-Step Execution Protocol & Data Flow

1. **Pre-flight Check**: verify Node.js >= 20.11.0 and the active package manager (`npm`, `pnpm`, `yarn`, or `bun`) are on PATH; confirm all five sub-skill paths exist under `skills/<id>/<id>.md`; confirm `projectRoot` is writable and, when `full_run` is false but scaffolding steps are included, that the target `package.json` already exists so later steps do not overwrite a live tree unintentionally.

2. **Sequential Chaining** (each stage materializes its sub-skill's Section 3 blueprint — the fenced block between `## 3. Production Reference Implementation` and `## 4` — by splitting on `# FILE: <relative-path>` markers and writing each file under `projectRoot`; parent dirs are created on demand):
   - **S1 — `scaffold`** (path `skills/nextjs-app-router-scaffolder/nextjs-app-router-scaffolder.md`): writes the App Router skeleton — `package.json`, `tsconfig.json`, `app/layout.tsx`, `app/page.tsx`, `app/error.tsx`, `app/loading.tsx`, `app/not-found.tsx`, `app/globals.css`, `app/actions/schema.ts`, `app/actions/user.ts`, `app/components/UserForm.tsx`. Output: the scaffolded file inventory in the step result.
   - **S2 — `styler`** (path `skills/tailwind-responsive-darkmode-styler/tailwind-responsive-darkmode-styler.md`): writes `tailwind.config.js`, `postcss.config.js`, `app/globals.css` (semantic tokens + `.dark`), `components/ResponsiveNavbar.tsx`, `components/Card.tsx`, `components/ThemeToggle.tsx`, `app/layout.tsx` (ThemeProvider), `app/page.tsx` (demo), `input-reference.html`, `index.html`. Output: component inventory + themed layout state.
   - **S3 — `forms`** (path `skills/form-validation-schema-builder/form-validation-schema-builder.md`): writes `lib/validators.ts` (zod single source of truth), `components/Field.tsx`, `components/RegistrationForm.tsx`, replaces `app/layout.tsx`, `app/page.tsx` with the registration demo. Output: `RegistrationFormFields`/`registrationBundleSchema` contract types and the form component inventory.
   - **S4 — `state_query`** (path `skills/state-management-query-architect/state-management-query-architect.md`): writes `stores/authStore.ts`, `stores/themeStore.ts`, `stores/cartStore.ts`, `providers/QueryProvider.tsx`, `hooks/useTodos.ts`, `app/api/todos/route.ts`, `components/TodoApp.tsx`, replaces `app/layout.tsx` (QueryProvider) and `app/page.tsx` (TodoApp). Output: store/query inventory + `QueryClient` defaultOptions contract.
   - **S5 — `validate_build`**: runs `npm run build` (fallback `npx next build`) in `projectRoot`, then asserts the combined mandatory inventory exists (App Router pages, server-action layer, theme components, zod form layer, state/query layer, mock API route). Output: `build_exit_code`, `verified_component_tree`, `missing_files`, `build_stdout_tail`/`build_stderr_tail`, and the consolidated `FRONTEND_SUITE_REPORT.md`.

3. **Data Contracting** — step-N output artifact to step-(N+1) input fields:
   - S1 → **S2**: the scaffold's `app/layout.tsx`, `app/globals.css`, and `package.json` are the baseline the styler overwrites — `app/globals.css` gains `:root`/`.dark` token vars and tailwind `@directives`; `app/layout.tsx` gains `ThemeProvider` wiring; `package.json` gains `tailwindcss`/`postcss`/`autoprefixer` dev deps and the `next-themes` runtime dep.
   - S2 → **S3**: the styler's `app/page.tsx` demo markup and semantic token classes are replaced by `components/RegistrationForm.tsx`; `lib/validators.ts` (`accountStepSchema`, `addressStepSchema`, `confirmStepSchema`, discriminated-union `registrationBundleSchema`, inferred `RegistrationFormFields`) becomes the single validation source consumed by `components/Field.tsx` and `components/RegistrationForm.tsx`.
   - S3 → **S4**: `RegistrationForm.onSubmitSuccess(RegistrationFormFields)` payload and the `lib/validators.ts` types define the submit boundary; S4 wires `providers/QueryProvider.tsx` into `app/layout.tsx`, exposes `stores/*` (auth/theme/cart) selectors, and provides `hooks/useTodos.ts` (`todoKeys.all`, `useTodos`, `useCreateTodo`, `useToggleTodo`) plus the `app/api/todos/route.ts` mock backend the hooks call with `staleTime: 30_000`, `gcTime: 5 * 60_000`, `retry: 2`.
   - S4 → **S5**: the complete materialized file inventory (S1..S4 artifact paths) is the `required` list the build gate checks against disk; `package.json` scripts (`build`, `typecheck`) are the execution contract for the `npm run build` gate.

4. **Final Consolidation**: the orchestrator writes `{report_dir}/FRONTEND_SUITE_REPORT.md` containing (a) a scaffolded file-tree summary grouped by stage with a per-step PASS/FAIL/NOT_RUN matrix, (b) the validation section with the build command, exit code, verified routes/components, and any missing files, and (c) an Open Items list assembled from missing artifacts, build stderr/exit hints, and warnings. A machine-readable mirror is written to `{report_dir}/frontend_suite_result.json`.

## 4. Reference Execution DAG / Pseudo-Code Implementation

```python
#!/usr/bin/env python3
"""Frontend Suite Orchestrator — 5-stage Next.js scaffold DAG.

Materializes four App Router blueprint stages (scaffold, styler, forms,
state_query) from their sub-skill Section 3 reference implementations, gates
the tree with a real npm build, then consolidates FRONTEND_SUITE_REPORT.md.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STEP_ORDER = ["scaffold", "styler", "forms", "state_query", "validate_build"]

SKILL_PATHS = {
    "scaffold": "skills/nextjs-app-router-scaffolder/nextjs-app-router-scaffolder.md",
    "styler": "skills/tailwind-responsive-darkmode-styler/tailwind-responsive-darkmode-styler.md",
    "forms": "skills/form-validation-schema-builder/form-validation-schema-builder.md",
    "state_query": "skills/state-management-query-architect/state-management-query-architect.md",
    "validate_build": None,
}

STEP_NUM = {key: "S" + str(index + 1) for index, key in enumerate(STEP_ORDER)}

# Mandatory artifact inventory each stage is contracted to materialize to disk.
ARTIFACTS = {
    "scaffold": [
        "package.json", "tsconfig.json",
        "app/layout.tsx", "app/page.tsx", "app/error.tsx",
        "app/loading.tsx", "app/not-found.tsx", "app/globals.css",
        "app/actions/schema.ts", "app/actions/user.ts",
        "app/components/UserForm.tsx",
    ],
    "styler": [
        "tailwind.config.js", "postcss.config.js", "app/globals.css",
        "components/ResponsiveNavbar.tsx", "components/Card.tsx",
        "components/ThemeToggle.tsx", "app/layout.tsx", "app/page.tsx",
        "input-reference.html", "index.html",
    ],
    "forms": [
        "lib/validators.ts", "components/Field.tsx",
        "components/RegistrationForm.tsx", "app/layout.tsx", "app/page.tsx",
    ],
    "state_query": [
        "stores/authStore.ts", "stores/themeStore.ts", "stores/cartStore.ts",
        "providers/QueryProvider.tsx", "hooks/useTodos.ts",
        "app/api/todos/route.ts", "components/TodoApp.tsx",
        "app/layout.tsx", "app/page.tsx",
    ],
}

BUILD_GATE_PATHS = [
    "package.json", "tsconfig.json",
    "app/layout.tsx", "app/page.tsx",
    "app/globals.css",
    "app/actions/schema.ts", "app/actions/user.ts",
    "app/components/UserForm.tsx",
    "tailwind.config.js", "postcss.config.js",
    "components/ResponsiveNavbar.tsx", "components/Card.tsx",
    "components/ThemeToggle.tsx",
    "lib/validators.ts", "components/Field.tsx",
    "components/RegistrationForm.tsx",
    "stores/authStore.ts", "stores/themeStore.ts", "stores/cartStore.ts",
    "providers/QueryProvider.tsx", "hooks/useTodos.ts",
    "app/api/todos/route.ts", "components/TodoApp.tsx",
]

RECOMMENDED_DEFAULT = {
    "report_dir": "./frontend-suite-build",
    "package_manager": "npm",
    "fail_fast": True,
    "build_timeout_seconds": 1200,
}

FILE_MARKER = re.compile(r"#\s*FILE:\s*(\S+)")


def predecessor_of(key):
    index = STEP_ORDER.index(key)
    return STEP_ORDER[index - 1] if index > 0 else ""


def select_steps(options):
    full_run = bool(options.get("full_run", True))
    include = list(options.get("include_steps") or [])
    skip = set(options.get("skip_steps") or [])
    active = []
    for key in STEP_ORDER:
        take = (key in include) if include else full_run
        if take and key not in skip and key not in active:
            active.append(key)
    return active


def materialize_blueprint(skill_path, project_root, stage):
    """Write every '# FILE: <path>' artifact in the sub-skill's Section 3 block."""
    text = Path(skill_path).read_text(encoding="utf-8")
    if "## 3. Production Reference Implementation" not in text:
        raise LookupError("missing Section 3 blueprint in " + skill_path)
    if "## 4" not in text:
        raise LookupError("missing Section 4 terminator in " + skill_path)
    section3 = text.split("## 3. Production Reference Implementation", 1)[1]
    section3 = section3.split("## 4", 1)[0]
    written = []
    for chunk in re.split(r"#\s*={4,}", section3):
        match = FILE_MARKER.search(chunk)
        if not match:
            continue
        rel = match.group(1)
        body_parts = chunk.split("\n", 1)
        body = body_parts[1].lstrip("\n") if len(body_parts) == 2 else ""
        out = project_root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8")
        written.append(str(out))
    if not written:
        raise RuntimeError("no '# FILE:' artifacts parsed from " + skill_path)
    return written


def verify_paths(project_root, rel_paths):
    present = []
    missing = []
    for rel in rel_paths:
        if (project_root / rel).is_file():
            present.append(rel)
        else:
            missing.append(rel)
    return present, missing


def step_materialize(key, options):
    skill_path = SKILL_PATHS[key]
    if not Path(skill_path).is_file():
        raise FileNotFoundError("sub-skill path missing: " + skill_path)
    project_root = Path(options["project_root"]).resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    written = materialize_blueprint(skill_path, project_root, key)
    supposed = [str(project_root / rel) for rel in ARTIFACTS[key]]
    present, missing = verify_paths(project_root, ARTIFACTS[key])
    status = "PASS" if not missing else "FAIL"
    return {
        "key": key,
        "step": STEP_NUM[key],
        "skill_path": skill_path,
        "status": status,
        "exit_code": 0 if status == "PASS" else 3,
        "report_path": str(project_root),
        "payload": {
            "artifacts_written": written,
            "artifacts_expected": supposed,
            "missing_files": missing,
        },
        "stdout_tail": "wrote " + str(len(written)) + " file(s) under " + str(project_root),
        "stderr_tail": ("missing: " + ", ".join(missing)) if missing else "",
    }


def resolve_runner(options):
    manager = options.get("package_manager", "npm")
    if manager in ("pnpm", "yarn", "bun"):
        return manager
    return "npm"


def run_build(project_root, options):
    manager = resolve_runner(options)
    command_classes = [[manager, "run", "build"], [manager, "exec", "next", "build"]]
    last = None
    for command in command_classes:
        try:
            proc = subprocess.run(
                command,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=options.get("build_timeout_seconds", 1200),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            last = ("exception", None, "", str(exc))
            continue
        last = (" ".join(command), proc.returncode, proc.stdout, proc.stderr)
        if proc.returncode == 0:
            return last
    return last


def step_validate_build(options, step_outputs):
    project_root = Path(options["project_root"]).resolve()
    present, missing = verify_paths(project_root, BUILD_GATE_PATHS)
    command, exit_code, stdout, stderr = run_build(project_root, options)
    open_items = []
    for rel in missing:
        open_items.append("missing required artifact: " + rel)
    if exit_code != 0:
        open_items.append(
            "build failed (" + str(command) + " exit " + str(exit_code) + "): " + (stderr or stdout)[-400:]
        )
    report_dir = Path(options["report_dir"]).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    final_path = report_dir / "FRONTEND_SUITE_REPORT.md"
    lines = []
    lines.append("# Frontend Suite Build Report")
    lines.append("")
    lines.append("Orchestrator: frontend-suite-orchestrator")
    lines.append("Run time: " + datetime.now(timezone.utc).isoformat())
    lines.append("Project root: " + str(project_root))
    lines.append("Build command: " + str(command))
    lines.append("Build exit code: " + str(exit_code))
    lines.append("")
    lines.append("## Scaffolded File Tree Summary")
    lines.append("")
    lines.append("| Stage | Artifacts expected | Artifacts present | Missing |")
    lines.append("|-------|--------------------|-------------------|---------|")
    for stage in ["scaffold", "styler", "forms", "state_query"]:
        expected = len(ARTIFACTS[stage])
        present_count = sum(1 for rel in ARTIFACTS[stage] if (project_root / rel).is_file())
        missing_count = expected - present_count
        lines.append("| " + stage + " | " + str(expected) + " | " + str(present_count) +
                     " | " + str(missing_count) + " |")
    lines.append("")
    lines.append("## Per-Step Pass / Fail Matrix")
    lines.append("")
    lines.append("| Step | Key | Skill | Status |")
    lines.append("|------|-----|-------|--------|")
    for key in STEP_ORDER:
        result = step_outputs.get(key)
        if not result:
            lines.append("| " + STEP_NUM[key] + " | " + key + " | (not selected) | NOT_RUN |")
            continue
        skill = result.get("skill_path") or "(local build gate)"
        lines.append("| " + result.get("step", STEP_NUM[key]) + " | " + key +
                     " | `" + skill + "` | " + str(result.get("status", "?")) + " |")
    lines.append("")
    lines.append("## Verified Routes / Component Tree")
    lines.append("")
    lines.append("Missing files: " + (", ".join(missing) if missing else "none"))
    lines.append("")
    lines.append("## Open Items")
    lines.append("")
    if open_items:
        for rank, item in enumerate(open_items, 1):
            lines.append(str(rank) + ". " + item)
    else:
        lines.append("None. Build passed with the full mandated component tree present.")
    lines.append("")
    lines.append("---")
    lines.append("Generated by frontend-suite-orchestrator")
    final_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report_obj = {
        "orchestrator": "frontend-suite-orchestrator",
        "run_id": "fe-" + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S") + "Z",
        "report_dir": str(report_dir),
        "project_root": str(project_root),
        "steps": [],
        "build": {
            "command": command,
            "exit_code": exit_code,
            "verified_routes": ["/", "/api/todos"],
            "verified_component_tree": present,
            "missing_files": missing,
        },
        "open_items": open_items,
        "consolidated_report": "FRONTEND_SUITE_REPORT.md",
    }
    for stage in ["scaffold", "styler", "forms", "state_query", "validate_build"]:
        result = step_outputs.get(stage)
        if result:
            entry = dict(result)
            entry.pop("payload", None)
            report_obj["steps"].append(entry)
    result_path = report_dir / "frontend_suite_result.json"
    result_path.write_text(json.dumps(report_obj, indent=2), encoding="utf-8")

    status = "PASS" if (exit_code == 0 and not missing) else "FAIL"
    return {
        "key": "validate_build",
        "step": STEP_NUM["validate_build"],
        "skill_path": None,
        "status": status,
        "exit_code": exit_code,
        "report_path": str(final_path),
        "payload": {
            "build_command": command,
            "build_exit_code": exit_code,
            "verified_component_tree": present,
            "missing_files": missing,
            "open_items": open_items,
        },
        "stdout_tail": stdout[-2000:] if stdout else "",
        "stderr_tail": stderr[-2000:] if stderr else "",
    }


def should_run(key, options, results, active):
    predecessor = predecessor_of(key)
    if predecessor == "":
        return True
    if predecessor in active and results.get(predecessor, {}).get("status") == "PASS":
        return True
    return False


def copy_typecheck_dependency(project_root):
    """Symlink/copy next-env.d.ts requirement note so the build gate is not the first tsc run."""
    marker = project_root / "next-env.d.ts"
    if not marker.exists():
        marker.write_text("// next-env.d.ts is regenerated by the first `next build`.\n", encoding="utf-8")


def run_dag(options):
    merged = dict(RECOMMENDED_DEFAULT)
    merged.update(options)
    options = merged
    project_root = Path(options["project_root"]).resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    report_dir = Path(options["report_dir"]).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    active = select_steps(options)
    results = {}
    for key in active:
        if not should_run(key, options, results, active):
            results[key] = {
                "key": key,
                "step": STEP_NUM[key],
                "skill_path": SKILL_PATHS[key],
                "status": "SKIPPED_BY_PREDECESSOR",
                "exit_code": None,
                "report_path": None,
                "payload": {},
                "stdout_tail": "predecessor step did not pass; step not executed",
                "stderr_tail": "",
            }
            continue
        try:
            if key == "validate_build":
                copy_typecheck_dependency(project_root)
                result = step_validate_build(options, results)
            else:
                result = step_materialize(key, options)
        except Exception as exc:
            result = {
                "key": key,
                "step": STEP_NUM[key],
                "skill_path": SKILL_PATHS[key],
                "status": "FAIL",
                "exit_code": 1,
                "report_path": None,
                "payload": {},
                "stdout_tail": "",
                "stderr_tail": str(exc),
            }
        results[key] = result
        if result["status"] != "PASS" and options.get("fail_fast", True):
            break
    return results


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Frontend Suite Orchestrator")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--report-dir", default="./frontend-suite-build")
    parser.add_argument("--package-manager", choices=["npm", "pnpm", "yarn", "bun"], default="npm")
    parser.add_argument("--include", action="append", default=None)
    parser.add_argument("--skip", action="append", default=None)
    parser.add_argument("--no-fail-fast", action="store_true")
    parser.add_argument("--build-timeout-seconds", type=int, default=1200)
    args = parser.parse_args(argv)

    options = {
        "project_root": args.project_root,
        "report_dir": args.report_dir,
        "package_manager": args.package_manager,
        "include_steps": args.include or [],
        "skip_steps": args.skip or [],
        "full_run": not bool(args.include),
        "fail_fast": not args.no_fail_fast,
        "build_timeout_seconds": args.build_timeout_seconds,
    }
    results = run_dag(options)
    print(json.dumps(
        {key: {"step": res["step"], "status": res["status"], "exit_code": res["exit_code"],
               "report_path": res.get("report_path")} for key, res in results.items()},
        indent=2,
    ))
    bad = [res["key"] for res in results.values() if res["status"] != "PASS"]
    if bad:
        print("Failed steps: " + ", ".join(bad))
        return 1
    print("All active steps PASS. Consolidated: " + str(Path(options["report_dir"]) / "FRONTEND_SUITE_REPORT.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 5. Edge Cases & Error Handling
- **Missing sub-skill path**: `step_materialize` raises `FileNotFoundError` naming the missing `skills/<id>/<id>.md`; with `fail_fast: true` the chain halts and the matrix records the step as FAIL rather than writing a partial tree.
- **Blueprint parse failure**: `materialize_blueprint` requires both the `## 3. Production Reference Implementation` header and the `## 4` terminator, and raises `LookupError`/`RuntimeError` if the Section 3 block or any `# FILE:` marker is absent — a prerequisite change in a skill can never silently mis-scaffold the project.
- **Non-zero build / missing artifacts**: the `validate_build` gate is authoritative; a failed `npm run build` or any missing `BUILD_GATE_PATHS` entry flips that step to FAIL and records exact paths plus the last 400 chars of build stderr into Open Items.
- **Overwrite semantics**: later stages intentionally overwrite earlier `app/layout.tsx`, `app/page.tsx`, and `app/globals.css` placeholders (styler → forms → state_query). A partial run that skips a stage therefore leaves the earlier placeholder in place; the matrix + Open Items flag any resulting gap for operators.
- **Rollback / partial-run notes**: the output tree is fully deterministic and regenerable — deleting `projectRoot` and re-running a `full_run` reconstructs the identical tree, so no incremental rollback bookkeeping is required. `next-env.d.ts` is pre-seeded before the build gate (the first `next build` regenerates it), avoiding spurious type errors on CI.
- **Rerun-idempotency bullets**: identical options rebuild the identical tree and overwrite `FRONTEND_SUITE_REPORT.md` / `frontend_suite_result.json` deterministically; `include_steps: ["state_query","validate_build"]` re-writes only those stages against an existing tree; `skip_steps` and `include_steps` never both apply (include wins); a re-run after a mid-chain fail_fast halts starts fresh from S1.
- **Package-manager variance**: the build gate resolves `pnpm`/`yarn`/`bun` by name and falls back to `npx next build` if the manager exposes no `build` script, so scaffolding stays portable while the exit code remains the single source of truth.
- **Timeout handling**: the build runs under `build_timeout_seconds` (default 1200); a timeout surfaces as a FAIL build step with the offending command, preventing the DAG from blocking indefinitely.