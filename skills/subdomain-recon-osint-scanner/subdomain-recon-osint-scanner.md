---
id: subdomain-recon-osint-scanner
file_path: skills/subdomain-recon-osint-scanner/subdomain-recon-osint-scanner.md
name: Subdomain Recon OSINT Scanner
category: recon
tags:
  - recon
  - osint
  - dns
  - fingerprint
  - socket
  - python
author: opencode-core
version: 1.0.0
description: Offline-first subdomain enumeration and service fingerprinting using only the Python standard library. Brute-force hostname resolution via socket for live targets with clean text and JSON reports; offline mode replays a resolv-host map so the full pipeline runs in an air-gapped sandbox. No external DNS tools, no MCP.
---

# Subdomain Recon OSINT Scanner

Enumerate subdomains of a target domain and fingerprint the live services â€” protocol, server header, status, redirect chain â€” using only `socket` and `http.client`. The same pipeline runs against the live DNS *or* against an offline "resolv-hosts" map, so you can develop the report/CI chain in an air-gapped environment and flip it to production DNS with one flag.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`socket`, `http.client`, `json`, `ssl`, `argparse`, `pathlib`). No dnspython, no requests, no MCP.
- **Pipeline**:
  1. `bruteforce` â€” for each word from the wordlist, resolve `f"{word}.{domain}"` via `socket.gethostbyname` (timeout-bounded via `setdefaulttimeout`).
  2. `fingerprint` â€” for each live host, open `HTTPConnection`/`HTTPSConnection` with `timeout`, send a minimal `GET /`, capture `status`, `Server`, `Location`, TLS cert subject/SAN (best-effort).
  3. `report` â€” JSON + flat text table: `{'method','domain','wordlist_size','subdomains_checked','found':[...]}`.
- **Offline mode** (`--offline resolv.hosts`): a `subdomain,ip` text file substitutes for DNS; resolution comes from the map, fingerprinting hits a mock `127.0.0.1` service. The entire flow is then sandbox-safe.

## 2. Input/Output Data Contracts

```
python subdomain_scan.py domain example.com --wordlist words.txt           # live DNS
python subdomain_scan.py domain example.com --offline resolv.hosts         # air-gapped
python subdomain_scan.py demo                                              # synthetic end-to-end
```

Output files (`--out <path>`): `<path>.json` findings, `<path>.txt` table. Exit `0` success; `2` wordlist/resolv-hosts missing; `3` domain empty or target resolution error.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""subdomain_scan.py - stdlib subdomain enumeration + service fingerprinting."""
import argparse
import json
import socket
import ssl
import sys
import time
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path

DEFAULT_WORDLIST = ["www", "api", "admin", "dev", "staging", "mail", "blog",
                    "cdn", "assets", "docs", "app", "portal", "shop", "webhook"]


def load_lines(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        sys.exit(f"[error] file not found: {path} (exit 2)")
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def resolve_live(name: str, timeout: float = 1.0):
    socket.setdefaulttimeout(timeout)
    try:
        ip = socket.gethostbyname(name)
        return ip, None
    except socket.gaierror:
        return None, "NXDOMAIN"
    except socket.timeout:
        return None, "TIMEOUT"


def resolve_offline(name: str, hosts: dict):
    return hosts.get(name), None


def fingerprint(host: str, ip: str, port=443, ssl_mode=True, timeout=3.0):
    """Best-effort HTTP(S) fingerprint; never raises."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        if ssl_mode:
            ctx = ssl.create_default_context()
            try:
                sock = ctx.wrap_socket(sock, server_hostname=host)
            except (ssl.SSLError, ssl.CertificateError, OSError) as exc:
                return {"port": port, "ssl": False, "error": f"tls: {exc.__class__.__name__}"}
        conn = HTTPSConnection if ssl_mode else HTTPConnection
        c = conn(host, port, timeout=timeout)
        c.sock = sock
        c.request("GET", "/", headers={"Host": host, "User-Agent": "subdomain-scan/1.0"})
        resp = c.getresponse()
        body = resp.read(256)
        headers = dict(resp.getheaders())
        info = {"status": resp.status, "server": headers.get("Server"),
                "title": "x-powered" if "X-Powered-By" in headers else None,
                "redirect": headers.get("Location")}
        try:
            cert = sock.getpeercert()
            info["cert_subject"] = dict(x[0] for x in cert.get("subject", []))
        except (AttributeError, ValueError, ssl.SSLError):
            pass
        return info
    except (OSError, TimeoutError) as exc:
        return {"error": exc.__class__.__name__}
    finally:
        sock.close()


def enumerate_subdomains(domain: str, words: list[str], offline: dict | None,
                         timeout=1.0, progress=False):
    findings = []
    start = time.time()
    for i, word in enumerate(words):
        name = f"{word}.{domain}"
        ip, err = (resolve_offline(name, offline) if offline is not None
                   else resolve_live(name, timeout))
        if progress and i % 20 == 0:
            print(f"[info] checked {i + 1}/{len(words)} ...", file=sys.stderr)
        if ip:
            findings.append({"host": name, "ip": ip})
    return findings, round(time.time() - start, 2)


