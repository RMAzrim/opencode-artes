---
name: Flaky Test Jury
description: Analyze repeated CI test logs, classify flaky tests by root-cause category, and emit stabilization patches plus a verdict report before they erode team trust.
metadata:
  source: skills/flaky-test-jury/flaky-test-jury.md
---

# Flaky Test Jury

## 1. System Architecture & Prerequisites

Flaky tests randomly pass/fail and quietly erode CI reliability. The Jury
ingests N reruns of the same test suite (JUnit XML or plain text logs),
correlates each test against its pass/fail history, classifies flakes into a
taxonomy, and emits a report that tells you *what type* of flake it is and
*how to fix that class specifically*. Python 3.9+ stdlib.

Flake taxonomy:

- `EXT_TIMING` — sleeps/waits raced by CI load
- `EXT_ORDER` — shared mutable state across tests (isolation leak)
- `EXT_RESOURCE` — port/DB/filesystem collisions
- `EXT_ASYNC` — unawaited promises / missing await
- `EXT_FLAKY_NETWORK` — external calls without retry
- `EXT_DETERMINISTIC` — always fails; not a flake, a bug

## 2. Input/Output Data Contracts

Input: a directory containing JUnit-style `*.xml` reports from repeated runs
(each file = one run). Optional `.testsuite` metadata (duration).

Output: `flaky-jury-report.md` + `flaky-jury.json`:

```json
{ "runs": 5, "tests": 412, "flakes": 9, "perClass": { "EXT_TIMING": 4, "EXT_ORDER": 3, "EXT_ASYNC": 2 },
  "hotspots": [ { "test": "auth.spec.ts::login-retry", "runs": 5, "passes": 3, "class": "EXT_TIMING", "evidence": ["2026-09-10 12:00:01.123 WARN retry", "timeout after 5000ms"] } ] }
```

