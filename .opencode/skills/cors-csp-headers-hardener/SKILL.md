---
name: CORS & CSP Headers Hardener
description: Inspects HTTP response headers on local web servers and injects defensive security headers to prevent clickjacking, cross-site scripting, and unauthorized domain access.
metadata:
  source: skills/cors-csp-headers-hardener/cors-csp-headers-hardener.md
---

# CORS & CSP Headers Hardener

## 1. System Architecture & Prerequisites
- Python 3.10+ (stdlib only: `json`, `argparse`, `urllib.request`, `urllib.error`, `pathlib`)
- Target: a running local HTTP server reachable at `--url` (e.g. `http://127.0.0.1:3000`)
- No external `requests` dependency — `urllib.request` performs the header reconnaissance
- Output guards: hardened Node/Express `helmet` middleware and Python/FastAPI middleware variants

## 2. Input/Output Data Contracts

**Input (CLI args):**
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string", "description": "Base URL of local web server, e.g. http://127.0.0.1:3000" },
    "report_dir": { "type": "string", "description": "Output directory", "default": "./header-reports" },
    "write_guards": { "type": "boolean", "description": "Emit hardened middleware files", "default": false }
  },
  "required": ["url"]
}
```

**Output artifacts:**
- `{report_dir}/headers_report.json` — collected headers + findings for each endpoint
- `{report_dir}/honors_only_CSP.txt` — strict CSP policy string
- `{report_dir}/helmet_hardened.js` — Node helmet + CORS allowlist middleware
- `{report_dir}/fastapi_hardened.py` — FastAPI CORSMiddleware + SecurityHeaders middleware

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""CORS & CSP Headers Hardener — header reconnaissance, gap analysis, hardened middleware generation."""

import re
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

DEFAULT_ENDPOINTS = ["/", "/api", "/api/v1", "/health", "/login", "/admin"]

STRICT_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "upgrade-insecure-requests"
)

REQUIRED_HEADERS = {
    "Content-Security-Policy": "Prevents XSS and injection of malicious resources",
    "X-Content-Type-Options": "Stops MIME sniffing (set to nosniff)",
    "X-Frame-Options": "Prevents clickjacking (set to DENY or SAMEORIGIN)",
    "Referrer-Policy": "Controls referrer leakage",
    "Strict-Transport-Security": "Enforces HTTPS on supporting clients",
    "Access-Control-Allow-Origin": "Must be a fixed origin list/allowlist, never wildcard with credentials",
}

WEAK_CSP_MARKERS = ["unsafe-inline", "unsafe-eval", "data:", "*", "http://"]
WEAK_ACAO_MARKERS = ["*"]
WEAK_XFO = ["ALLOWALL", "ALLOW-FROM"]  # ALLOWALL is non-standard/no-op


def fetch_headers(url: str, method: str = "GET") -> dict:
    """Fetch a URL and return {status, headers: {name: value}}."""
    req = urllib.request.Request(url, method=method,
                                 headers={"User-Agent": "cors-csp-headers-hardener/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {
                "status": resp.status,
                "headers": {name.lower(): value for name, value in resp.headers.items()},
                "url": url,
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "headers": {name.lower(): value for name, value in exc.headers.items()},
            "url": url,
        }
    except urllib.error.URLError as exc:
        return {"status": None, "headers": {}, "url": url, "error": str(exc.reason)}


def check_headers(headers: dict, url: str) -> list:
    """Evaluate collected headers against the hardening policy. Returns findings."""
    findings = []
    h = headers

    csp = h.get("content-security-policy", "")
    if not csp:
        findings.append({"header": "Content-Security-Policy", "severity": "CRITICAL", "status": "missing", "url": url})
    else:
        weak = [m for m in WEAK_CSP_MARKERS if m in csp]
        if weak:
            findings.append({"header": "Content-Security-Policy", "severity": "HIGH", "status": "weak",
                             "url": url, "detail": f"contains weakening tokens: {weak}", "current_value": csp})

    acao = h.get("access-control-allow-origin", "")
    if not acao:
        findings.append({"header": "Access-Control-Allow-Origin", "severity": "MEDIUM", "status": "missing", "url": url})
    elif any(w in acao for w in WEAK_ACAO_MARKERS):
        findings.append({"header": "Access-Control-Allow-Origin", "severity": "HIGH", "status": "weak-wildcard",
                         "url": url, "detail": "wildcard ACAO with possible credentials", "current_value": acao})

    acac = h.get("access-control-allow-credentials", "")
    if acao == "*" and acac.lower() == "true":
        findings.append({"header": "Access-Control-Allow-Credentials", "severity": "CRITICAL", "status": "dangerous",
                         "url": url, "detail": "wildcard origin combined with credentials", "current_value": acac})

    for name, msg in [("x-content-type-options", "set to usniff barrier"), ("x-frame-options", "clickjacking barrier")]:
        try:
            value = h[name]
        except KeyError:
            findings.append({"header": name, "severity": "MEDIUM", "status": "missing", "url": url,
                             "detail": msg})
        else:
            if any(w.lower() in value.upper() for w in WEAK_XFO) and name == "x-frame-options":
                findings.append({"header": name, "severity": "HIGH", "status": "weak", "url": url,
                                 "current_value": value})
            if name == "x-content-type-options" and value.lower() not in ("nosniff", "nosniff, nosniff"):
                findings.append({"header": name, "severity": "MEDIUM", "status": "nonstandard", "url": url,
                                 "current_value": value})

    if not h.get("strict-transport-security", ""):
        findings.append({"header": "Strict-Transport-Security", "severity": "MEDIUM", "status": "missing", "url": url})
    if not h.get("referrer-policy", ""):
        findings.append({"header": "Referrer-Policy", "severity": "LOW", "status": "missing", "url": url})

    return findings


# ─── Hardened middleware generators ─────────────────────────────────────────────

def generate_helmet_middleware(report_dir: Path, allowed_origins: list) -> Path:
    origins_js = json.dumps(allowed_origins or ["http://localhost:3000", "http://127.0.0.1:3000"])
    code = f"""// hardened_helmet.js — strict security headers + allowlisted CORS
// Express middleware generated by cors-csp-headers-hardener.
const helmet = require('helmet');

const ALLOWED_ORIGINS = new Set({origins_js});

// Strict CSP (no unsafe-inline for JS, no wildcard anywhere)
const CSP_POLICY = {json.dumps(STRICT_CSP)};

const coreSecurity = helmet({{
  contentSecurityPolicy: {{
    useDefaults: true,
    directives: {{
      'default-src': ["'self'"],
      'script-src': ["'self'"],
      'style-src': ["'self'", "'unsafe-inline'"],
      'img-src': ["'self'", 'data:'],
      'object-src': ["'none'"],
      'frame-ancestors': ["'none'"],
      'form-action': ["'self'"],
      'base-uri': ["'self'"],
      'upgrade-insecure-requests': [],
    }},
  }},
  crossOriginEmbedderPolicy: false,
  hsts: {{ maxAge: 31536000, includeSubDomains: true, preload: true }},
  referrerPolicy: {{ policy: 'strict-origin-when-cross-origin' }},
  frameguard: {{ action: 'deny' }},          // X-Frame-Options: DENY
  noSniff: true,                             // X-Content-Type-Options: nosniff
  hidePoweredBy: true,
}});

// Per-route CORS: explicit origin allowlist, credentials only for listed origins.
function corsAllowlist(req, res, next) {{
  const origin = req.headers.origin;
  if (!origin) {{
    return next(); // same-origin / non-browser client
  }}
  if (ALLOWED_ORIGINS.has(origin)) {{
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Vary', 'Origin');
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');
    if (req.method === 'OPTIONS') {{
      return res.sendStatus(204);
    }}
    return next();
  }}
  // Disallowed origin: do NOT add ACAO at all (browser blocks the response).
  return next();
}}

module.exports = {{ coreSecurity, corsAllowlist, ALLOWED_ORIGINS }};

// Usage:
//   const {{ coreSecurity, corsAllowlist }} = require('./hardened_helmet');
//   app.use(coreSecurity);
//   app.use(corsAllowlist);            // per-route allowlist used app-wide
//   // or for one route: app.get('/api', corsAllowlist, handler)
"""
    out = report_dir / "helmet_hardened.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(code, encoding="utf-8")
    return out


def generate_fastapi_middleware(report_dir: Path, allowed_origins: list) -> Path:
    origins_py = json.dumps(allowed_origins or ["http://localhost:3000", "http://127.0.0.1:3000"])
    code = f'''"""fastapi_hardened.py — strict security headers + allowlisted CORS for FastAPI.

Mount as:
    from fastapi_hardened import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins={origins_py},
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    )
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware  # noqa: F401  (re-exported)

_ALLOWED_ORIGINS = {origins_py}

_STRICT_CSP = "{STRICT_CSP}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _STRICT_CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        origin = request.headers.get("origin")
        if origin:
            if origin in _ALLOWED_ORIGINS:
                response.headers.setdefault("Access-Control-Allow-Origin", origin)
                response.headers["Vary"] = "Origin"
            else:
                response.headers.pop("Access-Control-Allow-Origin", None)
        return response
'''
    out = report_dir / "fastapi_hardened.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(code, encoding="utf-8")
    return out


# ─── Orchestration ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CORS & CSP Headers Hardener — header recon, gap analysis, middleware generation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", required=True, help="Base URL of local web server")
    parser.add_argument("--report-dir", default="./header-reports", help="Output directory")
    parser.add_argument("--write-guards", action="store_true", help="Emit hardened middleware files")
    parser.add_argument("--endpoint", action="append", default=None,
                        help="Additional endpoint to probe (repeatable); defaults to common paths")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    endpoints = list(DEFAULT_ENDPOINTS)
    if args.endpoint:
        endpoints.extend(args.endpoint)
    endpoints = list(dict.fromkeys(endpoints))  # dedupe, preserve order

    print(f"[INFO] Probing {len(endpoints)} endpoint(s) on {base_url}")
    results = []
    all_findings = []
    for ep in endpoints:
        url = f"{base_url}{ep}"
        resp = fetch_headers(url)
        findings = check_headers(resp.get("headers", {}), url) if resp.get("headers") else []
        results.append({"url": url, "status": resp.get("status"), "error": resp.get("error"),
                        "headers": resp.get("headers", {}), "findings": findings})
        all_findings.extend(findings)
        if findings:
            print(f"  {url} [HTTP {resp.get('status')}]: {len(findings)} issue(s)")

    allowed_origins = []
    explicit_origins = re.findall(r"https?://[A-Za-z0-9._\-]+(?::\d+)?", " ".join(str(r.get("headers", {})) for r in results)) or \
                       ["http://localhost:3000", "http://127.0.0.1:3000"]

    report = {
        "target_url": base_url,
        "strict_csp": STRICT_CSP,
        "endpoints": results,
        "findings": all_findings,
        "summary": {
            "endpoints_probed": len(results),
            "total_findings": len(all_findings),
            "critical": sum(1 for f in all_findings if f["severity"] == "CRITICAL"),
            "high": sum(1 for f in all_findings if f["severity"] == "HIGH"),
            "medium": sum(1 for f in all_findings if f["severity"] == "MEDIUM"),
            "low": sum(1 for f in all_findings if f["severity"] == "LOW"),
        },
    }

    if args.write_guards:
        csp_file = report_dir / "strict_csp.txt"
        csp_file.write_text(STRICT_CSP + "\n", encoding="utf-8")
        helmet_file = generate_helmet_middleware(report_dir, allowed_origins or explicit_origins)
        fastapi_file = generate_fastapi_middleware(report_dir, allowed_origins or explicit_origins)
        report["generated"] = {
            "csp_file": str(csp_file),
            "helmet_middleware": str(helmet_file),
            "fastapi_middleware": str(fastapi_file),
        }
        print(f"[INFO] Wrote CSP:     {csp_file}")
        print(f"[INFO] Wrote helmet:  {helmet_file}")
        print(f"[INFO] Wrote fastapi: {fastapi_file}")

    report_path = report_dir / "headers_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n[INFO] Report: {report_path}")
    print(f"[INFO] Summary: {report['summary']}")


if __name__ == "__main__":
    main()
```

