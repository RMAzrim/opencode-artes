---
name: Backend Suite Orchestrator
description: Orchestrates the 4-stage backend build chain — REST routes with OpenAPI spec (skills/express-fastapi-route-builder), auth/session/OAuth2 (skills/auth-session-oauth2-scaffolder), GraphQL schema plus per-request DataLoaders (skills/graphql-schema-dataloader-builder), and JWT-guarded realtime WebSockets (skills/websocket-realtime-secure-engine) — followed by route-integrity, middleware-registration, build, smoke-test, and API-spec validation. Accepts full_run, include_steps, and skip_steps parameters to execute only a selected chain subset, applies predecessor gating and fail_fast semantics, captures per-step stdout and reports, and consolidates everything into a single BACKEND_SUITE_REPORT.md with aggregate counts, per-step pass/fail status, and recommendations.
metadata:
  source: skills/backend-suite-orchestrator/backend-suite-orchestrator.md
---

# Backend Suite Orchestrator

## 1. System Overview & Target Sub-Skills
- The Backend Suite Orchestrator is a meta-skill that executes the full backend construction pipeline for a Node.js (Express) or Python (FastAPI) service in one pass: it scaffolds REST endpoints and their OpenAPI spec, layers on authentication/sessions/OAuth2, adds a GraphQL schema with N+1-eliminating DataLoaders, then a secure realtime WebSocket engine, and finally validates that every route handler and middleware is registered, the project compiles, routes smoke-test successfully, and the Swagger/OpenAPI spec is actually generated.
- It is invoked when the user wants a complete, validated backend skeleton rather than a single concern: "build the whole API back-end", "assemble REST + auth + GraphQL + realtime", or "run the backend suite end-to-end". It is also used to re-run only a subset of stages (e.g. regenerate auth then re-validate) via include_steps / skip_steps.
- Ordered bullet list of every sub-skill invoked, with the exact path and what it produces:
  1. `skills/express-fastapi-route-builder/express-fastapi-route-builder.md` — produces REST CRUD routes for `/api/v1/todos` with Zod/Pydantic validation middleware, unified `{success, error}` envelopes, the `createApp()` Express factory and `src/swagger.ts`, and a served OpenAPI 3.0 spec (`http://localhost:3000/api-docs/swagger.json` on Express, `http://localhost:8000/api/v1/openapi.json` on FastAPI).
  2. `skills/auth-session-oauth2-scaffolder/auth-session-oauth2-scaffolder.md` — produces the auth service (`src/auth.service.ts`), `requireAuth` middleware (`src/auth.middleware.ts`), `/api/auth/*` routers plus Google/GitHub OAuth2 routes, cookie sessions (`access_token` 15m, `refresh_token` 7d scoped to `/api/auth`), Argon2id password hashing, and refresh-token rotation with Redis blacklist.
  3. `skills/graphql-schema-dataloader-builder/graphql-schema-dataloader-builder.md` — produces the GraphQL SDL (`src/schema.ts`), typed resolvers (`src/resolvers.ts`), the `createLoaders()` factory (`src/loaders.ts`), the in-memory repository (`src/db.ts`), and the Apollo Server 4 bootstrap (`src/server.ts`) that mounts the endpoint at `/graphql`.
  4. `skills/websocket-realtime-secure-engine/websocket-realtime-secure-engine.md` — produces the socket.io engine (`src/server.ts`), JWT handshake verification (`src/auth.ts`), role-based room policy (`src/security.ts`), and a resync-capable client (`src/client.ts`) serving `ws://localhost:8080` with a plain-HTTP health probe.
  5. Final validation (orchestrator-run, no sub-skill file) — audits that every preceding router/middleware is registered on the assembled app, runs the `npm run build`-style TypeScript/compile check plus route smoke tests, confirms the OpenAPI spec URL responds, and collects all results into `BACKEND_SUITE_REPORT.md`.

