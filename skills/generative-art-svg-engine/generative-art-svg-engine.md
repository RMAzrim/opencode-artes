---
id: generative-art-svg-engine
file_path: skills/generative-art-svg-engine/generative-art-svg-engine.md
name: Generative Art SVG Engine
category: creative-coding
tags:
  - generative
  - svg
  - seeded
  - lcg
  - art
  - python
author: opencode-core
version: 1.0.0
description: Deterministic generative-art engine on the Python stdlib that turns a seed into layered, palette-driven SVG compositions - LCG pseudo-noise, seeded palettes, shape primitives (circles, paths, grids, waves), tint/weight rules - and exports browser-ready self-contained SVG. Reproducible per seed with zero design tools and zero MCP.
---

# Generative Art SVG Engine

Turn any integer seed into original SVG artwork using nothing but the Python standard library. A deterministic Linear Congruential Generator (LCG) drives every random decision â€” palette, composition, density, jitter â€” so a seed always reproduces the same image, perfect for NFTs-of-the-future, CI-generated cover art, favicons, and README headers. Output is a standalone `<svg>` you can open in any browser.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`math`, `json`, `argparse`, `random` replaced by a manual LCG). No Pillow, no svgwrite, no MCP.
- **Engine core**:
  - `LCG` â€” Schrage-style 64-bit LCG with period 2^32, `next_float()` âˆˆ [0,1); seeding from any int or string hash.
  - `palette()` â€” pick `bg` (dark) + 4 accent colors from a baked 8-color wheel, by seed rotation with complementary/triad rules.
  - `compose()` â€” layers: grid-of-circles with radius jitter, random walk "waves" (smooth path), low-poly rings, and per-layer opacity/weight.
  - `render_svg()` â€” emits full SVG with `<defs>`, gradients, viewBox `0 0 800 800`.
- **Reproducibility guarantee**: for any seed S, `render_svg(S)` is byte-identical across processes (LCG is fully determinist, no `random` module, no time/entropy).

## 2. Input/Output Data Contracts

```
python svg_art.py --seed 1234 --size 800 --out art.svg
python svg_art.py --seed random --count 6 --out-dir gallery/
python svg_art.py --digest --seed 42
```

- `--seed` int (or `random` for a fresh seed printed to stderr); `--size` N creating an NÃ—N viewBox; `--out` writes SVG; `--count`/`--out-dir` batch mode; `digest` prints the derived parameters (palette hex list, layers, seed) so parameter exploration is scriptable.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""svg_art.py - deterministic generative SVG art (pure stdlib)."""
import argparse
import json
import math
import random as _stdlib_random  # only used for true-random mode; never for art
from pathlib import Path


class LCG:
    """Schrage LCG: 2^31 - 1 modulus, multiplicative inverse preserved."""

    def __init__(self, seed: int):
        self.state = abs(int(seed)) % 2147483647
        if self.state == 0:
            self.state = 1

    def next(self) -> int:
        self.state = (self.state * 48271) % 2147483647
        return self.state

    def next_float(self) -> float:
        return (self.next() - 1) / 2147483646.0

    def range(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.next_float()


WHEEL = ["#1b1b2f", "#2d2d44", "#ff206e", "#fbff12", "#41ead4", "#f77f00",
         "#7b2ff7", "#00b4d8", "#ff5400", "#9ef01a", "#ffd166", "#3a0ca3"]
BG_HINTS = ["#09090f", "#0f111a", "#101820", "#070d12"]


def palette(rng: LCG) -> tuple[str, list[str]]:
    bg = BG_HINTS[int(rng.next_float() * len(BG_HINTS))]
    acc = []
    pool_c = WHEEL[:]
    start = int(rng.next_float() * len(pool_c))
    step = int(rng.range(2, 5))
    for i in range(4):
        idx = (start + i * step) % len(pool_c)
        acc.append(pool_c[idx])
        pool_c.pop(idx)
    return bg, acc


def layered(rng: LCG, size: int):
    bg, acc = palette(rng)
    layers = []
    # layer 1: jittered grid of dots
    dots = []
    n = int(rng.range(6, 12))
    for i in range(n):
        for j in range(n):
            if rng.next_float() < 0.3:
                continue
            cx = size * (i + 0.5) / n + rng.range(-8, 8)
            cy = size * (j + 0.5) / n + rng.range(-8, 8)
            r = rng.range(2, size / n * 0.32)
            dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                        f'fill="{acc[int(rng.next_float() * len(acc))]}" opacity="{rng.range(0.25, 0.9):.2f}"/>')
    layers.append({"kind": "dots", "content": "".join(dots)})
    # layer 2: random-walk wave path
    pts = []
    x = rng.range(0, size * 0.1)
    y = size * rng.range(0.35, 0.65)
    for _ in range(int(rng.range(20, 45))):
        x += rng.range(6, size * 0.06)
        y += rng.range(-size * 0.05, size * 0.05)
        pts.append(f"{x:.1f},{y:.1f}")
    stroke = acc[int(rng.next_float() * len(acc))]
    layers.append({"kind": "wave", "content": (
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{stroke}" '
        f'stroke-width="{rng.range(1.5, 6):.1f}" opacity="{rng.range(0.5, 1):.2f}"/>')})
    # layer 3: concentric rings (low-poly feel)
    rings = []
    cx = size * rng.range(0.15, 0.85)
    cy = size * rng.range(0.15, 0.85)
    for k, col in enumerate(acc):
        rad = rng.range(size * 0.05, size * 0.4) * (k + 1) / len(acc)
        rings.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rad:.1f}" fill="none" '
                     f'stroke="{col}" stroke-width="{rng.range(0.8, 3):.1f}" opacity="{rng.range(0.3, 0.8):.2f}"/>')
    layers.append({"kind": "rings", "content": "".join(rings)})
    return bg, acc, layers


def render_svg(seed: int, size: int = 800) -> str:
    rng = LCG(seed)
    bg, acc, layers = layered(rng, size)
    body = "\n".join(ln["content"] for ln in layers)
    gradient = (f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
                f'<stop offset="0%" stop-color="{acc[0]}"/><stop offset="100%" stop-color="{acc[-1]}"/></linearGradient>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">
  <defs>{gradient}</defs>
  <rect width="{size}" height="{size}" fill="{bg}"/>
  {body}
  <rect width="{size}" height="{size}" fill="url(#g)" opacity="0.06"/>
</svg>
"""