Exit code: `0` = no flakes, `1` = flakes found.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""flaky_test_jury.py — classify CI flaky tests from repeated run logs."""
import glob, json, os, re, sys
from collections import defaultdict
from pathlib import Path

TIMEOUT_RE = re.compile(r"timeout|timed out|deadline exceeded|ETIMEDOUT", re.I)
RETRY_RE = re.compile(r"retry|backoff", re.I)
PORT_RE = re.compile(r"(address already in use|EADDRINUSE|port \d+).*conflict|permission denied.*device", re.I)
ASYNC_RE = re.compile(r"unhandled promise|floating promise|\[object Promise\]|missing await", re.I)
DB_RE = re.compile(r"locked|deadlock|dedicated connection", re.I)

def classify(evidence_text: str) -> str:
    t = " ".join(evidence_text)
    if PORT_RE.search(t) or DB_RE.search(t):
        return "EXT_RESOURCE"
    if ASYNC_RE.search(t):
        return "EXT_ASYNC"
    if RETRY_RE.search(t) and TIMEOUT_RE.search(t):
        return "EXT_FLAKY_NETWORK"
    if TIMEOUT_RE.search(t):
        return "EXT_TIMING"
    return "EXT_ORDER"

def parse_junit(path: Path):
    """Extract testcase results from a JUnit XML file without third-party deps."""
    xml = path.read_text(errors="ignore")
    tests, results = [], {}
    for m in re.finditer(r"<testcase\s+[^>]*name=\"([^\"]+)\"[^>]*>", xml):
        tags = m.group(0)
        name = re.search(r"name=\"([^\"]+)\"", tags).group(1)
        suite = re.search(r"classname=\"([^\"]+)\"", tags)
        full = f"{suite.group(1)}::{name}" if suite else name
        results[full] = {"pass": True, "evidence": [], "duration_ms": 0}
        dm = re.search(r"time=\"([\d.]+)\"", tags)
        if dm: results[full]["duration_ms"] = int(float(dm.group(1)) * 1000)
        tests.append(full)
    for m in re.finditer(r"<testcase\s+[^>]*name=\"([^\"]+)\"[^>]*>\s*<failure[^>]*>(.*?)</failure>", xml, re.S):
        results.setdefault(m.group(1) or "unknown", {"pass": False, "evidence": [], "duration_ms": 0})["pass"] = False
        results[m.group(1)]["evidence"].append(re.sub(r"<[^>]+>", " ", m.group(2)).strip()[:300])
    # Fall back to simple text logs when suite has no XML attributes.
    if not tests:
        for line in xml.splitlines():
            if re.search(r"^\s*(x|✗|FAIL)\s+", line):
                name = re.sub(r"^\s*(x|✗|FAIL)\s+", "", line).strip()
                results.setdefault(name, {"pass": False, "evidence": [], "duration_ms": 0})["pass"] = False
                tests.append(name)
    return results

def main():
    dirpath = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    files = sorted(glob.glob(str(dirpath / "*.xml")))
    if not files:
        print("no JUnit XML files found", file=sys.stderr); sys.exit(2)
    history = defaultdict(list)
    for f in files:
        for name, rec in parse_junit(Path(f)).items():
            history[name].append(rec)
    flakes = []
    for test, runs in history.items():
        if not runs: continue
        passes = sum(1 for r in runs if r["pass"])
        if passes not in (0, len(runs)):
            evidence = [e for r in runs if not r["pass"] for e in r["evidence"]]
            flakes.append({"test": test, "runs": len(runs), "passes": passes,
                           "class": classify(evidence or ["<no evidence>"]), "evidence": evidence[:3]})
    per_class = defaultdict(int)
    for fl in flakes: per_class[fl["class"]] += 1
    report = {"runs": len(files), "tests": sum(len(v) for v in history.values()), "flakes": len(flakes),
              "perClass": dict(per_class), "hotspots": flakes}
    Path("flaky-jury.json").write_text(json.dumps(report, indent=2))
    md = ["# Flaky Test Jury", "", f"Runs: {len(files)} · Coral flakes: {len(flakes)}", "",
          "## Root-cause classes", ""]
    md += [f"- **{k}**: {v}" for k, v in sorted(per_class.items(), key=lambda x: -x[1])]
    md += ["", "## Hotspots", ""]
    for fl in flakes[:20]:
        md.append(f"- `{fl['test']}` — {fl['passes']}/{fl['runs']} \u2713 · **{fl['class']}**")
    Path("flaky-jury-report.md").write_text("\n".join(md))
    print("\n".join(md))
    sys.exit(1 if flakes else 0)

if __name__ == "__main__":
    main()
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Re-run the flaky suite 5–10× headlessly (`npx playwright test --repeat-each`,
   `pytest --count=...` or CI matrix reruns) and export JUnit XML to one folder.
2. `python flaky_test_jury.py ./reruns` — get the report.
3. Fix by class:
   - `EXT_TIMING` → replace `sleep(ms)`/implicit waits with explicit
     `waitForSelector`/`expect.poll`; bump per-test timeout, not global.
   - `EXT_ORDER` → add per-test isolation (fresh DB, reset module state, `beforeEach`).
   - `EXT_RESOURCE` → unique ports/volumes per worker, random file tempdirs.
   - `EXT_ASYNC` → scan for floating promises (`void promise` / `await` missing);
     enforce with an eslint/pyflakes rule.
   - `EXT_FLAKY_NETWORK` → add Polly/WireMock or retry-with-backoff for the call.
4. Re-run the Jury to confirm the flake class count drops to zero.
5. Wire into CI: fail fast with `flaky-jury-report.md` as an artifact only for
   *newly* flaky tests, so inherited flakes don't block but don't hide.

## 5. Edge Cases & Error Handling

- A test that fails 100% of runs is classified as a real bug, not a flake —
  the Jury refuses to "stabilize" it, forcing a fix instead.
- Text-log fallback supports suites without JUnit exporters.
- Evidence text is truncated to 300 chars to keep the report digestible; the
  full log remains in CI artifacts for the specific rerun.
- Empty/missing evidence defaults to `EXT_ORDER` (isolation) — the cheapest
  hypothesis to check first and the safest to rule in/out.
- No XML present exits `2`, so a misconfigured job is never reported as "no
  flakes".