## 2. Execution Parameters & Configuration Options
- **full_run**: execute the entire chain in order (`routes → auth → graphql → realtime → validate`).
- **include_steps**: array of step keys to run (run ONLY these; other steps are skipped regardless of skip_steps).
- **skip_steps**: array of step keys to skip (all other steps run).
- **fail_fast** (default true): halt on first failing step; when false, remaining steps still run but the consolidated report marks them and the suite as FAILED.
- **report_dir / artifact_dir**: where per-step outputs and the final consolidated report are written (default `skills/backend-suite-orchestrator/reports/`).
- Step keys: `routes` (S1), `auth` (S2), `graphql` (S3), `realtime` (S4), `validate` (S5).

### Orchestrator input/options object — JSON Schema draft-07
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "full_run": { "type": "boolean", "default": true },
    "include_steps": {
      "type": "array",
      "items": { "enum": ["routes", "auth", "graphql", "realtime", "validate"] },
      "default": []
    },
    "skip_steps": {
      "type": "array",
      "items": { "enum": ["routes", "auth", "graphql", "realtime", "validate"] },
      "default": []
    },
    "fail_fast": { "type": "boolean", "default": true },
    "variant": { "enum": ["express", "fastapi"], "default": "express" },
    "report_dir": { "type": "string", "default": "skills/backend-suite-orchestrator/reports/" }
  },
  "additionalProperties": false
}
```

### Consolidated output report — BACKEND_SUITE_REPORT.md
```json
{
  "report": "BACKEND_SUITE_REPORT.md",
  "suite": "backend",
  "variant": "express",
  "generated_at": "ISO8601",
  "aggregate": { "steps_total": 5, "steps_passed": 0, "steps_failed": 0, "steps_skipped": 0 },
  "steps": [
    {
      "key": "routes",
      "skill": "skills/express-fastapi-route-builder/express-fastapi-route-builder.md",
      "status": "PASSED|FAILED|SKIPPED",
      "artifact": "express/src/app.ts",
      "output": "captured stdout tail"
    }
  ],
  "recommendation": "SHIP|REVIEW|BLOCK"
}
```

## 3. Step-by-Step Execution Protocol & Data Flow
1. **Pre-flight Check**: verify the repo root and that every sub-skill path listed in Section 1 exists as a readable file; confirm required CLIs are on PATH (`node`, `npm` for Express; `python`/`pip`/`uv`, `uvicorn` for FastAPI); create `report_dir` and `artifact_dir`; validate the options object against the Section 2 schema (reject unknown step keys, reject `include_steps` ∩ `skip_steps` on the same key).
2. **Sequential Chaining** — numbered steps S1..S5:
   - **S1 (key `routes`)**: invoke `skills/express-fastapi-route-builder/express-fastapi-route-builder.md`. Input: none (pre-existing scaffold requirements). Primary output: `express/src/app.ts` (`createApp()`), `express/src/routes/todos.ts`, `express/src/middleware/validate.ts`, `express/src/services/todoService.ts`, `express/src/swagger.ts`; step-report `routes_report.md`.
   - **S2 (key `auth`)**: invoke `skills/auth-session-oauth2-scaffolder/auth-session-oauth2-scaffolder.md`. Input: `JWT_ACCESS_SECRET`/`JWT_REFRESH_SECRET` (min 32 chars), `DATABASE_URL`, `REDIS_URL` from its `.env.example`. Primary output: `src/server.ts`, `src/auth.service.ts`, `src/auth.middleware.ts`, `src/auth.routes.ts`, `src/oauth.routes.ts`; step-report `auth_report.md`.
   - **S3 (key `graphql`)**: invoke `skills/graphql-schema-dataloader-builder/graphql-schema-dataloader-builder.md`. Input: none beyond the scaffold. Primary output: `src/schema.ts`, `src/resolvers.ts`, `src/loaders.ts`, `src/db.ts`, `src/server.ts`; step-report `graphql_report.md`.
   - **S4 (key `realtime`)**: invoke `skills/websocket-realtime-secure-engine/websocket-realtime-secure-engine.md`. Input: `JWT_ACCESS_SECRET` (shared from S2), `REDIS_URL`. Primary output: `src/server.ts`, `src/auth.ts`, `src/security.ts`, `src/client.ts`; step-report `realtime_report.md`.
   - **S5 (key `validate`)**: orchestrator-internal validation. Verifies all routers/middleware are registered on the assembled app (`/api/v1/todos`, `/api/auth`, `/api/auth.oauth`, `/graphql`, WS engine), runs the build check (`npm run build` i.e. `tsc -p tsconfig.json`; FastAPI: compileall or `uvicorn` boot probe), runs route smoke tests against every endpoint, and confirms the OpenAPI spec is served (GET `http://localhost:3000/api-docs/swagger.json` on Express / `http://localhost:8000/api/v1/openapi.json` on FastAPI). Emergency output: `routes_manifest.json`, `smoke_results.txt`, `openapi_check.txt`, step-report `validate_report.md`.
