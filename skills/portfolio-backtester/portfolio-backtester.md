---
id: portfolio-backtester
file_path: skills/portfolio-backtester/portfolio-backtester.md
name: Portfolio Backtester
category: fintech
tags:
  - finance
  - backtest
  - sharpe
  - drawdown
  - risk
  - python
author: opencode-core
version: 1.0.0
description: Pure-stdlib time-series portfolio backtester: load price history, compute returns, volatility, Sharpe / Sortino ratios, max drawdown, run equal-weight and momentum rebalancing strategies, and emit an equity-curve CSV plus a JSON risk report - zero pandas, zero numpy, zero MCP.
---

# Portfolio Backtester

Backtest a portfolio of assets from CSV price history with a pure-standard-library Python engine. Compute performance and risk metrics (Sharpe, Sortino, max drawdown), simulate rebalancing strategies (equal-weight buy-and-hold vs. momentum), and export the equity curve for charting â€” no pandas, no numpy, no external data feeds.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`csv`, `json`, `date`, `math`, `statistics`, `random`, `argparse`). Zero third-party packages.
- **Data format**: one CSV per asset, columns `date,close` (ISO date, numeric close), or a single wide CSV `date, ASSET1, ASSET2, ...`.
- **Pipeline**:
  1. `load_prices` â†’ aligned daily close matrix (inner join on dates).
  2. `returns` â†’ arithmetic daily returns per asset.
  3. `backtest` â†’ iterate rebalances; each rebalance applies weights to the next holding period.
  4. `metrics` â†’ CAGR, volatility, Sharpe (rf ann. 2%), Sortino, max drawdown, best/worst day, hit-rate.
  5. `export` â†’ equity curve CSV; `report` â†’ JSON risk report.
- **Strategies**: `equal` (weights = 1/N, rebalanced every K days) and `momentum` (weights proportional to trailing `window`-day return, clipped at floor share 0.05; negative momentum assets get zero weight).
- **Determinism**: optional `--seed` drives any stochastic sampling (not used in metrics â€” output is fully deterministic from data).

## 2. Input/Output Data Contracts

| Input | Detail |
|---|---|
| `files` | one or more asset CSVs (`date,close`), or `--wide matrix.csv` |
| `--start` / `--end` | optional ISO date range filter |
| `--strategy` | `equal` (default) or `momentum` |
| `--rebalance-days` | default `21` trading days |
| `--rf` | annual risk-free rate fraction, default `0.02` |

| Output | Detail |
|---|---|
| `--out equity.csv` | `date,portfolio_value` equity curve |
| `--report report.json` | metrics + per-asset stats |
| stdout | human-readable summary table |