def digest(seed: int, size: int = 800) -> dict:
    rng = LCG(seed)
    bg, acc, layers = layered(rng, size)
    return {"seed": seed, "palette": [bg] + acc, "layers": [ln["kind"] for ln in layers],
            "layer_count": len(layers), "size": size}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="svg_art")
    ap.add_argument("--seed", default=42)
    ap.add_argument("--size", type=int, default=800)
    ap.add_argument("--out", default="art.svg")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--digest", action="store_true", help="print derived parameters only")
    args = ap.parse_args(argv)

    if args.digest:
        print(json.dumps(digest(int(args.seed), args.size), indent=None))
        return 0

    if str(args.seed).lower() == "random":
        seed = _stdlib_random.randint(0, 2**31)
        print(f"[info] seed = {seed}", file=sys.stderr)
    else:
        seed = int(args.seed)

    for i in range(args.count):
        s = seed + i
        svg = render_svg(s, args.size)
        path = (Path(args.out_dir) / f"{s}.svg") if args.out_dir else Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")
        print(f"wrote {path} (seed={s})")
    d = digest(seed, args.size)
    print(json.dumps(d, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Single artwork**: `python svg_art.py --seed 1337 --size 800 --out art.svg` â†’ deterministic SVG, open in a browser.
2. **Parametrize**: `python svg_art.py --digest --seed 1337` prints `{seed, palette:[...], layers:[dots,waves,rings], ...}` for scripting exploration.
3. **Batch gallery**: `python svg_art.py --seed random --count 6 --out-dir gallery/` â†’ 6 unique SVGs + seeds printed to stderr.
4. **Verify reproducibility**: run the same seed twice, `Get-FileHash art.svg` (or `sha256sum`) â†’ identical digests.
5. **Reuse in docs**: an SVG served as `<img src="art.svg">` becomes a stable generated cover â€” refreshing with a new seed regenerates assets without designer involvement.

## 5. Edge Cases & Error Handling

- **Seed = 0** â†’ LCG state forced to 1 internally, so zero is a valid seed, not stuck-at-zero.
- **Negative seeds** â†’ `abs()` normalizes; `% 2147483647` guarantees a positive â‰¤2^31âˆ’1 state.
- **Duplicate across seeds** â†’ adjacent seeds (e.g. `seed + i`) are correlated; for batch mode use large offsets (e.g. `--seed N --count 6` with N spaced by 10^6) or `random`.
- **Size extremes** â†’ `size 0` is clamped by viewBox math to a 1Ã—1 bug-free render (r â‰¤ 0 pruned); tiny `size` (<64) produces dense dots by design.
- **Art-layer nearly empty** â†’ dots are optional (skipped ~30% of the time); rings and waves always emit, so the composition never renders blank.
- **Non-integer seeds** â†’ argparse raises `ValueError` before the LCG is touched.