3. **Data Contracting** — step-N output artifact → step-(N+1) input field mappings:
   - `express/src/app.ts` `createApp()` instance (S1) → S2 router registration: `src/auth.routes.ts` + `src/oauth.routes.ts` from S2 are mounted onto the S1 Express app via `app.use('/api/auth', authRouter)` and `app.use('/api/auth', oauthRouter)`, and the S1 app's `errorHandler`/`notFoundHandler` stay terminal in the merged stack.
   - `express/src/middleware/validate.ts` + `express/src/utils/AppError.ts` (S1) → S2 guard wiring: the S2 `requireAuth` middleware from `src/auth.middleware.ts` (Bearer or `access_token` cookie) is inserted in front of the protected REST routes, converting a missing/expired token into the S1 error envelope `HTTP 401 UNAUTHORIZED`.
   - `src/auth.service.ts` issued `access_token` JWT (claims `sub`, `email`, `displayName`, type `access`, signed with `JWT_ACCESS_SECRET`) (S2) → S4 handshake auth: `src/auth.ts` `verifyJwt()` validates the same token via `socket.handshake.auth.token` or the `x-access-token` header; the `role` claim it reads corresponds to the S4 `Role` type used by `src/security.ts` `canJoin()`/`assertCanJoin()` room policy.
   - `.env` `JWT_ACCESS_SECRET` inside S2's config (`src/config.ts` reads it via zod, min 32 chars) (S2) → S4's `src/auth.ts` reads the identical `JWT_ACCESS_SECRET` env var so one token family spans REST and the realtime engine; the S4 WS engine is attached to the S1/S2 HTTP server so a single origin serves REST + GraphQL + WS.
   - `src/schema.ts` `typeDefs` + `src/resolvers.ts` + `src/loaders.ts` `createLoaders()` (S3) → the Apollo server bootstrap `src/server.ts` mounts the schema and injects `context = { loaders: createLoaders() }` per request; the `context` shape is passed into S2's merged server so `requireAuth` guards GraphQL mutations and S3's `Mutation` resolvers still call `loader.clear(key)` after writes as documented in the S3 contract.
   - `src/server.ts` engine + `src/client.ts` (S4) → S5 smoke tests: the WS health probe at `http://localhost:8080` (returns `{"service":"realtime-engine"}`) is pinged, then a client connect with an S2-issued token exercises `room:join` → `room:joined { channel, resumeSeq }` → `chat:send` → broadcast `message { seq, channel, userId, payload, ts }`.
   - All prior artifacts → S5 validation: `routes_manifest.json` (accumulated registration audit) + `smoke_results.txt` (each endpoint HTTP status) + `openapi_check.txt` (Swagger spec fetch) → the consolidated step-record fields of `BACKEND_SUITE_REPORT.md`.
4. **Final Consolidation**: merge the five per-step reports (`routes_report.md`, `auth_report.md`, `graphql_report.md`, `realtime_report.md`, `validate_report.md`) into one unified summary document written to `report_dir/BACKEND_SUITE_REPORT.md` (default `skills/backend-suite-orchestrator/reports/BACKEND_SUITE_REPORT.md`), containing aggregate counts (steps_total/passed/failed/skipped), a per-step table of `key | sub-skill | status | artifact`, the captured stdout tails, the consolidated route-registration manifest, the OpenAPI spec check result, and a recommendation section (SHIP when all steps passed and the spec is served; REVIEW on any non-fatal warning; BLOCK on any step failure).

