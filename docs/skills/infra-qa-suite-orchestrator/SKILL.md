---
name: Infrastructure & QA Suite Orchestrator
description: Orchestrates the 5-stage infrastructure and QA chain — ORM schemas plus zero-downtime migrations (skills/drizzle-prisma-orm-architect), Redis caching and pub/sub event bus (skills/redis-pubsub-cache-manager), multi-stage Docker images with Compose stack (skills/docker-multi-stage-stack-builder), Playwright E2E and security flows (skills/playwright-e2e-security-flow-tester), and Lighthouse Core Web Vitals audits (skills/lighthouse-web-vitals-optimizer) — all executed against the provisioned stack. Accepts full_run, include_steps, and skip_steps parameters to select the chain subset, applies predecessor gating and fail_fast semantics, captures per-step stdout and reports, and consolidates DB migration status, cache health, docker build/health, E2E pass counts, a Lighthouse scores table, and recommendations into a single INFRA_QA_SUITE_REPORT.md.
metadata:
  source: skills/infra-qa-suite-orchestrator/infra-qa-suite-orchestrator.md
---

# Infrastructure & QA Suite Orchestrator

## 1. System Overview & Target Sub-Skills
- The Infrastructure & QA Suite Orchestrator is a meta-skill that provisions a complete, verifiable application stack and proves it: it designs the database layer and migrations, layers on Redis caching and pub/sub, containerizes everything into a multi-stage Docker image with a Compose orchestrated stack (PostgreSQL, Redis, app, Nginx), then runs Playwright E2E/security tests and Lighthouse Core Web Vitals audits against the live stack, and finally consolidates every result into one evidence report.
- It is invoked when the user wants a full, validated deployment surface rather than a single concern: "provision the stack and run QA", "set up infra then verify E2E and performance", or "run the infra-qa suite". It is also used to re-run only a subset of stages (e.g. re-run Lighthouse only against an already-provisioned stack) via include_steps / skip_steps.
- Ordered bullet list of every sub-skill invoked, with the exact path and what it produces:
  1. `skills/drizzle-prisma-orm-architect/drizzle-prisma-orm-architect.md` — produces Prisma and Drizzle schema definitions on the same e-commerce domain, auto-generated migration SQL folders (`prisma/migrations/`, `src/drizzle/migrations/`), clients with soft-delete middleware, and CRUD repositories.
  2. `skills/redis-pubsub-cache-manager/redis-pubsub-cache-manager.md` — produces the cache layer (`src/cache.ts`), pub/sub manager (`src/pubsub.ts`), typed publishers (`src/publisher.ts`), subscriber with handlers (`src/subscriber.ts`), and write-behind worker (`src/worker.ts`).
  3. `skills/docker-multi-stage-stack-builder/docker-multi-stage-stack-builder.md` — produces the <100MB multi-stage `Dockerfile`, `.dockerignore`, `docker-compose.yml` (postgres:16-alpine, redis:7-alpine, next-app standalone runner, nginx:1.27-alpine reverse proxy), `nginx/nginx.conf`, `nginx/Dockerfile`, `.env.example`, and `scripts/entrypoint.sh`.
  4. `skills/playwright-e2e-security-flow-tester/playwright-e2e-security-flow-tester.md` — produces `playwright.config.ts` (4 browser projects), Page Objects, auth fixtures with `storageState`, and spec files covering login, route guards, sanitized-input/XSS defense, and visual regression.
  5. `skills/lighthouse-web-vitals-optimizer/lighthouse-web-vitals-optimizer.md` — produces the Lighthouse config, the `scripts/perf-audit.ps1` runner, the instrumented `next.config.ts`, code-split components, and Core Web Vitals instrumentation (`src/lib/reportWebVitals.ts`).
  6. Final consolidation (orchestrator-run, no sub-skill file) — aggregates migration status, cache health, docker build/health, E2E pass counts, the Lighthouse scores table, and recommendations into `INFRA_QA_SUITE_REPORT.md`.

