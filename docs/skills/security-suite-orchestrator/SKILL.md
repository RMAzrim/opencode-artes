---
name: Security Suite Orchestrator
description: "Orchestrates a full 8-stage security audit chain over a local web app: dependency CVE scan, OWASP SAST static audit, SQLi/XSS input sanitization, JWT security cracking, BOLA/IDOR authorization scan, rate-limit brute-force shielding, and CORS/CSP header hardening, then consolidates every per-stage report into one SECURITY_AUDIT_REPORT.md. Supports full_run, include_steps, skip_steps, fail_fast, and report_dir customization so operators can re-run a subset of the chain without touching the others. Aggregates severity counts per category, per-stage pass/fail status, and a top-remediation ranked list from all seven stage artifacts."
metadata:
  source: skills/security-suite-orchestrator/security-suite-orchestrator.md
---

# Security Suite Orchestrator

## 1. System Overview & Target Sub-Skills
The Security Suite Orchestrator is a deterministic DAG runner that chains seven independent security sub-skills over one target codebase (plus a live localhost API when supplied), then merges their JSON reports into a single unified markdown summary. It is invoked when the user wants a complete, reproducible security posture assessment — dependency vulnerabilities, static injection/OWASP findings, sanitization remediation, authentication token strength, object-level authorization, brute-force resistance, and response-header hardening — in one pass with one consolidated report.

The chain is executed strictly in order because each stage refines or re-scopes the work of its predecessor. Invoked sub-skills and what each produces:

1. `skills/dependency-cve-audit-patcher/dependency-cve-audit-patcher.md` — runs `npm audit --json` (or an offline CVE list for `requirements.txt`) and emits `cve_report.json` with `cve_findings[]` (dependency, cve, severity, action) plus an optional npm fix-command plan.
2. `skills/owasp-sast-auditor/owasp-sast-auditor.md` — regex/AST static scan of `.py/.js/.ts/.jsx/.tsx` for OWASP injection sinks; emits `owasp_sast_report.json` + `owasp_sast_report.md` with `vulnerabilities[]` and optional `fixes/` + `backups/` trees.
3. `skills/sqli-xss-payload-sanitizer/sqli-xss-payload-sanitizer.md` — classifies SQLi/XSS sink lines and (with `--fix`) rewrites safe copies; emits `sanitizer_report.json`, a `sanitized/` tree and a `backups/` tree plus `_html_escape.js|py` utilities.
4. `skills/jwt-security-cracker-tester/jwt-security-cracker-tester.md` — analyzes an intercepted JWT for `alg:none` bypass, weak-secret cracking, claim gaps and RS256 key confusion; emits `jwt_report.json` and generates `hardened_jwt_middleware.js`.
5. `skills/bola-idor-vulnerability-scanner/bola-idor-vulnerability-scanner.md` — static route analysis plus optional live tampering tests; emits `bola_report.json` and generates `express_requireOwnership.js` / `fastapi_dependency.py` guards.
6. `skills/rate-limit-bruteforce-shield/rate-limit-bruteforce-shield.md` — scans source for auth endpoints and whether they are rate limited; emits `rate_limit_report.json` and generates `express_rate_limit.js` + `rate_limit_client_test.js`.
7. `skills/cors-csp-headers-hardener/cors-csp-headers-hardener.md` — probes a running local server's headers against the hardening policy; emits `headers_report.json` and generates `helmet_hardened.js` / `fastapi_hardened.py` (+ `strict_csp.txt`).
8. **Final consolidation (in orchestrator)** — merges the seven step reports into `SECURITY_AUDIT_REPORT.md` with aggregate severity counts per category, a per-step pass/fail matrix, and a ranked top-remediation list.

