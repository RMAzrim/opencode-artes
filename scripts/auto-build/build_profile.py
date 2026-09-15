#!/usr/bin/env python3
"""Project Auto Builder - steps 1-3: registry inspection, workspace analysis, dynamic matching.

Emits three artifacts next to this script:
  registry-index.json  - condensed {id: {name, category, tags, description}}
  workspace-profile.json - detected stack, runtime versions, markers
  skill-order.json     - execution order with match scores for a target skill set
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REGISTRY = ROOT / "registry.json"

NEW_SKILLS = {
    "voice-agent-turn-engine": {"categories": ["voice-ai", "mlops"], "tags": ["speech", "pipeline", "barge-in", "turn"]},
    "llm-gateway-model-router": {"categories": ["mlops", "backend", "api"], "tags": ["gateway", "routing", "fallback", "quota"]},
    "etl-incremental-pipeline-builder": {"categories": ["data-engineering", "database", "data"], "tags": ["etl", "sqlite", "watermark", "idempotent"]},
    "bullet-hell-pattern-generator": {"categories": ["game-dev", "creative-coding"], "tags": ["game", "deterministic", "pattern", "svg"]},
    "generative-art-svg-engine": {"categories": ["creative-coding", "frontend"], "tags": ["generative", "svg", "seeded", "art"]},
    "subdomain-recon-osint-scanner": {"categories": ["recon", "security"], "tags": ["recon", "osint", "dns", "fingerprint"]},
    "iot-hub-dashboard-builder": {"categories": ["iot", "backend", "data"], "tags": ["iot", "pubsub", "telemetry", "rules"]},
    "portfolio-backtester": {"categories": ["fintech", "data", "data-science"], "tags": ["finance", "backtest", "sharpe", "montecarlo"]},
    "transcript-to-srt-automator": {"categories": ["media", "content"], "tags": ["subtitles", "srt", "transcript", "chapters"]},
    "tamper-proof-hashchain-ledger": {"categories": ["blockchain", "security", "data"], "tags": ["hashchain", "merkle", "sha256", "verification"]},
}

STACK_MARKERS = {
    "node": ["package.json", "node_modules", "tsconfig.json", "build-registry.js"],
    "python": ["requirements.txt", "pyproject.toml", "setup.py", ".python-version"],
    "docker": ["Dockerfile", "docker-compose.yml", ".dockerignore"],
}

CATEGORY_RANK = {
    "data-engineering": 10, "mlops": 10, "fintech": 9, "recon": 8, "blockchain": 8,
    "iot": 8, "game-dev": 8, "creative-coding": 7, "media": 7, "voice-ai": 8,
}
STACK_TAG_OVERLAP = {"python": ["py", "stdlib", "python", "sqlite", "asyncio"]}


def run(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (out.stdout or out.stderr).strip()
    except Exception as exc:
        return f"unavailable ({exc})"


def inspect_registry():
    if not REGISTRY.exists():
        sys.exit("Registry corrupted: cannot proceed with auto-build")
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        sys.exit("Registry corrupted: invalid JSON")
    if not isinstance(data, list) or any(
        not all(k in item for k in ("id", "name", "category", "tags", "description")) for item in data
    ):
        sys.exit("Registry corrupted: schema mismatch")
    cats = {}
    for item in data:
        cats.setdefault(item["category"], []).append(item["id"])
    index = {item["id"]: {"name": item["name"], "category": item["category"], "tags": item["tags"], "description": item["description"]} for item in data}
    return data, index, cats


def analyze_workspace():
    markers = {stack: [str(ROOT.joinpath(m)) for m in files if ROOT.joinpath(m).exists()] for stack, files in STACK_MARKERS.items()}
    markers = {k: v for k, v in markers.items() if v}
    primary = "mixed" if len(markers) > 1 else (next(iter(markers)) if markers else "unknown")
    profile = {
        "primary_stack": primary,
        "secondary_stack": None if len(markers) <= 1 else [m for m in markers if m != primary],
        "versions": {"python": run(["python", "--version"]), "node": run(["node", "--version"])},
        "markers": markers,
    }
    return profile


def score(skill_id, spec, profile):
    score_val = 0
    tags = " ".join(spec["tags"])
    for cat in spec["categories"]:
        score_val += CATEGORY_RANK.get(cat, 5)
    if profile["primary_stack"] in ("python", "mixed") or profile["versions"].get("python", "unavailable").lower().startswith("python"):
        score_val += 15  # stdlib python implementations are first-class here
    for tok in STACK_TAG_OVERLAP.get("python", []):
        if tok in tags.lower():
            score_val += 2
    return score_val


def main():
    data, index, cats = inspect_registry()
    profile = analyze_workspace()
    order = [
        {"id": sid, "score": score(sid, spec, profile), "categories": spec["categories"], "reason": "deterministic stdlib-python module, matches mixed node+python stack"}
        for sid, spec in sorted(NEW_SKILLS.items(), key=lambda kv: -score(kv[0], kv[1], profile))
    ]
    (OUT / "registry-index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    (OUT / "workspace-profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    (OUT / "skill-order.json").write_text(json.dumps(order, indent=2), encoding="utf-8")
    print(f"registry: {len(data)} skills, {len(cats)} categories")
    print(f"stack: {profile['primary_stack']} ({', '.join(profile['markers'])})")
    print(f"matched execution order: {', '.join(item['id'] for item in order)}")
    print(f"artifacts written to {OUT}")


if __name__ == "__main__":
    main()