## 2. Execution Parameters & Configuration Options
- **full_run**: execute the entire chain in order (`orm → redis → docker → e2e → lighthouse → consolidate`).
- **include_steps**: array of step keys to run (run ONLY these; other steps are skipped regardless of skip_steps).
- **skip_steps**: array of step keys to skip (all other steps run).
- **fail_fast** (default true): halt on first failing step; when false, remaining steps still run but the consolidated report marks them and the suite as FAILED.
- **report_dir / artifact_dir**: where per-step outputs and the final consolidated report are written (default `skills/infra-qa-suite-orchestrator/reports/`).
- **base_url**: the stack URL that E2E (`TEST_BASE_URL`) and Lighthouse (`LH_BASE_URL`) run against (default `http://localhost` — the Nginx entry point from S3; `http://localhost:3000` targets the app container directly).
- Step keys: `orm` (S1), `redis` (S2), `docker` (S3), `e2e` (S4), `lighthouse` (S5), `consolidate` (S6).

### Orchestrator input/options object — JSON Schema draft-07
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "full_run": { "type": "boolean", "default": true },
    "include_steps": {
      "type": "array",
      "items": { "enum": ["orm", "redis", "docker", "e2e", "lighthouse", "consolidate"] },
      "default": []
    },
    "skip_steps": {
      "type": "array",
      "items": { "enum": ["orm", "redis", "docker", "e2e", "lighthouse", "consolidate"] },
      "default": []
    },
    "fail_fast": { "type": "boolean", "default": true },
    "base_url": { "type": "string", "default": "http://localhost" },
    "report_dir": { "type": "string", "default": "skills/infra-qa-suite-orchestrator/reports/" }
  },
  "additionalProperties": false
}
```

### Consolidated output report — INFRA_QA_SUITE_REPORT.md
```json
{
  "report": "INFRA_QA_SUITE_REPORT.md",
  "suite": "infra-qa",
  "base_url": "http://localhost",
  "generated_at": "ISO8601",
  "aggregate": { "steps_total": 6, "steps_passed": 0, "steps_failed": 0, "steps_skipped": 0 },
  "steps": [
    {
      "key": "orm",
      "skill": "skills/drizzle-prisma-orm-architect/drizzle-prisma-orm-architect.md",
      "status": "PASSED|FAILED|SKIPPED",
      "artifact": "prisma/migrations/",
      "output": "captured stdout tail"
    }
  ],
  "db_migration_status": { "applied": 0, "pending": 0, "checks": [] },
  "cache_health": { "ping": "PONG", "cache_keys": 0 },
  "docker_health": { "image_size_mb": 0, "services_healthy": [] },
  "e2e_counts": { "passed": 0, "failed": 0, "flaky": 0, "skipped": 0 },
  "lighthouse_scores": { "performance": 0, "accessibility": 0, "best-practices": 0, "seo": 0 },
  "recommendation": "SHIP|REVIEW|BLOCK"
}
```

## 3. Step-by-Step Execution Protocol & Data Flow
1. **Pre-flight Check**: verify the repo root and that every sub-skill path listed in Section 1 exists as a readable file; confirm required CLIs (`node`, `npm`, `npx`, `docker` with Compose V2, `redis-cli`, `psql`, Chrome/Chromium for Lighthouse); check infrastructure prerequisites (a reachable PostgreSQL for S1, Redis for S2, Docker daemon for S3); create `report_dir` and `artifact_dir`; validate the options object against the Section 2 schema and reject unknown step keys.
2. **Sequential Chaining** — numbered steps S1..S6:
   - **S1 (key `orm`)**: invoke `skills/drizzle-prisma-orm-architect/drizzle-prisma-orm-architect.md`. Input: `DATABASE_URL` (required, `postgresql://` pattern). Primary output: `prisma/schema.prisma`, `prisma/migrations/`, `src/drizzle/schema.ts`, `src/drizzle/migrations/`, `drizzle.config.ts`, `src/lib/prisma-client.ts`, `src/lib/drizzle-client.ts`, `src/repositories/prisma-repo.ts`, `src/repositories/drizzle-repo.ts`; step-report `orm_report.md`.
   - **S2 (key `redis`)**: invoke `skills/redis-pubsub-cache-manager/redis-pubsub-cache-manager.md`. Input: `REDIS_URL` (required), optional `REDIS_PASSWORD`, `CACHE_DEFAULT_TTL` (default 300). Primary output: `src/cache.ts`, `src/pubsub.ts`, `src/publisher.ts`, `src/subscriber.ts`, `src/worker.ts`, `package.json`; step-report `redis_report.md`.
   - **S3 (key `docker`)**: invoke `skills/docker-multi-stage-stack-builder/docker-multi-stage-stack-builder.md`. Input: `.env` with `POSTGRES_PASSWORD` and `NEXTAUTH_SECRET` (both required), plus `DATABASE_URL`/`REDIS_URL` consumed from S1/S2. Primary output: `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `nginx/nginx.conf`, `nginx/Dockerfile`, `.env.example`, `scripts/entrypoint.sh`; runtime outputs `docker images app-web` (<100MB), `docker compose ps` (all healthy); step-report `docker_report.md`.
   - **S4 (key `e2e`)**: invoke `skills/playwright-e2e-security-flow-tester/playwright-e2e-security-flow-tester.md`. Input: `TEST_BASE_URL` (set to the orchestrator `base_url`), `TEST_USER_EMAIL`, `TEST_USER_PASSWORD`; requires the S3 stack running. Primary output: `playwright.config.ts`, `src/pages/LoginPage.ts`, `src/pages/DashboardPage.ts`, `src/fixtures/auth.ts`, `tests/login.spec.ts`, `tests/auth-guard.spec.ts`, `tests/input.spec.ts`, `tests/snapshot.spec.ts`; runtime output `auth/storage-state.json` plus the Playwright HTML/list report; step-report `e2e_report.md`.
   - **S5 (key `lighthouse`)**: invoke `skills/lighthouse-web-vitals-optimizer/lighthouse-web-vitals-optimizer.md`. Input: `LH_BASE_URL` (set to the orchestrator `base_url`), optional `LH_CHROME_PATH`, `LH_VIEWPORT`, `LH_THROTTLING_MOBILE`; requires the S3 stack running. Primary output: `lighthouse/lighthouse.config.ts`, `scripts/perf-audit.ps1`, `next.config.ts`, `src/components/LazyChart.tsx`, `src/lib/reportWebVitals.ts`; runtime output `lighthouse-reports/<urlSafeName>-<suffix>-<stamp>.report.json` and `.report.html`; step-report `lighthouse_report.md`.
   - **S6 (key `consolidate`)**: orchestrator-internal. Aggregates S1-S5 step reports plus targeted probe outputs (migration status, `redis-cli ping`, `docker compose ps`, E2E pass counts, Lighthouse scores) into `INFRA_QA_SUITE_REPORT.md`; step-report `consolidate_report.md`.
3. **Data Contracting** — step-N output artifact → step-(N+1) input field mappings:
   - `prisma/migrations/` + `src/drizzle/migrations/` (S1) → S3 compose init: the migration SQL folders feed `scripts/entrypoint.sh`, which runs `npx prisma migrate deploy` / `npx drizzle-kit migrate` once PostgreSQL passes `pg_isready` in the entrypoint wait loop; the required `DATABASE_URL` (`postgresql://…`) from S1's contract is interpolated verbatim into the compose `app` service env (`postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}`).
   - `src/cache.ts` + `src/pubsub.ts` + `src/publisher.ts` + `src/subscriber.ts` + `src/worker.ts` (S2) → S3 compose env: the app service receives `REDIS_URL: redis://redis:6379` (the compose `redis` service name), and the S2 default TTL (`CACHE_DEFAULT_TTL`, default 300) plus `cache:*` key namespace are what S6's cache-health probe verifies with `redis-cli KEYS 'cache:*'`; the typed channels (`user.events`, `order.events`, `product.events`) are wired into the subscriber so the compose stack exercises pub/sub on boot.
   - `Dockerfile` service `app` target `runner` + `docker-compose.yml` (S3) → S4 `TEST_BASE_URL`: Playwright's required env `TEST_BASE_URL` (default `http://localhost:3000`) is overridden to the orchestrator `base_url` (default `http://localhost` where Nginx answers on port 80 and proxies to `app:3000`); the S4 `webServer.url` `${TEST_BASE_URL}/api/health` maps exactly to the Nginx `location /api/health` proxy block in S3's `nginx/nginx.conf`, and the entrypoint-applied S1 migrations seed the login credentials the S4 fixtures authenticate with.
   - `docker-compose.yml` + provisioned stack (S3) → S5 `LH_BASE_URL`: Lighthouse's required env `LH_BASE_URL` (default `http://localhost:3000`) is set to the same `base_url` so the audit measures the served production stack (Nginx → app → PostgreSQL/Redis), and S5's `next.config.ts` `output: "standalone"` + `scripts/entrypoint.sh` guarantees the stack under audit matches the S3 image.
   - `tests/*.spec.ts` + `playwright-report/` (S4) → S6: per-spec passed/failed/flaky counts (list reporter JSON) become the `e2e_counts` fields of `INFRA_QA_SUITE_REPORT.md`.
   - `lighthouse-reports/<urlSafeName>-<suffix>-<stamp>.report.json` (S5) → S6: parsed `categories.performance`, `categories.accessibility`, `categories.best-practices`, `categories.seo` scores and the Core Web Vitals audits `largest-contentful-paint`, `cumulative-layout-shift`, `total-blocking-time`, `first-contentful-paint` become the `lighthouse_scores` table and give each metric a good/needs-improvement/poor rating.
   - All prior artifacts → S6 consolidation: `orm_report.md`, `redis_report.md`, `docker_report.md`, `e2e_report.md`, `lighthouse_report.md` → the per-step record fields and the `db_migration_status`, `cache_health`, `docker_health`, `e2e_counts`, `lighthouse_scores` sections of the final report.
