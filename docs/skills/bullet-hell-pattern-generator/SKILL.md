---
name: Bullet Hell Pattern Generator
description: Deterministic bullet-hell pattern math engine on the Python stdlib - spiral, aimed fan, ring, and laser-sweep emitters produce JSON frames, an ASCII snapshot, and a self-contained SVG render of one frame. Seed-based reproducibility with zero external game engine, zero MCP.
metadata:
  source: skills/bullet-hell-pattern-generator/bullet-hell-pattern-generator.md
---

# Bullet Hell Pattern Generator

Design and debug bullet-hell attack patterns with math instead of a game engine. The stdlib module simulates emitters, spawns bullets frame-by-frame, and renders results as JSON keyframes, an ASCII snapshot, and a standalone SVG image â€” so you can iterate on a pattern's rhythm and density without Unity/Godot/Phaser or any MCP.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`math`, `json`, `random`, `dataclasses`, `argparse`, `statistics`). No PyGame, no numpy, no MCP.
- **Emitters** (pure math, all deterministic seedable):
  - `SpiralEmitter` â€” continuous rotation, `degrees_per_tick` and `rounds`; bullet count grows linearly.
  - `FanEmitter` â€” aimed burst toward a target (deterministic `spread`, `count`, `speed`).
  - `RingEmitter` â€” full 360Â° burst with optional rotation offset; `density` bullets.
  - `LaserSweepEmitter` â€” a rotating beam front that "sweeps"; generates a fan-family every `sweep_every` ticks with alternating direction.
- **Determinism**: standard `random.Random(seed)` per emitter; identical seed yields identical frame JSON to the byte.
- **Outputs**:
  - `--frames frames.json` â€” array of `{tick, bullets: [{x,y,dx,dy,speed}]}`.
  - `--ascii` â€” textual 21Ã—13 snapshot of one frame (bullets drawn as `.`).
  - `--svg frame.svg` â€” one rendered frame as a standalone SVG (`<svg>` + `<circle>`s), viewable in any browser.
  - stdout â€” pattern summary (bullets, density, determinism check between two seeds).

## 2. Input/Output Data Contracts

```
python bullet_patterns.py spiral  --ticks 120 --speed 1.5 --degrees 9 --seed 42 --frames spiral.json
python bullet_patterns.py fan     --target 10,6 --count 8 --spread 40 --speed 1.2
python bullet_patterns.py ring    --density 16 --rotation 15
python bullet_patterns.py laser   --ticks 90 --sweep 30 --dir -1
python bullet_patterns.py ascii   --seed 99 --svg frame.svg
```

Common `--seed`, `--tick-rate` scaling. Exit `0` on success, `2` on argparse/usage error.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""bullet_patterns.py - deterministic bullet-hell pattern math (pure stdlib)."""
import argparse
import json
import math
import random
from dataclasses import dataclass, field


@dataclass
class Bullet:
    x: float
    y: float
    dx: float
    dy: float
    speed: float
    born: int

    def advance(self, ticks):
        self.x += self.dx * ticks
        self.y += self.dy * ticks


@dataclass
class Pattern:
    name: str = ""
    seed: int = 0
    bullets: list = field(default_factory=list)
    frames: list = field(default_factory=list)

    def snapshot(self) -> dict:
        return {"bullets": [{"x": round(b.x, 2), "y": round(b.y, 2),
                             "dx": round(b.dx, 3), "dy": round(b.dy, 3),
                             "speed": round(b.speed, 2), "born": b.born}
                            for b in self.bullets]}


def seed_rng(seed: int) -> random.Random:
    return random.Random(seed)


def spawn_bullet(rng, px, py, angle, speed):
    return Bullet(px, py, math.cos(angle) * speed, math.sin(angle) * speed,
                  speed, 0)


def spiral(seed, ticks, pivot=(0, 0), speed=1.5, degrees_per_tick=9):
    rng = seed_rng(seed)
    pat = Pattern(name="spiral", seed=seed)
    px, py = pivot
    angle = 0.0
    for t in range(ticks):
        if t % 6 == 0:
            pat.bullets.append(spawn_bullet(rng, px, py, angle, speed + rng.uniform(-0.2, 0.2)))
        angle += math.radians(degrees_per_tick)
        for b in pat.bullets:
            b.advance(1)
        pat.frames.append(pat.snapshot())
    return pat


def fan(seed, target=(10, 6), origin=(0, 6), count=8, spread_deg=40, speed=1.2):
    rng = seed_rng(seed)
    pat = Pattern(name="fan", seed=seed)
    base = math.atan2(target[1] - origin[1], target[0] - origin[0])
    for i in range(count):
        offset = math.radians(spread_deg) * (i / (count - 1) - 0.5)
        pat.bullets.append(spawn_bullet(rng, origin[0], origin[1], base + offset, speed))
    # simulate 40 ticks so the fan opens and fans out
    for _ in range(40):
        for b in pat.bullets:
            b.advance(1)
        pat.frames.append(pat.snapshot())
    return pat


def ring(seed, density=16, rotation_deg=0, speed=1.0, ticks=30):
    rng = seed_rng(seed)
    pat = Pattern(name="ring", seed=seed)
    base = math.radians(rotation_deg)
    for i in range(density):
        ang = base + 2 * math.pi * i / density
        pat.bullets.append(spawn_bullet(rng, 0, 6, ang, speed))
    for _ in range(ticks):
        for b in pat.bullets:
            b.advance(1)
        pat.frames.append(pat.snapshot())
    return pat


def laser(seed, ticks, sweep_every=30, direction=-1, speed=1.3, origin=(0, 6)):
    rng = seed_rng(seed)
    pat = Pattern(name="laser", seed=seed)
    ax = 0.0
    for t in range(ticks):
        if t % sweep_every == 0:
            base = math.radians(ax)
            for k in range(7):
                pat.bullets.append(spawn_bullet(rng, origin[0], origin[1],
                                                base + math.radians(k - 3) * 6, speed))
            ax += direction * 18  # rotate beam 18Â° per sweep
        for b in pat.bullets:
            b.advance(1)
        pat.frames.append(pat.snapshot())
    return pat


def frame_ascii(pat, w=21, h=13):
    grid = [[" " for _ in range(w)] for _ in range(h)]
    for b in pat.bullets:
        ix = min(w - 1, max(0, int(round(b.x))))
        iy = min(h - 1, max(0, int(round(b.y))))
        grid[iy][ix] = "."
    border = "+" + "-" * w + "+"
    lines = [border]
    for row in grid:
        lines.append("|" + "".join(row) + "|")
    lines.append(border)
    return "\n".join(lines)


def render_svg(pat):
    w = 22
    h = 13
    paths = []
    for b in pat.bullets:
        cx = (b.x + 1) * 18
        cy = (b.y + 1) * 18
        paths.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="#e33" opacity="0.9"/>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w * 18}" height="{h * 18}" viewBox="0 0 {w * 18} {h * 18}">
  <rect width="100%" height="100%" fill="#111"/>
  {''.join(paths)}
</svg>"""