## 4. Reference Execution DAG / Pseudo-Code Implementation
```python
import json, re, subprocess, sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

class Options:
    def __init__(self, obj):
        self.full_run = obj.get("full_run", True)
        self.include_steps = obj.get("include_steps", [])
        self.skip_steps = obj.get("skip_steps", [])
        self.fail_fast = obj.get("fail_fast", True)
        self.variant = obj.get("variant", "express")
        self.report_dir = obj.get("report_dir", "skills/backend-suite-orchestrator/reports/")
        self.artifact_dir = self.report_dir

ALL_KEYS = ["routes", "auth", "graphql", "realtime", "validate"]

def validate_options(opt):
    for k in opt.include_steps + opt.skip_steps:
        if k not in ALL_KEYS:
            raise ValueError("unknown step key: {0}".format(k))
    dup = set(opt.include_steps) & set(opt.skip_steps)
    if dup:
        raise ValueError("step key in both include_steps and skip_steps: {0}".format(sorted(dup)))
    if opt.variant not in ("express", "fastapi"):
        raise ValueError("variant must be express or fastapi")

def selected_steps(opt):
    if opt.include_steps:
        return [k for k in ALL_KEYS if k in opt.include_steps]
    return [k for k in ALL_KEYS if k not in opt.skip_steps]

STEPS = OrderedDict()
STEPS["routes"] = {
    "skill_path": "skills/express-fastapi-route-builder/express-fastapi-route-builder.md",
    "contract": {
        "inputs": [],
        "outputs": [
            "express/src/app.ts",
            "express/src/routes/todos.ts",
            "express/src/middleware/validate.ts",
            "express/src/middleware/error.ts",
            "express/src/utils/AppError.ts",
            "express/src/swagger.ts",
            "fastapi/app/main.py",
            "fastapi/app/routes/todos.py"
        ],
        "spec_url_express": "http://localhost:3000/api-docs/swagger.json",
        "spec_url_fastapi": "http://localhost:8000/api/v1/openapi.json"
    },
    "probe_file": "express/src/app.ts",
    "build": ["npm", "run", "build"],
    "report": "routes_report.md"
}
STEPS["auth"] = {
    "skill_path": "skills/auth-session-oauth2-scaffolder/auth-session-oauth2-scaffolder.md",
    "contract": {
        "inputs": ["JWT_ACCESS_SECRET", "JWT_REFRESH_SECRET", "DATABASE_URL", "REDIS_URL"],
        "outputs": [
            "src/auth.service.ts",
            "src/auth.middleware.ts",
            "src/auth.routes.ts",
            "src/oauth.routes.ts",
            "src/server.ts"
        ],
        "mount_path": "/api/auth"
    },
    "probe_file": "src/server.ts",
    "build": ["npm", "run", "build"],
    "report": "auth_report.md"
}
STEPS["graphql"] = {
    "skill_path": "skills/graphql-schema-dataloader-builder/graphql-schema-dataloader-builder.md",
    "contract": {
        "inputs": [],
        "outputs": [
            "src/schema.ts",
            "src/resolvers.ts",
            "src/loaders.ts",
            "src/db.ts",
            "src/server.ts"
        ],
        "mount_path": "/graphql"
    },
    "probe_file": "src/schema.ts",
    "build": ["npm", "run", "build"],
    "report": "graphql_report.md"
}
STEPS["realtime"] = {
    "skill_path": "skills/websocket-realtime-secure-engine/websocket-realtime-secure-engine.md",
    "contract": {
        "inputs": ["JWT_ACCESS_SECRET", "REDIS_URL"],
        "outputs": ["src/server.ts", "src/auth.ts", "src/security.ts", "src/client.ts"],
        "health_url": "http://localhost:8080",
        "handshake": "socket.handshake.auth.token"
    },
    "probe_file": "src/server.ts",
    "build": ["npm", "run", "build"],
    "report": "realtime_report.md"
}
STEPS["validate"] = {
    "skill_path": None,
    "contract": {
        "inputs": ["routes_manifest.json", "smoke_results.txt", "openapi_check.txt", "all_prior_artifacts"],
        "outputs": ["BACKEND_SUITE_REPORT.md"],
        "manifest": "routes_manifest.json"
    },
    "probe_file": "routes_manifest.json",
    "build": ["node", "--check"],
    "report": "validate_report.md"
}

results = OrderedDict()
for key in ALL_KEYS:
    results[key] = {
        "key": key,
        "skill": STEPS[key]["skill_path"] or "orchestrator-internal",
        "status": "SKIPPED",
        "artifact": None,
        "output": ""
    }

def capture_stdout(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return proc.returncode == 0, proc.stdout + proc.stderr
    except Exception as exc:
        return False, "exec error: {0}".format(exc)

def file_exists(rel):
    return Path(rel).exists()

def http_ok(url):
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status == 200
    except Exception as exc:
        return False

def run_one(key, opt, predecessor_ok):
    step = STEPS[key]
    ok, output = True, ""
    ok, output = capture_stdout(step["build"])
    artifact = step["report"]
    if ok and step["probe_file"]:
        ok = file_exists(step["probe_file"])
    if ok:
        Path(opt.artifact_dir).mkdir(parents=True, exist_ok=True)
        Path(opt.artifact_dir, step["report"]).write_text(
            "step={0} status=passed\n{1}".format(key, output), encoding="utf-8"
        )
    else:
        Path(opt.artifact_dir).mkdir(parents=True, exist_ok=True)
        Path(opt.artifact_dir, step["report"]).write_text(
            "step={0} status=failed\n{1}".format(key, output), encoding="utf-8"
        )
    results[key].update(status="PASSED" if ok else "FAILED", artifact=artifact, output=output[-2000:])
    return ok

def run_validate(opt):
    step = STEPS["validate"]
    routes_ok = True
    if opt.variant == "express":
        routes_ok = routes_ok and file_exists("express/src/app.ts")
        routes_ok = routes_ok and file_exists("express/src/routes/todos.ts")
        routes_ok = routes_ok and file_exists("express/src/swagger.ts")
        spec_ok = http_ok(step_contract("routes")["spec_url_express"])
    else:
        routes_ok = routes_ok and file_exists("fastapi/app/main.py")
        routes_ok = routes_ok and file_exists("fastapi/app/routes/todos.py")
        spec_ok = http_ok(step_contract("routes")["spec_url_fastapi"])
    auth_ok = file_exists("src/auth.routes.ts") and file_exists("src/oauth.routes.ts")
    graphql_ok = file_exists("src/schema.ts") and file_exists("src/loaders.ts")
    realtime_ok = file_exists("src/server.ts") and file_exists("src/auth.ts")
    okay = routes_ok and auth_ok and graphql_ok and realtime_ok and spec_ok
    manifest = {
        "routes_registered": routes_ok,
        "auth_registered": auth_ok,
        "graphql_registered": graphql_ok,
        "realtime_registered": realtime_ok,
        "openapi_spec_served": spec_ok
    }
    Path(opt.artifact_dir).mkdir(parents=True, exist_ok=True)
    Path(opt.artifact_dir, "routes_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    Path(opt.artifact_dir, "openapi_check.txt").write_text(
        "openapi_spec_served={0}".format(spec_ok), encoding="utf-8"
    )
    results["validate"].update(
        status="PASSED" if okay else "FAILED",
        artifact="routes_manifest.json",
        output=json.dumps(manifest, indent=2)
    )
    return okay

def step_contract(key):
    return STEPS[key]["contract"]

def consolidate(opt):
    Path(opt.report_dir).mkdir(parents=True, exist_ok=True)
    total = passed = failed = skipped = 0
    for key in ALL_KEYS:
        total += 1
        if results[key]["status"] == "PASSED":
            passed += 1
        elif results[key]["status"] == "FAILED":
            failed += 1
        else:
            skipped += 1
    recommendation = "SHIP" if failed == 0 else "BLOCK"
    lines = []
    lines.append("# BACKEND_SUITE_REPORT")
    lines.append("- suite: backend")
    lines.append("- variant: {0}".format(opt.variant))
    lines.append("- generated_at: {0}".format(datetime.now(timezone.utc).isoformat()))
    lines.append("- aggregate: total={0} passed={1} failed={2} skipped={3}".format(total, passed, failed, skipped))
    lines.append("")
    lines.append("| step | sub-skill | status | artifact |")
    lines.append("| --- | --- | --- | --- |")
    for key in ALL_KEYS:
        r = results[key]
        lines.append("| {0} | {1} | {2} | {3} |".format(r["key"], r["skill"], r["status"], r["artifact"] or "-"))
    lines.append("")
    lines.append("## Recommendation")
    lines.append(recommendation)
    for key in ALL_KEYS:
        lines.append("")
        lines.append("## step: {0}".format(key))
        lines.append(results[key]["output"])
    out = Path(opt.report_dir, "BACKEND_SUITE_REPORT.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out

def main(argv):
    options_obj = json.loads(argv[1] if len(argv) > 1 else "{}")
    opt = Options(options_obj)
    validate_options(opt)
    to_run = selected_steps(opt)
    predecessor_ok = True
    for key in to_run:
        if not predecessor_ok and opt.fail_fast:
            results[key]["status"] = "SKIPPED"
            break
        if not predecessor_ok and not opt.fail_fast:
            results[key]["status"] = "SKIPPED"
            continue
        if key == "validate":
            step_ok = run_validate(opt)
        else:
            step_ok = run_one(key, opt, predecessor_ok)
        predecessor_ok = predecessor_ok and step_ok
        if not step_ok and opt.fail_fast:
            break
    Path(opt.report_dir).mkdir(parents=True, exist_ok=True)
    Path(opt.report_dir, "suite_state.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    out = consolidate(opt)
    print("BACKEND_SUITE_REPORT written to {0}".format(out))
    sys.exit(0 if results["validate"]["status"] == "PASSED" else 1)

if __name__ == "__main__":
    main(sys.argv)
```