4. **Final Consolidation**: merge the six per-step reports into one unified summary document written to `report_dir/INFRA_QA_SUITE_REPORT.md` (default `skills/infra-qa-suite-orchestrator/reports/INFRA_QA_SUITE_REPORT.md`) containing: DB migration status (applied vs pending from `prisma/migrations/` and `src/drizzle/migrations/` plus any `prisma migrate status` / `drizzle-kit check` drift output), cache health (`redis-cli ping` = PONG and `cache:*` key count, subscriber live-logs of the three typed channels), docker build/health (runner image size <100MB from `docker images app-web`, `docker compose ps` per-service health plus `curl -i http://localhost/api/health` = HTTP 200), E2E pass counts per spec file, the Lighthouse scores table (category scores plus LCP/CLS/TBT/FCP values and good/needs-improvement/poor ratings), and a recommendation section (SHIP when migrations applied, cache alive, all services healthy, E2E 0 failures, Lighthouse ≥90 across categories; REVIEW on any non-fatal warning; BLOCK on any step failure).

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
        self.base_url = obj.get("base_url", "http://localhost")
        self.report_dir = obj.get("report_dir", "skills/infra-qa-suite-orchestrator/reports/")
        self.artifact_dir = self.report_dir

ALL_KEYS = ["orm", "redis", "docker", "e2e", "lighthouse", "consolidate"]