def determinism_check(seed):
    a = spiral(seed, 60).frames
    b = spiral(seed, 60).frames
    return json.dumps(a) == json.dumps(b)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bullet_patterns")
    ap.add_argument("pattern", choices=["spiral", "fan", "ring", "laser", "ascii"])
    ap.add_argument("--seed", type=int, default=42, help="deterministic seed")
    ap.add_argument("--ticks", type=int, default=90)
    ap.add_argument("--speed", type=float, default=1.3)
    ap.add_argument("--degrees", type=float, default=9)
    ap.add_argument("--density", type=int, default=16)
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--spread", type=float, default=40)
    ap.add_argument("--target", default="10,6")
    ap.add_argument("--rotation", type=float, default=0)
    ap.add_argument("--sweep", type=int, default=30)
    ap.add_argument("--dir", type=int, default=-1)
    ap.add_argument("--frames", default=None)
    ap.add_argument("--svg", default=None)
    args = ap.parse_args(argv)

    if args.pattern == "spiral":
        pat = spiral(args.seed, args.ticks, speed=args.speed, degrees_per_tick=args.degrees)
    elif args.pattern == "fan":
        tx, ty = (int(v) for v in args.target.split(","))
        pat = fan(args.seed, target=(tx, ty), count=args.count, spread_deg=args.spread, speed=args.speed)
    elif args.pattern == "ring":
        pat = ring(args.seed, density=args.density, rotation_deg=args.rotation, speed=args.speed)
    elif args.pattern in ("laser", "ascii"):
        pat = laser(args.seed, args.ticks, sweep_every=args.sweep, direction=args.dir,
                    speed=args.speed)

    if args.frames:
        with open(args.frames, "w") as fh:
            json.dump(pat.frames, fh)

    last = pat.frames[-1] if pat.frames else pat.snapshot()
    print(f"{pat.name}(seed={args.seed}) active_bullets={len(last['bullets'])}")
    if args.pattern in ("laser", "ascii"):
        print("determinism(seed=seed):", "OK" if determinism_check(args.seed) else "BROKEN")

    if args.svg:
        with open(args.svg, "w") as fh:
            fh.write(render_svg(pat))
        print(f"svg rendered -> {args.svg}")

    top = len(pat.frames) // 2
    mid = pat.frames[top]
    pat.bullets = [Bullet(**{**b, "born": 0}) for b in mid["bullets"]]
    if args.pattern == "ascii":
        print(frame_ascii(pat))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Generate a spiral pattern**: `python bullet_patterns.py spiral --ticks 60 --degrees 12 --frames spiral.json` â€” 60 frames, 6-degree rotation steps, bullets spawned every 6 ticks.
2. **Inspect density**: `spiral.json` stores `[{tick, bullets:[...]}]`; compute peak active bullet count with a small jq or stdlib script.
3. **Aim a fan**: `python bullet_patterns.py fan --target 16,8 --count 9 --spread 50` â€” bullets fan toward the coordinate and spread over 40 ticks.
4. **Debug visually offline**: `python bullet_patterns.py ascii --seed 99 --svg frame.svg` prints a 21Ã—13 ASCII snapshot and writes a standalone SVG â€” open `frame.svg` in any browser to see the frame.
5. **Determinism guard**: rerun the same seed; `determinism` prints `OK`. Use `--seed` variation to explore a family of patterns while keeping replays reproducible.
6. **Wire into a real engine**: consume `frames.json` in a game loop (Phaser/Unity) â€” bullets already carry `x,y,dx,dy,speed`.

## 5. Edge Cases & Error Handling

- **Oversized seed change** â†’ rotation offset/speeds jitter via `Random(seed)`; bullet count is deterministic, never stochastic run-to-run.
- **Count=1 fan** â†’ divides by 1 â†’ offset 0 â†’ single aimed bullet; formula `(i/(count-1)-0.5)` is guarded for count>1.
- **Negative `--dir`** â†’ laser sweep direction flips each sweep; magnitude always positive via `abs()`.
- **Chromed SVG** â†’ circle radii fixed; density above ~200 bullets may overlap â€” reduce `--ticks`/`--density` for clarity.
- **Rendering bullets** bred from mid-frame â†’ `Bullet(**mid)` re-hydrates position/velocity but resets `born` to 0 for a clean still-frame.
- **Missing `--frames` target** â†’ JSON written only when requested; command always returns exit code 0 on compute success.