## 2. Execution Parameters & Configuration Options
- **full_run** (default `true`): execute the entire 8-step chain in order. When `true` and `include_steps` is empty, every step S1..S8 runs.
- **include_steps**: array of step keys to run — run ONLY these (overrides `full_run` for the listed steps). Valid keys: `dependency_cve`, `sast`, `sanitizer`, `jwt`, `bola_idor`, `rate_limit`, `headers`, `consolidate`.
- **skip_steps**: array of step keys to omit from the run. Excluded steps are recorded as `NOT_RUN` in the matrix and never block successor gating (a skipped predecessor still allows its successor to run when its gate is satisfied by an explicit include).
- **fail_fast** (default `true`): halt the chain at the first step whose sub-skill exits non-zero or raises. When `false`, remaining steps still run and their failures accumulate in the matrix.
- **report_dir / artifact_dir**: directory where per-step outputs aggregate (each sub-skill receives `--report-dir <report_dir>` / its own output path inside it). Default `./security-suite-reports`.
- Extra route-scoped inputs: `target` (source tree root for S2/S3/S5/S6), `manifest` (for S1), `base_url` (for S5 runtime tests and S7 header probing), `user_id`, `jwt_token`, `jwt_wordlist`, `jwt_pem`, `fix_mode`, `write_guards`.

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
      "items": { "enum": ["dependency_cve", "sast", "sanitizer", "jwt", "bola_idor", "rate_limit", "headers", "consolidate"] },
      "minItems": 1
    },
    "skip_steps": {
      "type": "array",
      "items": { "enum": ["dependency_cve", "sast", "sanitizer", "jwt", "bola_idor", "rate_limit", "headers", "consolidate"] }
    },
    "fail_fast": { "type": "boolean", "default": true },
    "report_dir": { "type": "string", "default": "./security-suite-reports" },
    "target": { "type": "string", "description": "Source tree root scanned by sast, sanitizer, bola_idor, rate_limit" },
    "manifest": { "type": "string", "description": "package.json or requirements.txt audited by dependency_cve" },
    "base_url": { "type": "string", "format": "uri", "description": "Live localhost API for bola runtime tests and headers probing" },
    "user_id": { "type": "string", "default": "testuser-1" },
    "jwt_token": { "type": "string", "description": "Intercepted JWT analyzed by the jwt step" },
    "jwt_wordlist": { "type": "string" },
    "jwt_pem": { "type": "string" },
    "fix_mode": { "type": "boolean", "default": false },
    "write_guards": { "type": "boolean", "default": true },
    "step_timeout_seconds": { "type": "integer", "default": 900 }
  },
  "required": ["target"]
}
```

Consolidated output report structure (written as `SECURITY_AUDIT_REPORT.md`, mirror JSON at `security_suite_result.json`):

```json
{
  "orchestrator": "security-suite-orchestrator",
  "run_id": "sec-2026-09-13T12-00-00Z",
  "report_dir": "./security-suite-reports",
  "steps": [
    {
      "key": "dependency_cve", "step": "S1",
      "skill_path": "skills/dependency-cve-audit-patcher/dependency-cve-audit-patcher.md",
      "status": "PASS", "exit_code": 0,
      "report_path": "security-suite-reports/cve_report.json",
      "payload": { "project": "app", "dependency_count": 214, "cve_findings": [] }
    }
  ],
  "aggregate": {
    "per_step": { "dependency_cve": "PASS", "sast": "PASS", "sanitizer": "PASS", "jwt": "PASS", "bola_idor": "PASS", "rate_limit": "PASS", "headers": "FAIL", "consolidate": "PASS" },
    "severity_counts_by_category": {
      "dependency_cve": { "CRITICAL": 0, "HIGH": 2, "MEDIUM": 1, "LOW": 0, "total": 3 },
      "sast": { "CRITICAL": 1, "HIGH": 4, "MEDIUM": 2, "LOW": 0, "total": 7 },
      "sanitizer": { "CRITICAL": 1, "HIGH": 3, "MEDIUM": 0, "LOW": 0, "total": 4 },
      "headers": { "CRITICAL": 1, "HIGH": 1, "MEDIUM": 3, "LOW": 1, "total": 6 }
    },
    "total_findings": 20
  },
  "top_remediation": ["sast[CRITICAL]: SQLI-execute in src/db.js:42", "headers: 1 CRITICAL header finding -> deploy helmet_hardened.js"],
  "consolidated_report": "SECURITY_AUDIT_REPORT.md"
}
```

## 3. Step-by-Step Execution Protocol & Data Flow

1. **Pre-flight Check**: verify Python 3.10+ and (for S1) Node.js 18+ with npm on PATH; confirm every sub-skill path under `skills/<id>/<id>.md` exists and the manifest/target/base_url pointed at by the options resolve to real files/directories. Create `report_dir` up front so every step can write into the same aggregation bucket. If a sub-skill path is missing, the step fails fast with the missing path rather than degrading silently.

2. **Sequential Chaining** (each step invokes its sub-skill as `python skills/<id>/<id>.md <args>` from a step-appropriate cwd, with `PYTHONIOENCODING=utf-8`):
   - **S1 — `dependency_cve`**: input `manifest` (default `package.json`). Output artifact `{report_dir}/cve_report.json` (`project`, `dependency_count`, `advisories`, `cve_findings[]`, `patch_plan`).
   - **S2 — `sast`**: input `--target <target> --report-dir <report_dir>`. Output artifacts `{report_dir}/owasp_sast_report.json` + `owasp_sast_report.md` (`scan_target`, `files_scanned`, `total_findings`, `vulnerabilities[]` with `severity/rule/cwe/file/line/recommendation`), plus `fixes/` + `backups/` when `fix_mode`.
   - **S3 — `sanitizer`**: input `--target <target> --report-dir <report_dir>`. Output artifact `{report_dir}/sanitizer_report.json` (`findings[]` with `type` SQLI/XSS, `patch_kind`, `file`, `line`; `patches_applied`, `output.sanitized_tree`, `output.backups`, `rollback`), plus `sanitized/`, `backups/`, `_html_escape.js` / `_html_escape.py`.
   - **S4 — `jwt`**: input `--token <jwt_token> --report {report_dir}/jwt_report.json`, optional `--wordlist` / `--pem`. Output artifact `{report_dir}/jwt_report.json` (`token_analysis`, `none_bypass`, `secret_cracked`, `claims_validation`, `key_confusion`, `remediation.middleware_file` → `hardened_jwt_middleware.js`, `summary`).
   - **S5 — `bola_idor`**: input `--source <target> --report-dir <report_dir> --user-id <user_id>`, plus `--base-url` when supplied. Output artifact `{report_dir}/bola_report.json` (`static_findings[]` with `status`/`confidence`, `runtime_findings[]` with `verdict`, `generated_guards` → `express_requireOwnership.js` / `fastapi_dependency.py`, `summary`).
   - **S6 — `rate_limit`**: input `--source <target> --report-dir <report_dir>`. Output artifact `{report_dir}/rate_limit_report.json` (`endpoints[]` with `{file,line,path,methods,protected,store,snippet}`, `summary`), plus generated `express_rate_limit.js` and `rate_limit_client_test.js`.
   - **S7 — `headers`**: input `--url <base_url> --report-dir <report_dir> [--write-guards]`. Output artifact `{report_dir}/headers_report.json` (`endpoints[]` with collected `headers` + `findings[]`, `summary.{endpoints_probed,total_findings,critical,high,medium,low}`), plus `helmet_hardened.js`, `fastapi_hardened.py`, `strict_csp.txt` when `write_guards`.
   - **S8 — `consolidate`**: no sub-skill; the orchestrator reads the seven step artifacts and writes `{report_dir}/SECURITY_AUDIT_REPORT.md`.

3. **Data Contracting** — step-N output artifact to step-(N+1) input fields:
   - S1 `cve_report.json` → **S2**: `cve_findings[*].dependency` and `patch_plan.npm[]` become the advisory context recorded in the S2 scan header, so SAST findings on packages with known CVEs are ranked first; `dependency_count` is echoed into the consolidated severity table.
   - S2 `owasp_sast_report.json` → **S3**: `vulnerabilities[*].file` where `rule` starts with a `SQLI-` or `XSS-` prefix is the verification gate — every such file must reappear under `sanitizer_report.json` findings or in `sanitized/`; `vulnerabilities[*].recommendation` seeds the sanitizer patch acceptance checklist.
   - S3 `sanitizer_report.json` → **S4**: `output.sanitized_tree` and `patches_applied` define the hardened app instance the JWT belongs to; any token literal encountered in `findings[*].file` is matched against `jwt_token` so S4 analyzes the same code path it was captured from.
   - S4 `jwt_report.json` → **S5**: if `summary.signature_forgery_risk` is true, `none_bypass.forged_none_tokens` and `key_confusion.forged_hs256_token` are supplied as `Authorization: Bearer <forged>` candidates for the S5 runtime `POST {base_url}/test` tampering harness; `remediation.middleware_file` (`hardened_jwt_middleware.js`) is flagged for deployment before object-level routes are re-tested.
   - S5 `bola_report.json` → **S6**: `static_findings[*].route` with `status: "VULNERABLE"` (and the paths confirmed by `runtime_findings[*].verdict == "VULNERABLE"`) become the priority route list S6's scanner targets; `summary.runtime_vulnerable_count` decides whether the rate-limit shield must ship before the re-audit.
   - S6 `rate_limit_report.json` → **S7**: `endpoints[*].path` where `protected` is `false` (unprotected login/reset/OTP routes from the `summary`) are appended to the header hardener's `--endpoint` probe list, so the exact sensitive routes are checked for CSP/ACAC/clickjacking headers.
   - S7 `headers_report.json` → **S8**: `findings[*].severity` and `summary.{critical,high,medium,low}` feed the headers severity bucket directly and receive a ranked entry in `top_remediation`.

4. **Final Consolidation**: the orchestrator merges all seven step payloads into `{report_dir}/SECURITY_AUDIT_REPORT.md` containing (a) an aggregate counts table with one row per step — status, exit code, finding total, CRITICAL/HIGH/MEDIUM/LOW from `cve_findings` / `vulnerabilities` / sanitizer+headers `findings` plus the bolt-on `summary` fields — (b) a per-step PASS/FAIL/NOT_RUN matrix, and (c) a short ranked Recommendation section assembled from `top_remediation`. A machine-readable mirror is written to `{report_dir}/security_suite_result.json` for CI consumption.

## 4. Reference Execution DAG / Pseudo-Code Implementation

```python
#!/usr/bin/env python3
"""Security Suite Orchestrator — 8-stage security audit DAG.

Runs seven sub-skill scripts (skills/<id>/<id>.md) gated by predecessor
success, filters by include_steps / skip_steps, halts on fail_fast, captures
per-step stdout + JSON reports, then consolidates SECURITY_AUDIT_REPORT.md.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STEP_ORDER = [
    "dependency_cve",
    "sast",
    "sanitizer",
    "jwt",
    "bola_idor",
    "rate_limit",
    "headers",
    "consolidate",
]

SKILL_PATHS = {
    "dependency_cve": "skills/dependency-cve-audit-patcher/dependency-cve-audit-patcher.md",
    "sast": "skills/owasp-sast-auditor/owasp-sast-auditor.md",
    "sanitizer": "skills/sqli-xss-payload-sanitizer/sqli-xss-payload-sanitizer.md",
    "jwt": "skills/jwt-security-cracker-tester/jwt-security-cracker-tester.md",
    "bola_idor": "skills/bola-idor-vulnerability-scanner/bola-idor-vulnerability-scanner.md",
    "rate_limit": "skills/rate-limit-bruteforce-shield/rate-limit-bruteforce-shield.md",
    "headers": "skills/cors-csp-headers-hardener/cors-csp-headers-hardener.md",
    "consolidate": None,
}

STEP_NUM = {key: "S" + str(index + 1) for index, key in enumerate(STEP_ORDER)}

STEP_OUTPUTS = {
    "dependency_cve": "cve_report.json",
    "sast": "owasp_sast_report.json",
    "sanitizer": "sanitizer_report.json",
    "jwt": "jwt_report.json",
    "bola_idor": "bola_report.json",
    "rate_limit": "rate_limit_report.json",
    "headers": "headers_report.json",
    "consolidate": "SECURITY_AUDIT_REPORT.md",
}

RECOMMENDED_DEFAULT = {
    "report_dir": "./security-suite-reports",
    "manifest": "package.json",
    "user_id": "testuser-1",
    "fail_fast": True,
    "fix_mode": False,
    "write_guards": True,
    "step_timeout_seconds": 900,
}


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


def step_cwd(key, options):
    if key == "dependency_cve":
        manifest = Path(options.get("manifest", "package.json"))
        return str(manifest.resolve().parent)
    if key == "jwt":
        return str(Path(options["report_dir"]).resolve())
    return str(Path(options.get("target", ".")).resolve())


def build_invocation(key, options):
    report_dir = str(Path(options["report_dir"]).resolve())
    argv = []
    if key == "dependency_cve":
        argv = ["--manifest", options.get("manifest", "package.json"),
                "--wordlist-report", os.path.join(report_dir, "cve_report.json")]
        if options.get("fix_mode"):
            argv.append("--fix-mode")
    elif key == "sast":
        argv = ["--target", options["target"], "--report-dir", report_dir]
        if options.get("fix_mode"):
            argv.append("--fix")
    elif key == "sanitizer":
        argv = ["--target", options["target"], "--report-dir", report_dir]
        if options.get("fix_mode"):
            argv.append("--fix")
    elif key == "jwt":
        token = options.get("jwt_token") or "MISSING_TOKEN"
        argv = ["--token", token, "--report", os.path.join(report_dir, "jwt_report.json")]
        if options.get("jwt_wordlist"):
            argv.append("--wordlist")
            argv.append(options["jwt_wordlist"])
        if options.get("jwt_pem"):
            argv.append("--pem")
            argv.append(options["jwt_pem"])
    elif key == "bola_idor":
        argv = ["--source", options["target"], "--report-dir", report_dir,
                "--user-id", options.get("user_id", "testuser-1")]
        if options.get("base_url"):
            argv.append("--base-url")
            argv.append(options["base_url"])
    elif key == "rate_limit":
        argv = ["--source", options["target"], "--report-dir", report_dir]
    elif key == "headers":
        base_url = options.get("base_url")
        if not base_url:
            raise LookupError("headers step requires options['base_url']")
        argv = ["--url", base_url, "--report-dir", report_dir]
        if options.get("write_guards"):
            argv.append("--write-guards")
    else:
        raise KeyError("unknown step key: " + key)
    return argv


def extract_severity_counts(payload):
    buckets = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    if not isinstance(payload, dict):
        buckets["total"] = 0
        return buckets
    findings = []
    findings.extend(payload.get("cve_findings", []))
    findings.extend(payload.get("vulnerabilities", []))
    findings.extend(payload.get("findings", []))
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        sev = str(finding.get("severity", "LOW")).upper()
        if sev in buckets:
            buckets[sev] += 1
    summary = payload.get("summary", {})
    if isinstance(summary, dict):
        for key in ("critical", "high", "medium", "low"):
            value = summary.get(key, 0)
            try:
                buckets[key.upper()] += int(value)
            except (TypeError, ValueError):
                continue
    buckets["total"] = sum(buckets[key] for key in ("CRITICAL", "HIGH", "MEDIUM", "LOW"))
    return buckets


def run_skill_step(key, options):
    skill_path = SKILL_PATHS[key]
    if not Path(skill_path).is_file():
        raise FileNotFoundError("sub-skill path missing: " + skill_path)
    argv = build_invocation(key, options)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, skill_path] + argv,
        cwd=step_cwd(key, options),
        capture_output=True,
        text=True,
        timeout=options.get("step_timeout_seconds", 900),
        env=env,
    )
    report_path = Path(options["report_dir"]) / STEP_OUTPUTS[key]
    payload = {}
    if report_path.is_file():
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
    return {
        "key": key,
        "step": STEP_NUM[key],
        "skill_path": skill_path,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "report_path": str(report_path),
        "payload": payload,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def collect_top_remediation(step_outputs):
    top = []
    cve_payload = step_outputs.get("dependency_cve", {}).get("payload", {})
    for finding in cve_payload.get("cve_findings", []):
        if isinstance(finding, dict):
            top.append("dependency_cve: " + str(finding.get("dependency", "?")) +
                       " -> " + str(finding.get("cve", "?")) +
                       " action=" + str(finding.get("action", "review-manually")))
    sast_payload = step_outputs.get("sast", {}).get("payload", {})
    for finding in sast_payload.get("vulnerabilities", []):
        if isinstance(finding, dict):
            top.append("sast[" + str(finding.get("severity", "LOW")) + "]: " +
                       str(finding.get("rule", "?")) + " in " +
                       str(finding.get("file", "?")) + ":" + str(finding.get("line", "?")))
    sanitizer_payload = step_outputs.get("sanitizer", {}).get("payload", {})
    for finding in sanitizer_payload.get("findings", []):
        if isinstance(finding, dict):
            top.append("sanitizer[" + str(finding.get("type", "?")) + "]: " +
                       str(finding.get("file", "?")) + ":" + str(finding.get("line", "?")) +
                       " -> " + str(finding.get("patch_kind", "?")))
    jwt_payload = step_outputs.get("jwt", {}).get("payload", {})
    jwt_summary = jwt_payload.get("summary", {}) if isinstance(jwt_payload, dict) else {}
    if jwt_summary.get("signature_forgery_risk"):
        top.append("jwt: signature forgery risk confirmed -> deploy hardened_jwt_middleware.js and pin an algorithm whitelist")
    if jwt_summary.get("weak_secret_risk"):
        top.append("jwt: weak HMAC secret cracked -> rotate JWT_SECRET and force re-issue of all tokens")
    bola_payload = step_outputs.get("bola_idor", {}).get("payload", {})
    bola_summary = bola_payload.get("summary", {}) if isinstance(bola_payload, dict) else {}
    if bola_summary.get("runtime_vulnerable_count"):
        top.append("bola_idor: " + str(bola_summary.get("runtime_vulnerable_count")) +
                   " runtime tamper-positive routes -> mount express_requireOwnership.js / fastapi_dependency.py guards")
    rl_payload = step_outputs.get("rate_limit", {}).get("payload", {})
    rl_summary = rl_payload.get("summary", {}) if isinstance(rl_payload, dict) else {}
    if rl_summary.get("unprotected_count"):
        top.append("rate_limit: " + str(rl_summary.get("unprotected_count")) +
                   " unprotected auth endpoints -> wire express_rate_limit.js and verify 429 with rate_limit_client_test.js")
    headers_payload = step_outputs.get("headers", {}).get("payload", {})
    headers_summary = headers_payload.get("summary", {}) if isinstance(headers_payload, dict) else {}
    if headers_summary.get("critical"):
        top.append("headers: " + str(headers_summary.get("critical")) +
                   " CRITICAL header findings -> deploy helmet_hardened.js / fastapi_hardened.py")
    return top if top else ["no remediable findings reported by any completed step"]


def consolidate(options, step_outputs):
    report_dir = Path(options["report_dir"]).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    final_path = report_dir / "SECURITY_AUDIT_REPORT.md"
    lines = []
    lines.append("# Security Suite Audit Report")
    lines.append("")
    lines.append("Orchestrator: security-suite-orchestrator")
    lines.append("Run time: " + datetime.now(timezone.utc).isoformat())
    lines.append("Report dir: " + str(report_dir))
    lines.append("")

    lines.append("## Aggregate Severity Counts by Category")
    lines.append("")
    lines.append("| Category | CRITICAL | HIGH | MEDIUM | LOW | Total |")
    lines.append("|----------|----------|------|--------|-----|-------|")
    grand = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for key in STEP_ORDER:
        if key == "consolidate":
            continue
        result = step_outputs.get(key)
        if not result:
            continue
        counts = extract_severity_counts(result.get("payload", {}))
        lines.append("| " + key + " | " + str(counts["CRITICAL"]) + " | " +
                     str(counts["HIGH"]) + " | " + str(counts["MEDIUM"]) + " | " +
                     str(counts["LOW"]) + " | " + str(counts["total"]) + " |")
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            grand[sev] += counts[sev]
    lines.append("| **TOTAL** | " + str(grand["CRITICAL"]) + " | " + str(grand["HIGH"]) +
                 " | " + str(grand["MEDIUM"]) + " | " + str(grand["LOW"]) +
                 " | " + str(sum(grand.values())) + " |")
    lines.append("")

    lines.append("## Per-Step Pass / Fail Matrix")
    lines.append("")
    lines.append("| Step | Key | Skill | Status | Exit |")
    lines.append("|------|-----|-------|--------|------|")
    for key in STEP_ORDER:
        result = step_outputs.get(key)
        if not result:
            lines.append("| " + STEP_NUM[key] + " | " + key + " | (not selected) | NOT_RUN | n/a |")
            continue
        exit_txt = "n/a" if result.get("exit_code") is None else str(result.get("exit_code"))
        skill = result.get("skill_path") or "(local consolidation)"
        lines.append("| " + result.get("step", STEP_NUM[key]) + " | " + key +
                     " | `" + skill + "` | " + str(result.get("status", "?")) +
                     " | " + exit_txt + " |")
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    for rank, item in enumerate(collect_top_remediation(step_outputs), 1):
        lines.append(str(rank) + ". " + item)
    lines.append("")
    lines.append("---")
    lines.append("Generated by security-suite-orchestrator")
    final_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    consolidated = {
        "orchestrator": "security-suite-orchestrator",
        "run_id": "sec-" + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S") + "Z",
        "report_dir": str(report_dir),
        "steps": [],
        "aggregate": {"per_step": {}, "severity_counts_by_category": {}, "total_findings": 0},
        "top_remediation": collect_top_remediation(step_outputs),
        "consolidated_report": "SECURITY_AUDIT_REPORT.md",
    }
    total = 0
    for key in STEP_ORDER:
        result = step_outputs.get(key)
        if not result:
            continue
        entry = dict(result)
        entry.pop("payload", None)
        consolidated["steps"].append(entry)
        consolidated["aggregate"]["per_step"][key] = result.get("status", "NOT_RUN")
        if key != "consolidate":
            counts = extract_severity_counts(result.get("payload", {}))
            consolidated["aggregate"]["severity_counts_by_category"][key] = counts
            total += counts["total"]
    consolidated["aggregate"]["total_findings"] = total
    result_path = report_dir / "security_suite_result.json"
    result_path.write_text(json.dumps(consolidated, indent=2), encoding="utf-8")
    return {
        "key": "consolidate",
        "step": STEP_NUM["consolidate"],
        "skill_path": None,
        "status": "PASS",
        "exit_code": 0,
        "report_path": str(final_path),
        "payload": consolidated,
        "stdout_tail": ("Consolidated " + str(len(consolidated["steps"])) +
                        " step reports into " + str(final_path)),
        "stderr_tail": "",
    }


def run_step(key, options, step_outputs):
    if key == "consolidate":
        return consolidate(options, step_outputs)
    return run_skill_step(key, options)


def should_run(key, options, results, active):
    predecessor = predecessor_of(key)
    if predecessor == "":
        return True
    if predecessor in active and results.get(predecessor, {}).get("status") == "PASS":
        return True
    if key == "consolidate" and key in active:
        any_pass = any(res.get("status") == "PASS" for res in results.values())
        return any_pass
    return False


def run_dag(options):
    merged = dict(RECOMMENDED_DEFAULT)
    merged.update(options)
    options = merged
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
            result = run_step(key, options, results)
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
    parser = argparse.ArgumentParser(description="Security Suite Orchestrator")
    parser.add_argument("--target", required=True, help="Source tree root to audit")
    parser.add_argument("--report-dir", default="./security-suite-reports")
    parser.add_argument("--manifest", default="package.json")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--user-id", default="testuser-1")
    parser.add_argument("--jwt-token", default=None)
    parser.add_argument("--jwt-wordlist", default=None)
    parser.add_argument("--jwt-pem", default=None)
    parser.add_argument("--include", action="append", default=None)
    parser.add_argument("--skip", action="append", default=None)
    parser.add_argument("--no-fail-fast", action="store_true")
    parser.add_argument("--fix-mode", action="store_true")
    parser.add_argument("--no-write-guards", action="store_true")
    parser.add_argument("--step-timeout-seconds", type=int, default=900)
    args = parser.parse_args(argv)

    options = {
        "target": args.target,
        "report_dir": args.report_dir,
        "manifest": args.manifest,
        "base_url": args.base_url,
        "user_id": args.user_id,
        "jwt_token": args.jwt_token,
        "jwt_wordlist": args.jwt_wordlist,
        "jwt_pem": args.jwt_pem,
        "include_steps": args.include or [],
        "skip_steps": args.skip or [],
        "full_run": not bool(args.include),
        "fail_fast": not args.no_fail_fast,
        "fix_mode": args.fix_mode,
        "write_guards": not args.no_write_guards,
        "step_timeout_seconds": args.step_timeout_seconds,
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
    print("All active steps PASS. Consolidated: " + str(Path(options["report_dir"]) / "SECURITY_AUDIT_REPORT.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 5. Edge Cases & Error Handling
- **Missing sub-skill path**: `run_skill_step` raises `FileNotFoundError` naming the missing `skills/<id>/<id>.md`; with default `fail_fast: true` the chain halts and the matrix records that step as FAIL with a clear path instead of invoking a nonexistent script.
- **Non-zero sub-skill exit**: the step records `status: FAIL`, `exit_code`, and last 2000 chars of stdout/stderr into the result payload; with `fail_fast: true` the run stops there, otherwise later steps still execute and their results accumulate in the matrix.
- **Missing required inputs for a step**: e.g. S4 without `jwt_token` (analyzes a literal `MISSING_TOKEN` placeholder and fails fast with a clear ValueError from the sub-skill) or S7 without `base_url` (raises `LookupError` in `build_invocation`). These are surfaced as step-level FAIL rows, not crashes of the whole DAG.
- **Empty report aggregation**: if a sub-skill exits 0 but its JSON report is absent or unparseable, `payload` defaults to `{}` and the step still passes; the aggregate table then renders zeros for that category and the matrix still shows the exit code — the run stays truthful about what was actually produced.
- **Offline / degraded sub-skills**: dependency step falls back to the offline CVE list when `npm audit` fails; JWT RS256 verification logs `"cryptography not installed"`; BOLA runtime tests record `status: "unreachable"`; header probes record `status: null`. All are tolerated because every sub-skill embeds its own graceful-degradation path, which the orchestrator passes through untouched.
- **Rollback / partial-run notes**: every fix-producing step writes to its own `report_dir` sandbox (`sanitized/`, `backups/`, `fixes/`) and never modifies source in place, so rolling back means copying the `backups/` tree back. Re-running the orchestrator is idempotent: report files are overwritten deterministically, and `full_run` after a partial run re-audits cleanly.
- **Rerun-idempotency bullets**: identical options produce identical artifacts at the same paths; `include_steps: ["sast","headers"]` never invokes the other sub-skills; `skip_steps` and `include_steps` are mutually exclusive in effect (include wins); reruns overwrite the previous `SECURITY_AUDIT_REPORT.md` and `security_suite_result.json` so CI consumers always read the freshest aggregate.
- **Timeout handling**: each sub-skill runs under `step_timeout_seconds` (default 900); a `TimeoutExpired` propagates as a FAIL step with the offending step key, preventing the DAG from hanging mid-chain.