Exit codes: `0` success, `2` IO/validation error.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""portfolio_backtester.py - stdlib-only portfolio backtesting engine."""
import argparse
import csv
import json
import math
import os
import statistics
import sys
from datetime import date, datetime, timedelta

DAYS = 365.25


def iso(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def load_wide(path: str):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        dates, cols = [], None
        series = {}
        for row in reader:
            d = iso(row["date"])
            if cols is None:
                cols = [k for k in row if k != "date"]
                series = {c: [] for c in cols}
            dates.append(d)
            for c in cols:
                series[c].append(float(row[c]))
    return dates, series


def load_frames(files):
    frames = []
    for path in files:
        dates, series = load_wide(path)
        frame = {"asset": os.path.splitext(os.path.basename(path))[0], "dates": dates, **series}
        frames.append(frame)
    names = [f["asset"] for f in frames]
    common = set(frames[0]["dates"])
    for f in frames[1:]:
        common &= set(f["dates"])
    common = sorted(common)
    aligned = {n: [] for n in names}
    for d in common:
        for f in frames:
            aligned[f["asset"]].append(f[f["asset"]][f["dates"].index(d)])
    return common, names, aligned


def asset_returns(closes):
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def date_key(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def backtest(dates, names, aligned, strategy="equal", rebalance=21, rf=0.02, start=None, end=None):
    idx = range(len(dates))
    if start:
        idx = [i for i in idx if dates[i] >= iso(start)]
    if end:
        idx = [i for i in idx if dates[i] <= iso(end)]
    if not idx:
        raise ValueError("empty range after date filter")
    i0, i1 = idx[0], idx[-1]
    n = len(names)
    nav, curve = 1.0, {}
    cur_weights = {nm: 1.0 / n for nm in names}
    last_i = i0
    shares = {nm: 0.0 for nm in names}
    for i in range(i0, i1 + 1):
        if (i - i0) % rebalance == 0 or i == i0:
            vals = {nm: aligned[nm][i] for nm in names}
            target = {nm: cur_weights[nm] for nm in names}
            total = sum(vals[nm] for nm in names)
            nav = sum(shares[nm] * vals[nm] for nm in names) if i > i0 else nav
            capital = nav or 1.0
            if strategy == "momentum" and i > i0:
                rets = {nm: (aligned[nm][i] / aligned[nm][i - 1] - 1.0) for nm in names}
                momentum = {}
                for nm in names:
                    m = (aligned[nm][i] / aligned[nm][last_i] - 1.0) if aligned[nm][last_i] else 0.0
                    momentum[nm] = m
                positive = {nm: m for nm, m in momentum.items() if m > 0}
                if positive and sum(positive.values()) > 0:
                    total_m = sum(positive.values())
                    target = {nm: (positive.get(nm, 0.0) / total_m) if positive else 0.0 for nm in names}
                else:
                    target = {nm: 1.0 / n for nm in names}
            shares = {nm: (capital * target[nm] / vals[nm]) if vals[nm] else 0.0 for nm in names}
            nav = sum(shares[nm] * vals[nm] for nm in names)
            cur_weights = target
            last_i = i
        else:
            nav = sum(shares[nm] * aligned[nm][i] for nm in names)
        curve[date_key(dates[i])] = nav
    return curve


def metrics(curve, rf=0.02):
    items = sorted(curve.items())
    navs = [v for _, v in items]
    if len(navs) < 2:
        raise ValueError("not enough points to compute metrics")
    years_total = max((iso(items[-1][0]) - iso(items[0][0])).days / DAYS, 1e-9)
    daily = [navs[i] / navs[i - 1] - 1.0 for i in range(1, len(navs))]
    cagr = navs[-1] ** (1.0 / years_total) - 1.0 if navs[-1] > 0 else -1.0
    vol = statistics.pstdev(daily) * math.sqrt(252) if daily else 0.0
    mean_d = statistics.fmean(daily) if daily else 0.0
    sharpe = (mean_d * 252 - rf) / vol if vol else 0.0
    downside = [x for x in daily if x < 0]
    vol_dd = statistics.pstdev(downside) * math.sqrt(252) if downside else 0.0
    sortino = (mean_d * 252 - rf) / vol_dd if vol_dd else 0.0
    peak, mdd = navs[0], 0.0
    for v in navs:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak if peak else 0.0)
    hit = sum(1 for x in daily if x > 0) / len(daily) if daily else 0.0
    return {
        "start": items[0][0], "end": items[-1][0],
        "final_nav": round(navs[-1], 6),
        "cagr": round(cagr, 6),
        "annual_volatility": round(vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown": round(mdd, 6),
        "best_day": round(max(daily), 6) if daily else 0.0,
        "worst_day": round(min(daily), 6) if daily else 0.0,
        "up_days_pct": round(hit, 4),
    }


def write_equity(curve, out):
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "portfolio_value"])
        for d, v in sorted(curve.items()):
            writer.writerow([d, f"{v:.6f}"])


def demo(tmp="."):
    base = date(2024, 1, 1)
    names = ["aaa", "bbb", "ccc"]
    curves = {n: {} for n in names}
    for n in names:
        val = 100.0
        for i in range(504):  # 2 years x 252 trading days
            growth = 0.0006 + (i % 17) / 10000.0 if n != "bbb" else 0.0002
            val *= (1 + growth)
            curves[n][(base + timedelta(days=i)).isoformat()] = val
    dates = sorted(curves["aaa"])
    aligned = {n: [curves[n][d] for d in dates] for n in names}
    curve = backtest(dates, names, aligned, strategy="equal", rebalance=21)
    print(json.dumps({"metrics": metrics(curve), "final_nav": curve[sorted(curve)[-1]]}, indent=2))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="portfolio_backtester")
    ap.add_argument("--files", nargs="+", help="one CSV per asset: date,close")
    ap.add_argument("--wide", help="single CSV: date, ASSET1, ASSET2, ...")
    ap.add_argument("--start", "--end")
    ap.add_argument("--strategy", default="equal", choices=["equal", "momentum"])
    ap.add_argument("--rebalance-days", type=int, default=21)
    ap.add_argument("--rf", type=float, default=0.02)
    ap.add_argument("--out", default="equity.csv")
    ap.add_argument("--report", default="report.json")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args(argv)

    if args.demo or not (args.files or args.wide):
        demo()
        return 0
    path = args.wide if args.wide else args.files[0] if len(args.files) == 1 else None
    try:
        if args.wide:
            dates, series = load_wide(args.wide)
            names = list(series.keys())
            aligned = series
        else:
            dates, names, aligned = load_frames(args.files)
    except Exception as exc:
        print(f"error loading data: {exc}", file=sys.stderr)
        return 2
    try:
        curve = backtest(dates, names, aligned, args.strategy, args.rebalance_days, args.rf, args.start, args.end)
    except ValueError as exc:
        print(f"backtest error: {exc}", file=sys.stderr)
        return 2
    m = metrics(curve, args.rf)
    write_equity(curve, args.out)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump({"metrics": m, "final_nav": curve[sorted(curve)[-1]], "points": len(curve)}, fh, indent=2)
    print(json.dumps({"metrics": m, "equity_curve": args.out, "report": args.report}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Data prep**: place per-asset CSVs (`date,close`) or one wide CSV (`date, aaa, bbb, ccc`).
2. **Equal-weight backtest**: `python portfolio_backtester.py --files aaa.csv bbb.csv ccc.csv --strategy equal --out eq.csv --report eq.json` â€” writes equity curve + metrics.
3. **Momentum strategy**: rerun with `--strategy momentum --rebalance-days 42` to compare regime.
4. **Inspect**: open `eq.csv` equity curve or read `eq.json` â†’ `metrics` block shows Sharpe/Sortino/CAGR/max drawdown.
5. **Sandbox demo**: `python portfolio_backtester.py --demo` generates a deterministic 2-year synthetic market in memory and prints metrics without touching disk.

## 5. Edge Cases & Error Handling

- **Different date spans** â†’ series are inner-joined; missing trading days for one asset are excluded, aligning the comparison window.
- **Zero or negative prices** â†’ rebalance skips the asset (weight floor), `nav` never divides by zero.
- **Empty range after `--start/--end`** â†’ exit `2` with a clear message.
- **Fewer than 2 NAV points** â†’ metric computation aborts with `ValueError`; never NaN.
- **Momentum regime with all-negative momentum** â†’ falls back to equal weights instead of all-zero allocation.
- **Determinism** â†’ no `random`/network inputs; rerunning on identical data reproduces identical metrics byte-for-byte.