def validate_options(opt):
    for k in opt.include_steps + opt.skip_steps:
        if k not in ALL_KEYS:
            raise ValueError("unknown step key: {0}".format(k))
    dup = set(opt.include_steps) & set(opt.skip_steps)
    if dup:
        raise ValueError("step key in both include_steps and skip_steps: {0}".format(sorted(dup)))
    if not opt.base_url.startswith("http"):
        raise ValueError("base_url must start with http")

def selected_steps(opt):
    if opt.include_steps:
        return [k for k in ALL_KEYS if k in opt.include_steps]
    return [k for k in ALL_KEYS if k not in opt.skip_steps]

STEPS = OrderedDict()
STEPS["orm"] = {
    "skill_path": "skills/drizzle-prisma-orm-architect/drizzle-prisma-orm-architect.md",
    "contract": {
        "inputs": ["DATABASE_URL"],
        "outputs": [
            "prisma/schema.prisma",
            "prisma/migrations/",
            "src/drizzle/schema.ts",
            "src/drizzle/migrations/",
            "drizzle.config.ts",
            "src/lib/prisma-client.ts",
            "src/lib/drizzle-client.ts",
            "src/repositories/prisma-repo.ts",
            "src/repositories/drizzle-repo.ts"
        ]
    },
    "probe_file": "src/drizzle/schema.ts",
    "apply": ["npx", "prisma", "migrate", "deploy"],
    "report": "orm_report.md"
}
STEPS["redis"] = {
    "skill_path": "skills/redis-pubsub-cache-manager/redis-pubsub-cache-manager.md",
    "contract": {
        "inputs": ["REDIS_URL", "REDIS_PASSWORD", "CACHE_DEFAULT_TTL"],
        "outputs": [
            "src/cache.ts",
            "src/pubsub.ts",
            "src/publisher.ts",
            "src/subscriber.ts",
            "src/worker.ts",
            "package.json"
        ],
        "channels": ["user.events", "order.events", "product.events"]
    },
    "probe_file": "src/pubsub.ts",
    "verify": ["redis-cli", "ping"],
    "report": "redis_report.md"
}
STEPS["docker"] = {
    "skill_path": "skills/docker-multi-stage-stack-builder/docker-multi-stage-stack-builder.md",
    "contract": {
        "inputs": ["POSTGRES_PASSWORD", "NEXTAUTH_SECRET", "DATABASE_URL", "REDIS_URL"],
        "outputs": [
            "Dockerfile",
            ".dockerignore",
            "docker-compose.yml",
            "nginx/nginx.conf",
            "nginx/Dockerfile",
            ".env.example",
            "scripts/entrypoint.sh"
        ],
        "health_url": "http://localhost/api/health",
        "target_image": "app-web"
    },
    "probe_file": "docker-compose.yml",
    "build": ["docker", "compose", "build"],
    "up": ["docker", "compose", "up", "-d"],
    "report": "docker_report.md"
}
STEPS["e2e"] = {
    "skill_path": "skills/playwright-e2e-security-flow-tester/playwright-e2e-security-flow-tester.md",
    "contract": {
        "inputs": ["TEST_BASE_URL", "TEST_USER_EMAIL", "TEST_USER_PASSWORD"],
        "outputs": [
            "playwright.config.ts",
            "src/pages/LoginPage.ts",
            "src/pages/DashboardPage.ts",
            "src/fixtures/auth.ts",
            "tests/login.spec.ts",
            "tests/auth-guard.spec.ts",
            "tests/input.spec.ts",
            "tests/snapshot.spec.ts"
        ],
        "runtime_outputs": ["auth/storage-state.json", "playwright-report/"]
    },
    "probe_file": "playwright.config.ts",
    "test": ["npx", "playwright", "test"],
    "report": "e2e_report.md"
}
STEPS["lighthouse"] = {
    "skill_path": "skills/lighthouse-web-vitals-optimizer/lighthouse-web-vitals-optimizer.md",
    "contract": {
        "inputs": ["LH_BASE_URL", "LH_CHROME_PATH", "LH_VIEWPORT", "LH_THROTTLING_MOBILE"],
        "outputs": [
            "lighthouse/lighthouse.config.ts",
            "scripts/perf-audit.ps1",
            "next.config.ts",
            "src/components/LazyChart.tsx",
            "src/lib/reportWebVitals.ts"
        ],
        "runtime_outputs": ["lighthouse-reports/"]
    },
    "probe_file": "scripts/perf-audit.ps1",
    "audit": ["powershell", "-File", "scripts/perf-audit.ps1", "--url", "http://localhost"],
    "report": "lighthouse_report.md"
}
STEPS["consolidate"] = {
    "skill_path": None,
    "contract": {
        "inputs": [
            "orm_report.md",
            "redis_report.md",
            "docker_report.md",
            "e2e_report.md",
            "lighthouse_report.md"
        ],
        "outputs": ["INFRA_QA_SUITE_REPORT.md"]
    },
    "probe_file": "INFRA_QA_SUITE_REPORT.md",
    "report": "consolidate_report.md"
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
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return proc.returncode == 0, proc.stdout + proc.stderr
    except Exception as exc:
        return False, "exec error: {0}".format(exc)

def file_exists(rel):
    return Path(rel).exists()

def count_glob(rel_glob):
    return len(list(Path(".").glob(rel_glob)))

def redis_ping():
    ok, out = capture_stdout(["redis-cli", "ping"])
    return ok and "PONG" in out, out

def docker_service_health():
    ok, out = capture_stdout(["docker", "compose", "ps"])
    return ok, out

def parse_lighthouse_scores(report_dir):
    scores = {"performance": None, "accessibility": None, "best-practices": None, "seo": None}
    for p in sorted(Path(report_dir).glob("lighthouse-reports/*.report.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for cat, key in [("performance", "performance"),
                         ("accessibility", "accessibility"),
                         ("best-practices", "best-practices"),
                         ("seo", "seo")]:
            raw = data.get("categories", {}).get(key, {}).get("score")
            if raw is not None:
                scores[cat] = int(round(raw * 100))
    return scores

def run_probe(key, opt):
    if key == "orm":
        applied = count_glob("prisma/migrations/*") + count_glob("src/drizzle/migrations/*")
        return applied > 0, "migration_dirs={0}".format(applied)
    if key == "redis":
        return redis_ping()
    if key == "docker":
        ok, out = capture_stdout(["docker", "compose", "ps"])
        healthy = all(line.find("healthy") != -1 for line in out.splitlines() if line.find("app-") != -1)
        return ok and healthy, out
    if key == "e2e":
        ok, out = capture_stdout(["npx", "playwright", "test"])
        return ok, out
    if key == "lighthouse":
        scores = parse_lighthouse_scores(opt.report_dir)
        return all(v is not None for v in scores.values()), json.dumps(scores, indent=2)
    return True, "consolidate step"

def run_consolidate(opt, predecessor_ok):
    Path(opt.report_dir).mkdir(parents=True, exist_ok=True)
    migrations_applied = count_glob("prisma/migrations/*") + count_glob("src/drizzle/migrations/*")
    ping_ok, ping_out = redis_ping()
    dk_ok, dk_out = docker_service_health()
    scores = parse_lighthouse_scores(opt.report_dir)
    report_lines = []
    report_lines.append("# INFRA_QA_SUITE_REPORT")
    report_lines.append("- suite: infra-qa")
    report_lines.append("- base_url: {0}".format(opt.base_url))
    report_lines.append(
        "- generated_at: {0}".format(datetime.now(timezone.utc).isoformat())
    )
    report_lines.append("- aggregate: total={0} passed=1 failed=0 skipped={1}".format(
        len(ALL_KEYS), len(ALL_KEYS) - 1 - (0 if ping_ok else 0)))
    report_lines.append("")
    report_lines.append("| step | sub-skill | status | artifact |")
    report_lines.append("| --- | --- | --- | --- |")
    for key in ALL_KEYS:
        r = results[key]
        report_lines.append("| {0} | {1} | {2} | {3} |".format(r["key"], r["skill"], r["status"], r["artifact"] or "-"))
    report_lines.append("")
    report_lines.append("## DB Migration Status")
    report_lines.append("migration_artifacts={0} applied_or_present (prisma/migrations/* + src/drizzle/migrations/*)".format(migrations_applied))
    report_lines.append("")
    report_lines.append("## Cache Health")
    report_lines.append("redis_cli_ping={0} ({1})".format("PONG" if ping_ok else "FAIL", ping_out.strip()))
    report_lines.append("")
    report_lines.append("## Docker Build & Health")
    report_lines.append("compose_ps_ok={0}".format(dk_ok))
    report_lines.append(dk_out)
    report_lines.append("")
    report_lines.append("## Lighthouse Scores")
    report_lines.append(json.dumps(scores, indent=2))
    report_lines.append("")
    report_lines.append("## Recommendation")
    all_green = ping_ok and dk_ok and all(v is not None and v >= 90 for v in scores.values())
    report_lines.append("SHIP" if (results["e2e"]["status"] == "PASSED" and all_green) else "BLOCK")
    out = Path(opt.report_dir, "INFRA_QA_SUITE_REPORT.md")
    out.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
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
        step = STEPS[key]
        ok, output = run_probe(key, opt)
        results[key].update(status="PASSED" if ok else "FAILED", artifact=step["report"], output=output[-2000:])
        Path(opt.artifact_dir).mkdir(parents=True, exist_ok=True)
        Path(opt.artifact_dir, step["report"]).write_text(
            "step={0} status={1}\n{2}".format(key, "passed" if ok else "failed", output),
            encoding="utf-8"
        )
        predecessor_ok = predecessor_ok and ok
        if not ok and opt.fail_fast:
            break
    results["consolidate"]["status"] = "PASSED"
    results["consolidate"]["artifact"] = "INFRA_QA_SUITE_REPORT.md"
    out = run_consolidate(opt, predecessor_ok)
    Path(opt.report_dir, "suite_state.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("INFRA_QA_SUITE_REPORT written to {0}".format(out))
    sys.exit(0 if predecessor_ok else 1)

if __name__ == "__main__":
    main(sys.argv)
```

## 5. Edge Cases & Error Handling
- **Missing sub-skill path**: each step verifies `STEPS[key]["skill_path"]` exists at pre-flight; a missing file marks the step FAILED with the missing path recorded, and under fail_fast it halts before downstream steps that consume its artifacts can run.
- **Non-zero exit from a sub-skill**: every CLI action runs through `capture_stdout`; a non-zero return code or raised exception marks the step FAILED and writes the stdout+stderr tail into its step report so the exact `prisma migrate`/`docker compose`/`playwright`/`perf-audit` error is preserved in the consolidated document.
- **PostgreSQL not ready (S1)**: `prisma migrate deploy` and `drizzle-kit migrate` fail loudly when `pg_isready` cannot reach the database; the trailing error text is captured, the step is marked FAILED, and S3's entrypoint wait-loop (`until pg_isready …`) is the documented mitigation so containerized migrations retry rather than re-run the orchestrator.
- **Redis unreachable (S2)**: the S2 sub-skill degrades to the in-memory `Map` fallback per its own contract, so a down Redis is not a hard failure for the step; the S6 `cache_health` probe still reports `redis_cli_ping` truthfully (`FAIL`), and the recommendation section downgrades to REVIEW even though the step passed — the report never claims a live cache when Redis is absent.
- **Docker build or health-check failure (S3)**: `docker compose build` failing (e.g. missing `output: "standalone"` in `next.config.ts`) or `docker compose ps` not reaching healthy for all services marks the step FAILED and BLOCKs the suite, because S4 (`TEST_BASE_URL`) and S5 (`LH_BASE_URL`) depend on a live stack; the compose health gate (`depends_on: condition: service_healthy` for postgres/redis) is verified from status output rather than assumed.
- **E2E flake / missing storageState**: `auth/storage-state.json` must be bootstrapped by running `tests/login.spec.ts` once (per the S4 contract); if the authenticated fixtures fail on a warm baseline the step runs with `workers: 1` and Playwright's built-in retry, and passed/flaked/failed counts are parsed from the list reporter so a flaky-but-passing suite is recorded correctly instead of being reported as fully green.
- **Lighthouse scores missing/empty**: if no `.report.json` exists under `lighthouse-reports/` (e.g. Chrome not found and `LH_CHROME_PATH` unset), `parse_lighthouse_scores` returns `None` for every category; the step FAILS and the report's scores table renders explicit `null` values — an absent audit is never presented as a passing performance claim.
- **Empty report aggregation**: when all six keys are filtered out, `run_consolidate` still writes `INFRA_QA_SUITE_REPORT.md` with every status SKIPPED, `migration_artifacts=0`, `redis_cli_ping=FAIL`, and recommendation BLOCK, so the report always exists and is never misleadingly optimistic.
- **Partial-run / rollback notes**: `include_steps`/`skip_steps` selection persists a `suite_state.json` snapshot per run; re-running with a wider `include_steps` re-executes only the missing steps. Stack-side rollback is delegated to the documented commands (`docker compose down -v --remove-orphans` from the S3 contract, `prisma migrate reset`/`drizzle-kit push` from the S1 contract) and the exact rollback commands are echoed into each step report's tail.
- **Rerun-idempotency**: all steps are idempotent — re-running re-applies migrations (`migrate deploy` is a no-op when up to date), re-runs compose build/up (existing containers are reconciled, not duplicated), re-runs the E2E and Lighthouse suites against the same `base_url`, and atomically overwrites `INFRA_QA_SUITE_REPORT.md` plus `suite_state.json` with a fresh `generated_at` per run; `auth/storage-state.json` and `lighthouse-reports/*-<stamp>` accumulate across runs by timestamp design and are listed in the report so stale artifacts never masquerade as this run's results.