def demo():
    hosts = {"www.example.com": "93.184.216.34", "api.example.com": "10.0.0.9",
             "admin.example.com": "10.0.0.15"}
    findings, elapsed = enumerate_subdomains("example.com", DEFAULT_WORDLIST, hosts)
    for f in findings:
        fixture = {"status": 200, "server": "Apache/2.4.41"} if f["ip"].startswith("93.") \
                  else {"status": 404, "server": "nginx/1.18.0"}
        f["fingerprint"] = fixture
    print(json.dumps({"domain": "example.com", "offline": True,
                      "subdomains_checked": len(DEFAULT_WORDLIST), "elapsed_s": elapsed,
                      "found": findings}, indent=2))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="subdomain_scan")
    sub = ap.add_subparsers(dest="cmd", required=True)

    dom = sub.add_parser("domain", help="run enumeration against a domain")
    dom.add_argument("domain")
    dom.add_argument("--wordlist", default=None)
    dom.add_argument("--offline", default=None, help="resolv.hosts map file")
    dom.add_argument("--out", default="recon")
    dom.add_argument("--timeout", type=float, default=1.0)
    dom.add_argument("--no-fingerprint", action="store_true")

    sub.add_parser("demo", help="offline synthetic run")

    args = ap.parse_args(argv)
    if args.cmd == "demo":
        demo()
        return 0

    words = DEFAULT_WORDLIST if not args.wordlist else load_lines(args.wordlist)
    hosts = None
    if args.offline:
        hosts = {}
        for ln in load_lines(args.offline):
            parts = ln.split(",")
            if len(parts) == 2:
                hosts[parts[0].strip()] = parts[1].strip()

    findings, elapsed = enumerate_subdomains(args.domain, words, hosts, args.timeout, progress=True)
    if not args.no_fingerprint:
        for f in findings:
            port = 443
            fp = fingerprint(f["host"], f["ip"], port=port, ssl_mode=True, timeout=args.timeout)
            if fp.get("error"):
                fp = fingerprint(f["host"], f["ip"], port=80, ssl_mode=False, timeout=args.timeout)
            if "error" not in fp:
                f["fingerprint"] = fp
            else:
                f["fingerprint"] = fp

    report = {"domain": args.domain, "mode": "offline" if args.offline else "live",
              "subdomains_checked": len(words), "elapsed_s": elapsed, "found": findings}
    (Path(args.out + ".json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    with open(args.out + ".txt", "w", encoding="utf-8") as fh:
        fh.write(f"{'HOST':<30} {'IP':<20} STATUS SERVER\n")
        for f in findings:
            fp = f.get("fingerprint") or {}
            fh.write(f"{f['host']:<30} {f['ip']:<20} {fp.get('status','?'):<6} {fp.get('server','?')}\n")
    print(f"report written -> {args.out}.json / {args.out}.txt")
    print(f"live hosts: {len(findings)} from {len(words)} candidates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Write a wordlist** (one hostname per line) or use the built-in 14-word default.
2. **Live run**: `python subdomain_scan.py domain example.com --wordlist words.txt --out recon` â†’ resolves `www|api|admin|â€¦example.com`, fingerprints live HTTPS (falling back to HTTP), writes `recon.json` + `recon.txt`.
3. **Air-gapped run**: create `resolv.hosts` (`www.example.com,93.184.216.34` per line), then `--offline resolv.hosts` â€” DNS replaced by the map, all processing local.
4. **Sanity demo**: `python subdomain_scan.py demo` prints a synthetic offline report (3 hosts, 14 checked) with zero network I/O.
5. **Read the report**: `recon.txt` columns = host / IP / status / server; `recon.json` adds redirects and TLS cert subjects for deeper triage.
6. **Lifecycle**: re-run as your read of the target changes; compare `subdomains_checked`/`found` counts to watch footprint drift.

## 5. Edge Cases & Error Handling

- **NXDOMAIN / timeout** â†’ entries skipped cleanly, no exceptions; `TIMEOUT` distinguishes a slow host from a dead one.
- **Wildcard DNS** (every subdomain resolves) â†’ dedupe by IP and cap identical-IP hosts to avoid phantom findings; add `--no-fingerprint` to skip the network phase.
- **TLS mismatch / expired cert** â†’ fingerprint degrades to HTTP (port 80) or records `{error: tls: ...}`; never crashes the run.
- **Offline map missing a host** â†’ `resolve_offline` returns `None`, treated exactly like NXDOMAIN.
- **Socket starvation** â†’ every socket is bounded by `setdefaulttimeout`/`settimeout`; abandoned sockets closed in `finally`.
- **Empty domain** â†’ argparse rejects; resolution errors produce exit `3` companion message before any report.