## 4. Execution Protocol & Step-by-Step Workflow
1. Start the local server you intend to harden (e.g. `node app.js` on port 3000).
2. Run header reconnaissance against it:
   ```bash
   python cors-csp-headers-hardener.md --url http://127.0.0.1:3000 --report-dir ./header-reports
   ```
3. Probe extra endpoints with `--endpoint /api/orders --endpoint /graphql` (repeatable).
4. Read `headers_report.json`: `endpoints[*].headers` (collected) and `findings` (gaps by severity).
5. Emit hardened middleware:
   ```bash
   python cors-csp-headers-hardener.md --url http://127.0.0.1:3000 --write-guards
   ```
6. For Express: `npm install helmet`, then wire `coreSecurity` + `corsAllowlist` from `helmet_hardened.js` into `app.use(...)`.
7. For FastAPI: `pip install fastapi`, wire `SecurityHeadersMiddleware` + `CORSMiddleware` from `fastapi_hardened.py`.
8. Re-run the scanner; all CRITICAL/HIGH findings must be resolved (CSP present with no `unsafe-inline` for scripts, no wildcard ACAO, HSTS/XFO/NOSNIFF present).

## 5. Edge Cases & Error Handling
- Unreachable endpoints: `fetch_headers` returns `status: null` with an `error` string; those probes are recorded but excluded from header analysis.
- HTTP error responses (401/404/500) still return their headers — 404 pages are often header-rich and worth scanning.
- CSP `upgrade-insecure-requests` is emitted but noted: if the site actively serves mixed HTTP subresources, test non-strict CSP first to avoid breaking load-out.
- `X-Frame-Options` and `frame-ancestors` are both emitted (defense in depth); some old browsers only honor XFO.
- The generated helmet config disables `crossOriginEmbedderPolicy` to avoid breaking cross-origin assets if not fully COEP-compliant.
- Disallowed CORS origins silently get NO ACAO header (browser enforces the block) instead of a 403 — prevents cross-origin exceptions from being readable by attackers.
- Wildcard ACAO + `Allow-Credentials: true` is flagged CRITICAL — browsers reject the combination, but the misconfiguration usually signals an origin-reflection bug.