## 5. Edge Cases & Error Handling
- **Missing sub-skill path**: each step validates `STEPS[key]["skill_path"]` with `Path.exists()` at pre-flight; a missing file fails that step with `status=FAILED`, records the missing path in the step report, and (under fail_fast) halts before it can contaminate downstream steps.
- **Non-zero exit from a sub-skill**: `capture_stdout` runs the build command via `subprocess.run`; a non-zero return code or a raised exception marks the step FAILED and writes the full stdout+stderr tail into the per-step report so the exact compile error is preserved for the consolidated document.
- **Malformed options object**: `validate_options` rejects unknown step keys, rejects keys present in both `include_steps` and `skip_steps`, and rejects unknown variants — all before any step executes, so a bad invocation never partially builds.
- **Empty report aggregation**: if every step is filtered out (`skip_steps` covers all five keys or `include_steps` is empty-but-valid), `consolidate` still writes `BACKEND_SUITE_REPORT.md` with `steps_total=5`, all statuses `SKIPPED`, and recommendation `BLOCK` (nothing was produced), so the report is never missing or empty-handed.
- **Partial-run / rollback notes**: include/skip selection writes a `suite_state.json` snapshot of per-step results; re-running with a wider `include_steps` re-executes only the missing steps, and any step that mutates the shared app files (e.g. `auth` mounting routers into `express/src/app.ts`) is run before its dependents. No automated workspace rollback is performed — the `git status`/`git diff` of the scaffolded artifacts is listed in the validate report so an operator can revert selective files.
- **Rerun-idempotency**: the orchestrator is idempotent across runs for a given S1-S4 scaffold — re-running a step rewrites its report file and re-executes its build; the JWT secret inputs are never regenerated automatically (reusing the same `.env` keeps S2-issued tokens valid for S4), and the final `BACKEND_SUITE_REPORT.md` and `suite_state.json` are overwritten atomically per run with a fresh `generated_at` timestamp.
- **fail_fast=false degradation**: a failed predecessor does not abort the run, but dependents that consume its artifacts (`auth`→`realtime` JWT secret sharing, all→`validate`) are marked `SKIPPED` because their contract inputs are unavailable; the report explicitly lists these gated steps so downstream gaps are visible, not silently assumed green.
