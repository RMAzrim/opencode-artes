#!/usr/bin/env python3
"""smoke_test.py - Project Auto Builder: execute each new skill's embedded
reference implementation and verify it runs (pure stdlib, offline)."""
import json
import re
import subprocess
import sys
import tempfile
import time
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS = pathlib.Path(ROOT, "skills")
FENCE = re.compile(r"```python\n(.*?)```", re.S)


def extract(code_name, skill_id):
    md = SKILLS / skill_id / f"{skill_id}.md"
    m = FENCE.search(md.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"[error] {skill_id}: no ```python block found")
    path = pathlib.Path(tempfile.mkdtemp(prefix=f"ab_{skill_id}_")) / code_name
    path.write_text(m.group(1), encoding="utf-8")
    return path


def run(py_path, args, cwd, timeout=60):
    start = time.time()
    try:
        proc = subprocess.run([sys.executable, str(py_path), *args],
                              capture_output=True, text=True, timeout=timeout,
                              cwd=cwd)
        tail = (proc.stdout or "")[-400:] + (proc.stderr or "")[-400:]
        ok = proc.returncode == 0
        return ok, round(time.time() - start, 1), tail
    except subprocess.TimeoutExpired:
        return False, None, "[timeout]"


def hashchain_cycle(py, cwd):
    ledger = cwd / "demo.json"
    steps = [
        (["init", str(ledger), "--genesis", "genesis-entry", "--key", "d3m0"], 0),
        (["append", str(ledger), "purchase#1", "purchase#2", "--key", "d3m0"], 0),
        (["verify", str(ledger), "--key", "d3m0"], 0),
    ]
    results = []
    for args, want in steps:
        actual_ok, elapsed, tail = run(py, args, cwd)
        results.append((actual_ok and actual_ok == (want == 0), elapsed, tail))
    # tamper probe: flip a char inside an entry, verify must FAIL
    raw = ledger.read_text(encoding="utf-8")
    ledger.write_text(raw.replace("purchase#1", "purchase#9"), encoding="utf-8")
    actual_ok, elapsed, tail = run(py, ["verify", str(ledger), "--key", "d3m0"], cwd)
    results.append((actual_ok is False, elapsed, tail))
    return results


def srt_cycle(py, cwd):
    fixture = {
        "id": "test-1",
        "duration_s": 120,
        "segments": [
            {"start": 0.0, "end": 6.0, "speaker": "P1", "text": "Welcome to the show."},
            {"start": 6.0, "end": 14.0, "speaker": "P2", "text": "Today that ETL pipeline design is the topic."},
            {"start": 14.0, "end": 30.0, "speaker": "P1", "text": "Let's also talk about the pipeline error cases."},
        ],
    }
    (cwd / "transcript.json").write_text(json.dumps(fixture), encoding="utf-8")
    actual_ok, elapsed, tail = run(py, ["transcript.json", "--out", "subs.srt", "--chapters", "ch.json",
                 "--clips", "clips.json", "--ffmpeg", "cut.sh", "--input", "ep.mp4",
                 "-k", "ETL, pipeline", "-c", "intro"], cwd, timeout=60)
    srt_ok = (cwd / "subs.srt").exists() and " --> " in (cwd / "subs.srt").read_text(encoding="utf-8")
    clips_ok = (cwd / "clips.json").exists()
    return [(actual_ok and srt_ok and clips_ok, elapsed, tail)]


def main():
    targets = [
        ("etl_pipeline.py", "etl-incremental-pipeline-builder", ["demo"]),
        ("llm_gateway.py", "llm-gateway-model-router", ["demo"]),
        ("portfolio_backtester.py", "portfolio-backtester", ["--demo"]),
        ("voice_turn_engine.py", "voice-agent-turn-engine", []),
        ("iot_hub.py", "iot-hub-dashboard-builder", ["demo", "3"]),
        ("bullet_patterns.py", "bullet-hell-pattern-generator",
         ["spiral", "--ticks", "40", "--frames", "frames.json"]),
        ("subdomain_scan.py", "subdomain-recon-osint-scanner", ["demo"]),
        ("svg_art.py", "generative-art-svg-engine", ["--seed", "1337", "--size", "128", "--out", "art.svg"]),
        ("hashchain_ledger.py", "tamper-proof-hashchain-ledger", None),   # special
        ("srt_automator.py", "transcript-to-srt-automator", None),        # special
    ]
    summary = []
    for code_name, skill_id, args in targets:
        py = extract(code_name, skill_id)
        cwd = pathlib.Path(py).parent
        if skill_id == "tamper-proof-hashchain-ledger":
            results = hashchain_cycle(py, cwd)
        elif skill_id == "transcript-to-srt-automator":
            results = srt_cycle(py, cwd)
        else:
            results = [run(py, args, cwd)]
        all_ok = all(res[0] for res in results)
        summary.append((skill_id, all_ok, results))
        status = "PASS" if all_ok else "FAIL"
        print(f"[{status}] {skill_id}")
        for res in results:
            print(f"    ok={res[0]} elapsed={res[1]}s tail={res[2][-160:]!r}")
    failed = [s for s, ok, _ in summary if not ok]
    print("\n== smoke summary ==")
    print(f"10 skills, {sum(1 for _, ok, _ in summary if ok)} passed, {len(failed)} failed")
    for f in failed:
        print(f"  FAILED: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())